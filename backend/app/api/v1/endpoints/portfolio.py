from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.account import Account
from app.models.asset import Asset, PriceHistory
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.portfolio import (
    AllocationOut,
    DividendOut,
    PerformanceOut,
    PortfolioSummaryOut,
    PositionOut,
)
from app.services.market_data.updater import get_cached_price, refresh_asset_price
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.performance import get_portfolio_performance
from app.services.portfolio.positions import calculate_positions
from app.services.transaction import get_transactions

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_ALL = 10_000  # limite pratico "prendi tutto"


async def _load_all_transactions(db: AsyncSession, user_id: int):
    return await get_transactions(db, user_id, limit=_ALL)


async def _price_data(db: AsyncSession, asset: Asset) -> dict | None:
    """Legge il prezzo dalla cache Redis; se manca, lo scarica live; fallback a price_history."""
    cached = await get_cached_price(asset.id)
    if cached is None:
        try:
            cached = await refresh_asset_price(db, asset)
        except Exception:
            pass

    if cached is not None:
        return cached

    # Fallback: ultimi 2 record da price_history
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset.id)
        .order_by(PriceHistory.date.desc())
        .limit(2)
    )
    rows = list(result.scalars())
    if rows:
        last = rows[0]
        prev = rows[1] if len(rows) >= 2 else rows[0]
        change_pct = round((last.close - prev.close) / prev.close * 100, 4) if prev.close else 0.0
        return {
            "price": last.close,
            "prev_close": prev.close,
            "change_pct": change_pct,
            "currency": asset.currency,
            "exchange_rate": 1.0,
        }

    return None


# ── Posizioni aperte ─────────────────────────────────────────────────────────


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)
    if not positions:
        return []

    result = await db.execute(
        select(Asset).where(Asset.id.in_(list(positions.keys())))
    )
    asset_map = {a.id: a for a in result.scalars()}

    out: list[PositionOut] = []
    for asset_id, pos in positions.items():
        asset = asset_map.get(asset_id)
        if not asset:
            continue

        data = await _price_data(db, asset)
        price = data.get("price") if data else None
        fx = data.get("exchange_rate", 1.0) if data else 1.0
        change_pct = data.get("change_pct") if data else None

        price_eur = price * fx if price is not None else None
        value_eur = pos.quantity * price_eur if price_eur is not None else None
        cost_basis = pos.quantity * pos.pmc_eur
        unrealized = (value_eur - cost_basis) if value_eur is not None else None
        unrealized_pct = (
            unrealized / cost_basis * 100
            if unrealized is not None and cost_basis > 0
            else None
        )

        out.append(PositionOut(
            asset_id=asset.id,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.type if isinstance(asset.type, str) else asset.type.value,
            currency=asset.currency,
            exchange=asset.exchange if isinstance(asset.exchange, str) else asset.exchange.value,
            quantity=pos.quantity,
            pmc_eur=round(pos.pmc_eur, 6),
            total_invested_eur=round(pos.total_invested_eur, 2),
            realized_pnl_eur=round(pos.realized_pnl_eur, 2),
            current_price=price,
            current_price_eur=round(price_eur, 4) if price_eur is not None else None,
            current_value_eur=round(value_eur, 2) if value_eur is not None else None,
            unrealized_pnl_eur=round(unrealized, 2) if unrealized is not None else None,
            unrealized_pnl_pct=round(unrealized_pct, 2) if unrealized_pct is not None else None,
            change_pct=change_pct,
        ))

    return sorted(out, key=lambda x: x.current_value_eur or 0, reverse=True)


# ── Sommario ─────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=PortfolioSummaryOut)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)

    result = await db.execute(
        select(Asset).where(Asset.id.in_(list(positions.keys())))
    )
    asset_map = {a.id: a for a in result.scalars()}

    total_value = 0.0
    total_invested = 0.0
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    daily_change = 0.0

    for asset_id, pos in positions.items():
        asset = asset_map.get(asset_id)
        if not asset:
            continue

        data = await _price_data(db, asset)
        realized_pnl += pos.realized_pnl_eur
        cost_basis = pos.quantity * pos.pmc_eur

        if data and data.get("price") is not None:
            price_eur = data["price"] * data.get("exchange_rate", 1.0)
            value = pos.quantity * price_eur
            total_value += value
            unrealized_pnl += value - cost_basis

            prev_close = data.get("prev_close")
            if prev_close is not None:
                prev_eur = prev_close * data.get("exchange_rate", 1.0)
                daily_change += pos.quantity * (price_eur - prev_eur)

        total_invested += cost_basis

    total_pnl = unrealized_pnl + realized_pnl
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return PortfolioSummaryOut(
        total_value_eur=round(total_value, 2),
        total_invested_eur=round(total_invested, 2),
        total_pnl_eur=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        realized_pnl_eur=round(realized_pnl, 2),
        unrealized_pnl_eur=round(unrealized_pnl, 2),
        daily_change_eur=round(daily_change, 2),
        positions_count=len(positions),
    )


# ── Performance (serie temporale) ────────────────────────────────────────────


@router.get("/performance", response_model=PerformanceOut)
async def get_performance(
    period: str = Query("1y", pattern=r"^(today|wtd|mtd|ytd|1w|1m|3m|6m|1y|3y|max|\d{4})$"),
    account_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    if account_id is not None:
        transactions = [tx for tx in transactions if tx.account_id == account_id]
    return await get_portfolio_performance(db, transactions, period)


# ── Allocazione ──────────────────────────────────────────────────────────────


@router.get("/allocation", response_model=AllocationOut)
async def get_allocation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)

    result = await db.execute(
        select(Asset).where(Asset.id.in_(list(positions.keys())))
    )
    assets_list = result.scalars().all()
    asset_map = {a.id: a for a in assets_list}

    asset_info = {
        a.id: {"type": a.type.value, "currency": a.currency}
        for a in assets_list
    }

    price_eur: dict[int, float] = {}
    for asset_id, pos in positions.items():
        asset = asset_map.get(asset_id)
        if not asset:
            continue
        data = await _price_data(db, asset)
        if data and data.get("price") is not None:
            price_eur[asset_id] = data["price"] * data.get("exchange_rate", 1.0)

    # Valore per conto
    accounts_result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    accounts_list = accounts_result.scalars().all()

    account_values: dict[str, float] = {}
    for acc in accounts_list:
        acc_txs = [tx for tx in transactions if tx.account_id == acc.id]
        acc_positions = calculate_positions(acc_txs)
        acc_value = sum(
            pos.quantity * price_eur[aid]
            for aid, pos in acc_positions.items()
            if aid in price_eur
        )
        if acc_value > 0:
            account_values[acc.name] = acc_value

    return calculate_allocation(positions, asset_info, price_eur, account_values)


# ── Dividendi e cedole ───────────────────────────────────────────────────────


@router.get("/dividends", response_model=list[DividendOut])
async def get_dividends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)

    accounts_result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    account_map = {a.id: a.name for a in accounts_result.scalars()}

    income_types = {TransactionType.DIVIDEND, TransactionType.COUPON, TransactionType.INTEREST}
    dividends: list[DividendOut] = []

    for tx in transactions:
        if tx.type not in income_types:
            continue
        amount_eur = tx.quantity * tx.price * tx.exchange_rate - tx.fee
        dividends.append(DividendOut(
            id=tx.id,
            date=tx.date,
            asset_id=tx.asset_id,
            symbol=tx.asset.symbol,
            name=tx.asset.name,
            type=tx.type.value,
            amount_eur=round(amount_eur, 2),
            account_name=account_map.get(tx.account_id, "—"),
            account_id=tx.account_id,
        ))

    return sorted(dividends, key=lambda d: d.date, reverse=True)


@router.post("/backfill-history", status_code=202)
async def backfill_history(
    current_user: User = Depends(get_current_user),
):
    """Avvia in background il download storico prezzi per tutti gli asset detenuti."""
    from app.tasks.prices import backfill_portfolio_history
    backfill_portfolio_history.delay(current_user.id)
    return {"detail": "Backfill avviato in background"}
