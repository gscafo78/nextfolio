"""
Calcolo della serie temporale di performance del portafoglio.

Algoritmo:
1. Carica la price_history dal DB per tutti gli asset del portafoglio nel periodo.
2. Per ogni giorno della serie, ricalcola le posizioni FIFO fino a quel giorno
   e le valorizza con il close di quel giorno.
3. Per asset non-EUR usa come tasso di cambio la media dei tassi storici
   delle transazioni (approssimazione accettabile per MVP).
4. Calcola il TWRR come prodotto dei sub-return giornalieri.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.schemas.portfolio import PerformanceOut, PerformancePoint
from app.services.portfolio.positions import calculate_positions

_PERIOD_DAYS: dict[str, int | None] = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "3y": 365 * 3,
    "max": None,
}


def _last_price_on_or_before(price_dict: dict[date, float], d: date) -> float | None:
    past = [(k, v) for k, v in price_dict.items() if k <= d]
    if not past:
        return None
    return max(past, key=lambda x: x[0])[1]


async def get_portfolio_performance(
    db: AsyncSession,
    transactions: list[Transaction],
    period: str = "1y",
) -> PerformanceOut:
    if not transactions:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[])

    today = date.today()
    days = _PERIOD_DAYS.get(period)
    earliest_tx = min(tx.date for tx in transactions)
    start_date = max(
        (today - timedelta(days=days)) if days else date.min,
        earliest_tx,
    )

    asset_ids = list({tx.asset_id for tx in transactions})

    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date >= start_date,
            PriceHistory.date <= today,
        )
        .order_by(PriceHistory.date)
    )
    history_rows = result.scalars().all()

    # price_map[asset_id][date] = close
    price_map: dict[int, dict[date, float]] = {}
    for row in history_rows:
        price_map.setdefault(row.asset_id, {})[row.date] = row.close

    # FX: media dei tassi storici delle transazioni per asset non-EUR
    fx_map: dict[int, list[float]] = {}
    for tx in transactions:
        if tx.price_currency != "EUR":
            fx_map.setdefault(tx.asset_id, []).append(tx.exchange_rate)
    avg_fx: dict[int, float] = {
        aid: sum(rates) / len(rates)
        for aid, rates in fx_map.items()
    }

    # Serie di date dalla price_history (solo giorni con almeno un prezzo)
    all_dates = sorted({row.date for row in history_rows})
    if not all_dates:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[])

    series: list[PerformancePoint] = []
    prev_value: float | None = None
    sub_returns: list[float] = []

    for d in all_dates:
        txs_up_to = [tx for tx in transactions if tx.date <= d]
        positions = calculate_positions(txs_up_to)

        value = 0.0
        for asset_id, pos in positions.items():
            close = _last_price_on_or_before(price_map.get(asset_id, {}), d)
            if close is None:
                continue
            fx = avg_fx.get(asset_id, 1.0)
            value += pos.quantity * close * fx

        # Capitale investito netto fino a questo giorno
        invested = sum(
            tx.quantity * tx.price * tx.exchange_rate + tx.fee
            for tx in txs_up_to
            if tx.type == TransactionType.BUY
        ) - sum(
            tx.quantity * tx.price * tx.exchange_rate - tx.fee
            for tx in txs_up_to
            if tx.type == TransactionType.SELL
        )

        series.append(PerformancePoint(
            date=d,
            value_eur=round(value, 2),
            invested_eur=round(max(invested, 0.0), 2),
            pnl_eur=round(value - max(invested, 0.0), 2),
        ))

        if prev_value is not None and prev_value > 0:
            sub_returns.append(value / prev_value)
        prev_value = value if value > 0 else prev_value

    # TWRR = prodotto dei sub-return giornalieri - 1
    twrr = 1.0
    for r in sub_returns:
        twrr *= r
    twrr_pct = (twrr - 1.0) * 100 if sub_returns else 0.0

    return PerformanceOut(period=period, twrr_pct=round(twrr_pct, 2), series=series)
