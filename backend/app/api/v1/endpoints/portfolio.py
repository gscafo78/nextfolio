import asyncio

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
    DashboardOut,
    DividendOut,
    HoldingDetailOut,
    PerformanceOut,
    PortfolioSummaryOut,
    PositionOut,
)
from app.services.market_data.updater import (
    get_cached_perf,
    get_cached_prices_bulk,
    refresh_asset_price,
    set_cached_perf,
)


async def _price_from_db(db: AsyncSession, asset: Asset) -> dict | None:
    """Fast DB-only fallback: last 2 rows from price_history."""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset.id)
        .order_by(PriceHistory.date.desc())
        .limit(2)
    )
    rows = list(result.scalars())
    if not rows:
        return None
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


async def _bg_refresh_prices(assets: list[Asset]) -> None:
    """Background task: refreshes all prices in parallel with a shared session."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await asyncio.gather(
            *[refresh_asset_price(db, a) for a in assets],
            return_exceptions=True,
        )


async def _fetch_prices_parallel(
    db: AsyncSession,
    asset_map: dict[int, Asset],
    background_tasks: "BackgroundTasks | None" = None,
) -> dict[int, dict | None]:
    """
    Fase 1 — bulk MGET Redis (una connessione, un round-trip).
    Fase 2 — cache miss: fallback DB istantaneo + refresh in background (non bloccante).
    """
    asset_ids = list(asset_map.keys())

    # Fase 1: singolo MGET
    cached_bulk = await get_cached_prices_bulk(asset_ids)
    price_map: dict[int, dict | None] = dict(zip(asset_ids, cached_bulk))

    # Fase 2: miss → DB price_history sequenziale (stesso AsyncSession, non safe per gather)
    miss_ids = [aid for aid, d in price_map.items() if d is None]
    if miss_ids:
        for aid in miss_ids:
            price_map[aid] = await _price_from_db(db, asset_map[aid])

        if background_tasks:
            background_tasks.add_task(_bg_refresh_prices, [asset_map[aid] for aid in miss_ids])

    return price_map
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.performance import get_portfolio_performance
from app.services.portfolio.positions import calculate_positions
from app.services.transaction import get_transactions

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_ALL = 10_000  # limite pratico "prendi tutto"


async def _load_all_transactions(db: AsyncSession, user_id: int):
    return await get_transactions(db, user_id, limit=_ALL)


async def _price_data(db: AsyncSession, asset: Asset) -> dict | None:
    """Cache Redis → DB fallback (live fetch in background, non bloccante)."""
    from app.services.market_data.updater import get_cached_price
    cached = await get_cached_price(asset.id)
    if cached is not None:
        return cached
    return await _price_from_db(db, asset)


# ── Posizioni aperte ─────────────────────────────────────────────────────────


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(
    background_tasks: BackgroundTasks,
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

    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    out: list[PositionOut] = []
    for asset_id, pos in positions.items():
        asset = asset_map.get(asset_id)
        if not asset:
            continue

        data = price_map.get(asset_id)
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


# ── Dashboard aggregata ──────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summary + positions + allocation in una sola chiamata (1 DB session, 1 Redis MGET)."""
    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)

    if not positions:
        empty_alloc = AllocationOut(by_type=[], by_currency=[], by_account=[], total_value_eur=0.0)
        empty_summary = PortfolioSummaryOut(
            total_value_eur=0.0, total_invested_eur=0.0, total_pnl_eur=0.0,
            total_pnl_pct=0.0, realized_pnl_eur=0.0, unrealized_pnl_eur=0.0,
            daily_change_eur=0.0, positions_count=0,
        )
        return DashboardOut(summary=empty_summary, positions=[], allocation=empty_alloc)

    result = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    assets_list = list(result.scalars())
    asset_map = {a.id: a for a in assets_list}

    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    # ── Build price_eur lookup (shared) ───────────────────────────────────────
    price_eur: dict[int, float] = {}
    for aid in positions:
        data = price_map.get(aid)
        if data and data.get("price") is not None:
            price_eur[aid] = data["price"] * data.get("exchange_rate", 1.0)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_value = 0.0
    total_invested = 0.0
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    daily_change = 0.0

    for aid, pos in positions.items():
        realized_pnl += pos.realized_pnl_eur
        cost_basis = pos.quantity * pos.pmc_eur
        total_invested += cost_basis
        if aid in price_eur:
            value = pos.quantity * price_eur[aid]
            total_value += value
            unrealized_pnl += value - cost_basis
            data = price_map.get(aid)
            if data and data.get("prev_close") is not None:
                prev_eur = data["prev_close"] * data.get("exchange_rate", 1.0)
                daily_change += pos.quantity * (price_eur[aid] - prev_eur)

    total_pnl = unrealized_pnl + realized_pnl
    summary = PortfolioSummaryOut(
        total_value_eur=round(total_value, 2),
        total_invested_eur=round(total_invested, 2),
        total_pnl_eur=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl / total_invested * 100, 2) if total_invested > 0 else 0.0,
        realized_pnl_eur=round(realized_pnl, 2),
        unrealized_pnl_eur=round(unrealized_pnl, 2),
        daily_change_eur=round(daily_change, 2),
        positions_count=len(positions),
    )

    # ── Positions ─────────────────────────────────────────────────────────────
    positions_out: list[PositionOut] = []
    for aid, pos in positions.items():
        asset = asset_map.get(aid)
        if not asset:
            continue
        data = price_map.get(aid)
        price = data.get("price") if data else None
        fx = data.get("exchange_rate", 1.0) if data else 1.0
        change_pct = data.get("change_pct") if data else None
        price_eur_val = price_eur.get(aid)
        value_eur = pos.quantity * price_eur_val if price_eur_val is not None else None
        cost_basis = pos.quantity * pos.pmc_eur
        unrealized = (value_eur - cost_basis) if value_eur is not None else None
        unrealized_pct = (
            unrealized / cost_basis * 100
            if unrealized is not None and cost_basis > 0 else None
        )
        positions_out.append(PositionOut(
            asset_id=asset.id,
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.type if isinstance(asset.type, str) else asset.type.value,
            currency=asset.currency,
            exchange=asset.exchange if isinstance(asset.exchange, str) else asset.exchange.value,
            quantity=pos.quantity,
            pmc_eur=round(pos.pmc_eur, 6),
            total_invested_eur=round(cost_basis, 2),
            realized_pnl_eur=round(pos.realized_pnl_eur, 2),
            current_price=price,
            current_price_eur=round(price_eur_val, 4) if price_eur_val is not None else None,
            current_value_eur=round(value_eur, 2) if value_eur is not None else None,
            unrealized_pnl_eur=round(unrealized, 2) if unrealized is not None else None,
            unrealized_pnl_pct=round(unrealized_pct, 2) if unrealized_pct is not None else None,
            change_pct=change_pct,
        ))
    positions_out.sort(key=lambda x: x.current_value_eur or 0, reverse=True)

    # ── Allocation ────────────────────────────────────────────────────────────
    asset_info = {
        a.id: {"type": a.type if isinstance(a.type, str) else a.type.value, "currency": a.currency}
        for a in assets_list
    }
    accounts_result = await db.execute(select(Account).where(Account.user_id == current_user.id))
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

    allocation = calculate_allocation(positions, asset_info, price_eur, account_values)

    return DashboardOut(summary=summary, positions=positions_out, allocation=allocation)


# ── Sommario ─────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=PortfolioSummaryOut)
async def get_summary(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)

    result = await db.execute(
        select(Asset).where(Asset.id.in_(list(positions.keys())))
    )
    asset_map = {a.id: a for a in result.scalars()}

    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    total_value = 0.0
    total_invested = 0.0
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    daily_change = 0.0

    for asset_id, pos in positions.items():
        asset = asset_map.get(asset_id)
        if not asset:
            continue

        data = price_map.get(asset_id)
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
    cached = await get_cached_perf(current_user.id, period, account_id)
    if cached:
        return PerformanceOut(**cached)
    transactions = await _load_all_transactions(db, current_user.id)
    if account_id is not None:
        transactions = [tx for tx in transactions if tx.account_id == account_id]
    result = await get_portfolio_performance(db, transactions, period)
    await set_cached_perf(current_user.id, period, account_id, result.model_dump(mode="json"))
    return result


# ── Allocazione ──────────────────────────────────────────────────────────────


@router.get("/allocation", response_model=AllocationOut)
async def get_allocation(
    background_tasks: BackgroundTasks,
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
        a.id: {"type": a.type if isinstance(a.type, str) else a.type.value, "currency": a.currency}
        for a in assets_list
    }

    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    price_eur: dict[int, float] = {}
    for asset_id in positions:
        data = price_map.get(asset_id)
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


@router.get("/holding/{asset_id}", response_model=HoldingDetailOut)
async def get_holding_detail(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi import HTTPException

    transactions = await _load_all_transactions(db, current_user.id)
    asset_txs = [tx for tx in transactions if tx.asset_id == asset_id]
    if not asset_txs:
        raise HTTPException(status_code=404, detail="Holding non trovata")

    positions = calculate_positions(transactions)
    pos = positions.get(asset_id)

    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset non trovato")

    # Prezzi correnti
    data = await _price_data(db, asset)
    price = data.get("price") if data else None
    fx = data.get("exchange_rate", 1.0) if data else 1.0
    change_pct = data.get("change_pct") if data else None
    price_eur = price * fx if price is not None else None

    quantity = pos.quantity if pos else 0.0
    pmc_eur = pos.pmc_eur if pos else 0.0
    total_invested = pos.total_invested_eur if pos else 0.0
    realized_pnl = pos.realized_pnl_eur if pos else 0.0
    cost_basis = quantity * pmc_eur
    value_eur = quantity * price_eur if price_eur is not None else None
    unrealized = (value_eur - cost_basis) if value_eur is not None else None
    unrealized_pct = (unrealized / cost_basis * 100) if (unrealized is not None and cost_basis > 0) else None

    def _ttype(tx) -> str:
        return tx.type if isinstance(tx.type, str) else tx.type.value

    # Storico prezzi dalla prima data di acquisto
    buy_dates = [tx.date for tx in asset_txs if _ttype(tx) == "BUY"]
    first_buy = min(buy_dates) if buy_dates else None

    ph_query = (
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id)
        .order_by(PriceHistory.date.asc())
    )
    if first_buy:
        ph_query = ph_query.where(PriceHistory.date >= first_buy)
    ph_result = await db.execute(ph_query)
    ph_rows = ph_result.scalars().all()
    price_history = [
        {"date": row.date, "price": round(row.close, 4)}
        for row in ph_rows
    ]

    closes = [row.close for row in ph_rows if row.close]
    min_price = round(min(closes), 4) if closes else None
    max_price = round(max(closes), 4) if closes else None
    total_fees = round(sum(tx.fee for tx in asset_txs), 2)

    # Attività (transazioni) per questo asset
    accounts_result = await db.execute(
        select(Account).where(Account.user_id == current_user.id)
    )
    account_map = {a.id: a for a in accounts_result.scalars()}

    activities = [
        {
            "id": tx.id,
            "type": _ttype(tx),
            "date": tx.date,
            "quantity": tx.quantity,
            "price": tx.price,
            "price_currency": tx.price_currency,
            "total_eur": round(tx.quantity * tx.price * tx.exchange_rate + tx.fee, 2),
            "fee": tx.fee,
            "account_name": account_map[tx.account_id].name if tx.account_id in account_map else "—",
            "account_id": tx.account_id,
        }
        for tx in sorted(asset_txs, key=lambda t: t.date, reverse=True)
    ]

    # Breakdown per conto
    holding_accounts = []
    for acc_id, acc in account_map.items():
        acc_txs = [tx for tx in asset_txs if tx.account_id == acc_id]
        if not acc_txs:
            continue
        acc_pos = calculate_positions(acc_txs)
        acc_holding = acc_pos.get(asset_id)
        acc_qty = acc_holding.quantity if acc_holding else 0.0
        if acc_qty <= 0:
            continue
        acc_value = acc_qty * price_eur if price_eur is not None else None
        holding_accounts.append({
            "account_id": acc_id,
            "account_name": acc.name,
            "quantity": acc_qty,
            "value_eur": round(acc_value, 2) if acc_value is not None else None,
            "pct": round((acc_qty / quantity) * 100, 1) if quantity > 0 else None,
        })

    return HoldingDetailOut(
        asset_id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        asset_type=asset.type.value if hasattr(asset.type, "value") else asset.type,
        currency=asset.currency,
        exchange=asset.exchange.value if hasattr(asset.exchange, "value") else asset.exchange,
        isin=asset.isin,
        quantity=quantity,
        pmc_eur=round(pmc_eur, 6),
        total_invested_eur=round(total_invested, 2),
        realized_pnl_eur=round(realized_pnl, 2),
        current_price=price,
        current_price_eur=round(price_eur, 4) if price_eur is not None else None,
        current_value_eur=round(value_eur, 2) if value_eur is not None else None,
        unrealized_pnl_eur=round(unrealized, 2) if unrealized is not None else None,
        unrealized_pnl_pct=round(unrealized_pct, 2) if unrealized_pct is not None else None,
        change_pct=change_pct,
        min_price=min_price,
        max_price=max_price,
        total_fees=total_fees,
        activities_count=len(asset_txs),
        first_buy_date=first_buy,
        price_history=price_history,
        activities=activities,
        accounts=holding_accounts,
    )


@router.post("/backfill-history", status_code=202)
async def backfill_history(
    current_user: User = Depends(get_current_user),
):
    """Avvia in background il download storico prezzi per tutti gli asset detenuti."""
    from app.tasks.prices import backfill_portfolio_history
    backfill_portfolio_history.delay(current_user.id)
    return {"detail": "Backfill avviato in background"}
