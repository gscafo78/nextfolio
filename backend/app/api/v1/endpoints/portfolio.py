import asyncio
from datetime import date, timedelta

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
    ETFHoldingOut,
    HoldingDetailOut,
    PerformanceOut,
    PortfolioSummaryOut,
    PositionOut,
    RiskMetricsOut,
    XRayResponse,
)
from app.services.portfolio.xray import compute_xray
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
from app.services.portfolio.risk import compute_risk_metrics
from app.services.portfolio.positions import calculate_positions
from app.services.portfolio.xirr import xirr as compute_xirr
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


# ── Helpers period P&L ───────────────────────────────────────────────────────

_PERIOD_DAYS_SIMPLE = {"1w": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 365 * 3}


def _period_start_date(period: str) -> date | None:
    """Restituisce la data di inizio del periodo, o None se non applicabile."""
    today = date.today()
    if period in ("today", "max", "all"):
        return None
    if period == "ytd":
        return today.replace(month=1, day=1)
    if period == "mtd":
        return today.replace(day=1)
    if period == "wtd":
        return today - timedelta(days=today.weekday())
    if period.isdigit() and len(period) == 4:
        return date(int(period), 1, 1)
    days = _PERIOD_DAYS_SIMPLE.get(period)
    return (today - timedelta(days=days)) if days else None


async def _period_start_prices(
    db: AsyncSession,
    asset_ids: list[int],
    start_date: date,
) -> dict[int, float]:
    """Ultimo prezzo disponibile ≤ start_date per ogni asset (DISTINCT ON PostgreSQL)."""
    if not asset_ids:
        return {}
    # DISTINCT ON (asset_id) con ORDER BY date DESC → riga più recente prima della data
    result = await db.execute(
        select(PriceHistory.asset_id, PriceHistory.close)
        .where(PriceHistory.asset_id.in_(asset_ids))
        .where(PriceHistory.date <= start_date)
        .order_by(PriceHistory.asset_id, PriceHistory.date.desc())
        .distinct(PriceHistory.asset_id)
    )
    return {row.asset_id: row.close for row in result}


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
    period: str = Query("ytd", pattern=r"^(today|wtd|mtd|ytd|1w|1m|3m|6m|1y|3y|max|\d{4})$"),
):
    """Summary + positions + allocation in una sola chiamata (1 DB session, 1 Redis MGET).
    Il param ``period`` arricchisce ogni posizione con period_pnl_eur/period_pnl_pct."""
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

    # ── Prezzi a inizio periodo (per period_pnl) ──────────────────────────────
    period_start = _period_start_date(period)
    start_prices: dict[int, float] = {}
    if period_start is not None and period != "today":
        start_prices = await _period_start_prices(db, list(positions.keys()), period_start)

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

        # period P&L: usa prezzo di inizio periodo × cambio attuale
        period_pnl_eur: float | None = None
        period_pnl_pct: float | None = None
        if period == "today" and change_pct is not None and value_eur is not None:
            # Variazione giornaliera in EUR
            period_pnl_eur = round(value_eur * (change_pct / 100) / (1 + change_pct / 100), 2)
            period_pnl_pct = round(change_pct, 2)
        elif value_eur is not None and aid in start_prices and start_prices[aid] > 0:
            start_value = pos.quantity * start_prices[aid] * fx
            period_pnl_eur = round(value_eur - start_value, 2)
            period_pnl_pct = round((value_eur - start_value) / start_value * 100, 2)
        elif unrealized is not None:
            # Fallback: periodo "max" (nessun start_price cercato) oppure asset
            # acquistato durante il periodo (nessun prezzo in price_history prima
            # della data di inizio) → P&L del periodo = P&L non realizzato totale
            period_pnl_eur = round(unrealized, 2)
            period_pnl_pct = round(unrealized_pct, 2) if unrealized_pct is not None else None

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
            period_pnl_eur=period_pnl_eur,
            period_pnl_pct=period_pnl_pct,
        ))
    positions_out.sort(key=lambda x: x.current_value_eur or 0, reverse=True)

    # ── Allocation ────────────────────────────────────────────────────────────
    asset_info = {
        a.id: {
            "type": a.type if isinstance(a.type, str) else a.type.value,
            "currency": a.currency,
            "sectors": a.sectors,
            "countries": a.countries,
            "sectors_override": a.sectors_override,
            "countries_override": a.countries_override,
        }
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


# ── Metriche di rischio ───────────────────────────────────────────────────────


@router.get("/risk", response_model=RiskMetricsOut)
async def get_risk_metrics(
    period: str = Query("3y", pattern=r"^(1m|3m|6m|1y|3y|max)$"),
    account_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = await _load_all_transactions(db, current_user.id)
    if account_id is not None:
        transactions = [tx for tx in transactions if tx.account_id == account_id]
    perf = await get_portfolio_performance(db, transactions, period)
    return compute_risk_metrics(period, perf.series)


# ── XIRR ─────────────────────────────────────────────────────────────────────


@router.get("/xirr")
async def get_xirr(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calcola XIRR (tasso interno di rendimento su flussi irregolari).
    Cash flow: ogni BUY = uscita negativa, ogni SELL/DIVIDEND/COUPON = entrata positiva.
    Il valore corrente del portafoglio viene aggiunto come incasso finale alla data odierna.
    """
    from datetime import date as date_type
    from app.models.transaction import TransactionType

    transactions = await _load_all_transactions(db, current_user.id)
    if not transactions:
        return {"xirr_pct": None}

    cashflows: list[tuple] = []
    for tx in transactions:
        total = tx.quantity * tx.price * tx.exchange_rate
        if tx.type == TransactionType.BUY:
            cashflows.append((tx.date, -(total + tx.fee)))
        elif tx.type == TransactionType.SELL:
            cashflows.append((tx.date, total - tx.fee))
        elif tx.type in (TransactionType.DIVIDEND, TransactionType.COUPON, TransactionType.INTEREST):
            cashflows.append((tx.date, total))

    if not cashflows:
        return {"xirr_pct": None}

    # Aggiungi il valore corrente del portafoglio come flusso finale
    positions = calculate_positions(transactions)
    asset_ids = list(positions.keys())
    assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
    asset_map = {a.id: a for a in assets_result.scalars()}
    price_map = await _fetch_prices_parallel(db, asset_map)

    current_value = 0.0
    for asset_id, lot_data in positions.items():
        price_data = price_map.get(asset_id)
        if price_data:
            qty = lot_data.quantity
            price_eur = price_data["price"] * price_data.get("exchange_rate", 1.0)
            current_value += qty * price_eur

    if current_value > 0:
        cashflows.append((date_type.today(), current_value))

    cashflows.sort(key=lambda x: x[0])
    result = compute_xirr(cashflows)
    return {"xirr_pct": result}


# ── Benchmark ────────────────────────────────────────────────────────────────


@router.get("/benchmark")
async def get_benchmark(
    index: str = Query("MSCI_WORLD", pattern=r"^(MSCI_WORLD|FTSE_MIB|SP500|NASDAQ)$"),
    period: str = Query("1y", pattern=r"^(1w|1m|3m|6m|1y|3y|max)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serie normalizzata a 100 per l'indice scelto nel periodo selezionato."""
    import asyncio
    from datetime import date as date_type, timedelta
    from functools import partial

    INDEX_TICKERS = {
        "MSCI_WORLD": "IWDA.AS",
        "FTSE_MIB": "FTSEMIB.MI",
        "SP500": "^GSPC",
        "NASDAQ": "^IXIC",
    }
    PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095, "max": 3650}

    ticker_sym = INDEX_TICKERS[index]
    days = PERIOD_DAYS[period]
    start = date_type.today() - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")

    def _fetch():
        import yfinance as yf
        t = yf.Ticker(ticker_sym)
        hist = t.history(start=start_str)
        if hist.empty:
            return []
        close = hist["Close"].dropna()
        if close.empty:
            return []
        base = float(close.iloc[0])
        if base == 0:
            return []
        return [
            {"date": str(idx.date()), "value": round(float(v) / base * 100, 4)}
            for idx, v in close.items()
        ]

    loop = asyncio.get_running_loop()
    series = await loop.run_in_executor(None, partial(_fetch))
    return {"index": index, "ticker": ticker_sym, "period": period, "series": series}


# ── Correlazione ─────────────────────────────────────────────────────────────


@router.get("/correlation")
async def get_correlation(
    period: str = Query("1y", pattern=r"^(3m|6m|1y|3y|max)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Matrice di correlazione Pearson dei rendimenti giornalieri tra le posizioni."""
    import math
    from datetime import date as date_type, timedelta

    PERIOD_DAYS = {"3m": 90, "6m": 180, "1y": 365, "3y": 1095, "max": 3650}
    days = PERIOD_DAYS[period]
    start = date_type.today() - timedelta(days=days)

    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)
    asset_ids = list(positions.keys())

    if not asset_ids:
        return {"labels": [], "matrix": []}

    # Carica price_history per tutti gli asset nel periodo
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id.in_(asset_ids))
        .where(PriceHistory.date >= start)
        .order_by(PriceHistory.date)
    )
    rows = list(result.scalars())

    # Raggruppa per asset_id
    price_series: dict[int, dict] = {aid: {} for aid in asset_ids}
    for row in rows:
        price_series[row.asset_id][row.date] = row.close

    # Filtra asset con almeno 10 prezzi
    valid_ids = [aid for aid, prices in price_series.items() if len(prices) >= 10]
    if not valid_ids:
        return {"labels": [], "matrix": []}

    # Carica simboli
    assets_result = await db.execute(select(Asset).where(Asset.id.in_(valid_ids)))
    asset_map = {a.id: a.symbol for a in assets_result.scalars()}

    # Calcola rendimenti giornalieri per ogni asset
    def daily_returns(prices: dict) -> list[float]:
        sorted_dates = sorted(prices.keys())
        returns = []
        for i in range(1, len(sorted_dates)):
            prev = prices[sorted_dates[i - 1]]
            curr = prices[sorted_dates[i]]
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns

    returns_map: dict[int, list[float]] = {}
    for aid in valid_ids:
        r = daily_returns(price_series[aid])
        if len(r) >= 5:
            returns_map[aid] = r

    final_ids = list(returns_map.keys())
    if not final_ids:
        return {"labels": [], "matrix": []}

    labels = [asset_map.get(aid, str(aid)) for aid in final_ids]

    def pearson(x: list[float], y: list[float]) -> float:
        n = min(len(x), len(y))
        if n < 3:
            return 0.0
        x, y = x[-n:], y[-n:]
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return 1.0 if sx == sy else 0.0
        return round(num / (sx * sy), 4)

    matrix = [
        [pearson(returns_map[ai], returns_map[aj]) for aj in final_ids]
        for ai in final_ids
    ]
    return {"labels": labels, "matrix": matrix, "period": period}


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
        a.id: {
            "type": a.type if isinstance(a.type, str) else a.type.value,
            "currency": a.currency,
            "sectors": a.sectors,
            "countries": a.countries,
            "sectors_override": a.sectors_override,
            "countries_override": a.countries_override,
        }
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
            type=tx.type.value if hasattr(tx.type, "value") else tx.type,
            amount_eur=round(amount_eur, 2),
            account_name=account_map.get(tx.account_id, "—"),
            account_id=tx.account_id,
        ))

    return sorted(dividends, key=lambda d: d.date, reverse=True)


@router.get("/dividend-analysis")
async def get_dividend_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analisi approfondita dei dividendi/cedole:
    - totale per anno
    - totale per mese (calendario)
    - yield on cost per posizione (dividendi totali / costo di acquisto)
    - crescita anno su anno
    """
    from collections import defaultdict

    transactions = await _load_all_transactions(db, current_user.id)
    income_types = {TransactionType.DIVIDEND, TransactionType.COUPON, TransactionType.INTEREST}

    # Raggruppa per anno e per mese
    by_year: dict[int, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    by_asset: dict[int, float] = defaultdict(float)

    for tx in transactions:
        if tx.type not in income_types:
            continue
        amount = tx.quantity * tx.price * tx.exchange_rate - tx.fee
        by_year[tx.date.year] += amount
        month_key = tx.date.strftime("%Y-%m")
        by_month[month_key] += amount
        by_asset[tx.asset_id] += amount

    # Costo di acquisto per asset (per yield on cost)
    positions = calculate_positions(transactions)
    assets_result = await db.execute(select(Asset).where(Asset.id.in_(list(by_asset.keys()))))
    asset_map = {a.id: a for a in assets_result.scalars()}

    yield_on_cost = []
    for asset_id, income_total in by_asset.items():
        pos = positions.get(asset_id)
        asset = asset_map.get(asset_id)
        if not asset:
            continue
        cost = pos.total_invested_eur if pos else 0.0
        yoc = round(income_total / cost * 100, 4) if cost > 0 else None
        yield_on_cost.append({
            "asset_id": asset_id,
            "symbol": asset.symbol,
            "name": asset.name,
            "total_income_eur": round(income_total, 2),
            "cost_basis_eur": round(cost, 2),
            "yield_on_cost_pct": yoc,
        })
    yield_on_cost.sort(key=lambda x: x["total_income_eur"], reverse=True)

    # Crescita anno su anno
    sorted_years = sorted(by_year.keys())
    yoy_growth = []
    for i, year in enumerate(sorted_years):
        amount = round(by_year[year], 2)
        prev = by_year.get(sorted_years[i - 1], 0) if i > 0 else None
        growth_pct = round((amount - prev) / prev * 100, 2) if (prev and prev > 0) else None
        yoy_growth.append({"year": year, "amount_eur": amount, "growth_pct": growth_pct})

    monthly_series = [
        {"month": k, "amount_eur": round(v, 2)}
        for k, v in sorted(by_month.items())
    ]

    return {
        "total_income_eur": round(sum(by_year.values()), 2),
        "by_year": yoy_growth,
        "by_month": monthly_series,
        "yield_on_cost": yield_on_cost,
    }


@router.get("/country-allocation")
async def get_country_allocation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
):
    """Allocazione geografica del portafoglio per paese (con classificazione MSCI)."""

    DEVELOPED = {"AU","AT","BE","CA","DK","FI","FR","DE","HK","IE","IL","IT","JP","NL","NZ","NO","PT","SG","ES","SE","CH","GB","US"}
    EMERGING = {"BR","CL","CN","CO","CZ","EG","GR","HU","IN","ID","KR","KW","MY","MX","MA","PE","PH","PL","QA","SA","ZA","TW","TH","TR","AE"}

    NAME_TO_ISO2: dict[str, str] = {
        "United States": "US", "USA": "US",
        "Germany": "DE",
        "France": "FR",
        "United Kingdom": "GB", "UK": "GB",
        "Japan": "JP",
        "Canada": "CA",
        "Switzerland": "CH",
        "Australia": "AU",
        "Netherlands": "NL",
        "Sweden": "SE",
        "Denmark": "DK",
        "Norway": "NO",
        "Finland": "FI",
        "Belgium": "BE",
        "Italy": "IT",
        "Spain": "ES",
        "Portugal": "PT",
        "Austria": "AT",
        "Ireland": "IE",
        "Singapore": "SG",
        "Hong Kong": "HK",
        "New Zealand": "NZ",
        "Israel": "IL",
        "China": "CN",
        "India": "IN",
        "Brazil": "BR",
        "South Korea": "KR", "Korea": "KR",
        "Taiwan": "TW",
        "Mexico": "MX",
        "South Africa": "ZA",
        "Russia": "RU",
        "Indonesia": "ID",
        "Thailand": "TH",
        "Malaysia": "MY",
        "Poland": "PL",
        "Turkey": "TR",
        "Saudi Arabia": "SA",
        "United Arab Emirates": "AE", "UAE": "AE",
        "Egypt": "EG",
        "Argentina": "AR",
        "Chile": "CL",
        "Colombia": "CO",
        "Peru": "PE",
        "Philippines": "PH",
        "Czech Republic": "CZ",
        "Hungary": "HU",
        "Greece": "GR",
        "Morocco": "MA",
        "Kuwait": "KW",
        "Qatar": "QA",
        "Luxembourg": "LU",
        "Denmark": "DK",
        "Romania": "RO",
        "Ukraine": "UA",
        "Pakistan": "PK",
        "Bangladesh": "BD",
        "Vietnam": "VN",
        "Nigeria": "NG",
        "Kenya": "KE",
        "United States of America": "US",
    }

    COUNTRY_NAMES: dict[str, str] = {
        "US": "Stati Uniti", "DE": "Germania", "FR": "Francia", "GB": "Regno Unito",
        "JP": "Giappone", "CA": "Canada", "CH": "Svizzera", "AU": "Australia",
        "NL": "Paesi Bassi", "SE": "Svezia", "DK": "Danimarca", "NO": "Norvegia",
        "FI": "Finlandia", "BE": "Belgio", "IT": "Italia", "ES": "Spagna",
        "PT": "Portogallo", "AT": "Austria", "IE": "Irlanda", "SG": "Singapore",
        "HK": "Hong Kong", "NZ": "Nuova Zelanda", "IL": "Israele",
        "CN": "Cina", "IN": "India", "BR": "Brasile", "KR": "Corea del Sud",
        "TW": "Taiwan", "MX": "Messico", "ZA": "Sudafrica", "RU": "Russia",
        "ID": "Indonesia", "TH": "Tailandia", "MY": "Malesia", "PL": "Polonia",
        "TR": "Turchia", "SA": "Arabia Saudita", "AE": "Emirati Arabi", "EG": "Egitto",
        "AR": "Argentina", "CL": "Cile", "CO": "Colombia", "PE": "Perù",
        "PH": "Filippine", "CZ": "Rep. Ceca", "HU": "Ungheria", "GR": "Grecia",
        "MA": "Marocco", "KW": "Kuwait", "QA": "Qatar", "LU": "Lussemburgo",
        "RO": "Romania", "UA": "Ucraina", "PK": "Pakistan", "VN": "Vietnam",
        "NG": "Nigeria", "KE": "Kenya",
        "SK": "Slovacchia", "LV": "Lettonia", "LT": "Lituania", "SI": "Slovenia", "EE": "Estonia",
        "HR": "Croazia", "BG": "Bulgaria", "RS": "Serbia", "BA": "Bosnia", "MK": "Macedonia",
        "IS": "Islanda", "CY": "Cipro", "MT": "Malta", "LI": "Liechtenstein",
    }

    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)
    if not positions:
        return {"countries": [], "totals": {"developed_pct": 0.0, "emerging_pct": 0.0, "other_pct": 0.0, "no_data_pct": 100.0}}

    result = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    assets_map = {a.id: a for a in result.scalars().all()}

    price_map = await _fetch_prices_parallel(db, assets_map, background_tasks)

    total_portfolio_eur = 0.0
    country_values: dict[str, float] = {}
    valued_eur = 0.0

    for asset_id, pos in positions.items():
        asset = assets_map.get(asset_id)
        if not asset:
            continue
        data = price_map.get(asset_id)
        price = data.get("price") if data else None
        fx = data.get("exchange_rate", 1.0) if data else 1.0
        value_eur = pos.quantity * price * fx if price is not None else pos.total_invested_eur
        total_portfolio_eur += value_eur

        raw_countries = asset.countries_override if asset.countries_override is not None else asset.countries
        if not raw_countries:
            continue

        # Normalizza i pesi a 1.0 (gestisce input approssimativi)
        weight_sum = sum(float(c.get("weight", 0)) for c in raw_countries)
        if weight_sum <= 0:
            continue

        valued_eur += value_eur
        for c in raw_countries:
            code = str(c.get("code", "")).strip()
            weight = float(c.get("weight", 0)) / weight_sum  # normalizzato
            if len(code) == 2:
                iso2 = code.upper()
            else:
                iso2 = NAME_TO_ISO2.get(code, "XX")
            if iso2 == "XX":
                continue
            country_values[iso2] = country_values.get(iso2, 0.0) + value_eur * weight

    if total_portfolio_eur == 0:
        return {"countries": [], "totals": {"developed_pct": 0.0, "emerging_pct": 0.0, "other_pct": 0.0, "no_data_pct": 100.0}}

    countries_out = []
    for iso2, val in sorted(country_values.items(), key=lambda kv: kv[1], reverse=True):
        pct = round(val / total_portfolio_eur * 100, 4)
        market_type = "developed" if iso2 in DEVELOPED else ("emerging" if iso2 in EMERGING else "other")
        countries_out.append({
            "code": iso2,
            "name": COUNTRY_NAMES.get(iso2, iso2),
            "value_eur": round(val, 2),
            "pct": pct,
            "market_type": market_type,
        })

    developed_val = sum(v for k, v in country_values.items() if k in DEVELOPED)
    emerging_val = sum(v for k, v in country_values.items() if k in EMERGING)
    other_val = sum(v for k, v in country_values.items() if k not in DEVELOPED and k not in EMERGING)
    no_data_val = max(0.0, total_portfolio_eur - valued_eur)

    return {
        "countries": countries_out,
        "totals": {
            "developed_pct": round(developed_val / total_portfolio_eur * 100, 2),
            "emerging_pct": round(emerging_val / total_portfolio_eur * 100, 2),
            "other_pct": round(other_val / total_portfolio_eur * 100, 2),
            "no_data_pct": round(no_data_val / total_portfolio_eur * 100, 2),
        },
    }


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
        sectors=_build_sector_items(asset),
        countries=_build_country_items(asset),
    )


def _build_sector_items(asset) -> list | None:
    from app.schemas.portfolio import SectorItem
    raw = asset.sectors_override if asset.sectors_override is not None else asset.sectors
    if not raw:
        return None
    return [SectorItem(name=s.get("name", ""), weight=float(s.get("weight", 0))) for s in raw]


def _build_country_items(asset) -> list | None:
    from app.schemas.portfolio import CountryItem
    raw = asset.countries_override if asset.countries_override is not None else asset.countries
    if not raw:
        return None
    return [CountryItem(code=c.get("code", ""), name=c.get("name", ""), weight=float(c.get("weight", 0))) for c in raw]


# ── ETF Holdings (look-through) ───────────────────────────────────────────────


@router.get("/etf-holdings", response_model=list[ETFHoldingOut])
async def get_etf_holdings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
):
    """Restituisce le posizioni ETF/BOND con le rispettive holdings (top 10)."""
    from app.models.asset import AssetType

    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)
    if not positions:
        return []

    result = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    assets_list = result.scalars().all()
    asset_map_obj = {a.id: a for a in assets_list}

    price_map = await _fetch_prices_parallel(db, asset_map_obj, background_tasks)

    out: list[ETFHoldingOut] = []
    for asset_id, pos in positions.items():
        asset = asset_map_obj.get(asset_id)
        if not asset:
            continue
        asset_type = asset.type if isinstance(asset.type, str) else asset.type.value
        if asset_type not in ("ETF", "BOND"):
            continue

        # Override ha priorità sui dati auto-enriched
        raw_holdings = asset.holdings_override if asset.holdings_override is not None else (asset.holdings or [])

        data = price_map.get(asset_id)
        price = data.get("price") if data else None
        fx = data.get("exchange_rate", 1.0) if data else 1.0
        value_eur = round(pos.quantity * price * fx, 2) if price is not None else None

        from app.schemas.portfolio import ETFHoldingItem
        from app.schemas.portfolio import CountryItem
        co = asset.countries_override
        countries_out = [
            CountryItem(code=c.get("code",""), name=c.get("name",""), weight=float(c.get("weight",0)))
            for c in co
        ] if co else None

        out.append(ETFHoldingOut(
            asset_id=asset_id,
            symbol=asset.symbol,
            name=asset.name,
            value_eur=value_eur,
            holdings=[
                ETFHoldingItem(
                    symbol=h.get("symbol", ""),
                    name=h.get("name", ""),
                    weight=float(h.get("weight", 0)),
                )
                for h in raw_holdings
            ],
            is_override=asset.holdings_override is not None,
            countries_override=countries_out,
        ))

    return sorted(out, key=lambda x: x.value_eur or 0, reverse=True)


@router.get("/xray", response_model=XRayResponse)
async def get_xray(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analisi diagnostica X-Ray: 10 regole di rischio in 4 categorie."""
    from app.services.market_data.updater import get_cached_price

    transactions = await _load_all_transactions(db, current_user.id)
    positions_map = calculate_positions(transactions)

    if not positions_map:
        return XRayResponse(rules=[], score=0, rules_total=0, rules_ok=0)

    # Prezzi correnti per calcolare i pesi
    result = await db.execute(select(Asset).where(Asset.id.in_(list(positions_map.keys()))))
    asset_map = {a.id: a for a in result.scalars()}
    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    price_eur: dict[int, float] = {}
    for aid in positions_map:
        data = price_map.get(aid)
        if data and data.get("price") is not None:
            price_eur[aid] = data["price"] * data.get("exchange_rate", 1.0)

    # Posizioni semplificate (solo i campi necessari a compute_xray)
    from app.schemas.portfolio import PositionOut as POut

    positions_out: list[POut] = []
    for aid, pos in positions_map.items():
        asset = asset_map.get(aid)
        if not asset:
            continue
        peur = price_eur.get(aid)
        cost = pos.quantity * pos.pmc_eur
        val = pos.quantity * peur if peur else None
        unreal = (val - cost) if val else None
        positions_out.append(POut(
            asset_id=asset.id, symbol=asset.symbol, name=asset.name,
            asset_type=asset.type if isinstance(asset.type, str) else asset.type.value,
            currency=asset.currency,
            exchange=asset.exchange if isinstance(asset.exchange, str) else asset.exchange.value,
            quantity=pos.quantity, pmc_eur=pos.pmc_eur, total_invested_eur=cost,
            realized_pnl_eur=pos.realized_pnl_eur,
            current_price=price_map.get(aid, {}).get("price"),
            current_price_eur=peur, current_value_eur=val,
            unrealized_pnl_eur=unreal,
            unrealized_pnl_pct=(unreal / cost * 100 if unreal and cost > 0 else None),
            change_pct=price_map.get(aid, {}).get("change_pct"),
        ))

    total_value = sum(p.current_value_eur or 0 for p in positions_out)

    # Ricalcola allocazione (serve by_type, by_currency, by_account, by_continent)
    from app.models.account import Account as AccModel
    from app.services.portfolio.allocation import calculate_allocation

    assets_list = list(asset_map.values())
    asset_info = {
        a.id: {
            "type": a.type if isinstance(a.type, str) else a.type.value,
            "currency": a.currency,
            "sectors": a.sectors,
            "countries": a.countries,
            "sectors_override": a.sectors_override,
            "countries_override": a.countries_override,
        }
        for a in assets_list
    }
    accs_result = await db.execute(select(AccModel).where(AccModel.user_id == current_user.id))
    accs = accs_result.scalars().all()
    account_values: dict[str, float] = {}
    for acc in accs:
        acc_txs = [t for t in transactions if t.account_id == acc.id]
        acc_pos = calculate_positions(acc_txs)
        v = sum(pos.quantity * price_eur[aid] for aid, pos in acc_pos.items() if aid in price_eur)
        if v > 0:
            account_values[acc.name] = v
    allocation = calculate_allocation(positions_map, asset_info, price_eur, account_values)

    return compute_xray(
        positions=positions_out,
        allocation=allocation,
        transactions=transactions,
        total_value=total_value,
    )


@router.post("/backfill-history", status_code=202)
async def backfill_history(
    current_user: User = Depends(get_current_user),
):
    """Avvia in background il download storico prezzi per tutti gli asset detenuti."""
    from app.tasks.prices import backfill_portfolio_history
    backfill_portfolio_history.delay(current_user.id)
    return {"detail": "Backfill avviato in background"}
