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
import math
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


def _resolve_period(period: str, earliest_tx: date) -> tuple[date, date]:
    """Returns (start_date, end_date) for the given period string."""
    today = date.today()
    end = today

    if period == "today":
        return today, today
    if period == "wtd":
        return today - timedelta(days=today.weekday()), today
    if period == "mtd":
        return today.replace(day=1), today
    if period == "ytd":
        return today.replace(month=1, day=1), today
    if period == "max":
        return earliest_tx, today
    if period.isdigit() and len(period) == 4:
        year = int(period)
        start = date(year, 1, 1)
        end = date(year, 12, 31) if year < today.year else today
        return max(start, earliest_tx), end

    days = _PERIOD_DAYS.get(period)
    start = (today - timedelta(days=days)) if days else earliest_tx
    return max(start, earliest_tx), today


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
    earliest_tx = min(tx.date for tx in transactions)
    start_date, end_date = _resolve_period(period, earliest_tx)

    asset_ids = list({tx.asset_id for tx in transactions})

    # Fetch a 30-day lookback so _last_price_on_or_before can fill in assets
    # whose price history starts a few days after the period start.
    fetch_from = start_date - timedelta(days=30)
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date >= fetch_from,
            PriceHistory.date <= end_date,
        )
        .order_by(PriceHistory.date)
    )
    history_rows = result.scalars().all()

    # price_map[asset_id][date] = close
    # (NaN difensivo: la barra del giorno corrente non ancora chiusa può arrivare
    # come NaN da alcune fonti dati; va trattata come "nessun prezzo", non usata)
    price_map: dict[int, dict[date, float]] = {}
    for row in history_rows:
        if row.close is None or math.isnan(row.close):
            continue
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

    # Serie di date dalla price_history (solo giorni nel periodo richiesto con almeno un prezzo)
    all_dates = sorted({row.date for row in history_rows if row.date >= start_date})
    if not all_dates:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[])

    # Cash flow per asset per giorno — usato nel loop per calcolare TWRR
    # (filtrato per asset_id così possiamo escludere gli asset senza prezzo in quel giorno)
    daily_cf_by_asset: dict[int, dict[date, float]] = {}
    for tx in transactions:
        if tx.type == TransactionType.BUY:
            cf = tx.quantity * tx.price * tx.exchange_rate + tx.fee
        elif tx.type == TransactionType.SELL:
            cf = -(tx.quantity * tx.price * tx.exchange_rate - tx.fee)
        else:
            continue
        daily_cf_by_asset.setdefault(tx.asset_id, {})
        daily_cf_by_asset[tx.asset_id][tx.date] = (
            daily_cf_by_asset[tx.asset_id].get(tx.date, 0.0) + cf
        )

    series: list[PerformancePoint] = []
    prev_value: float = 0.0
    running_twrr: float = 1.0

    for d in all_dates:
        txs_up_to = [tx for tx in transactions if tx.date <= d]
        # include_closed=True: una posizione venduta per intero deve comunque contare
        # il proprio cash flow nel giorno della vendita (altrimenti il suo valore sparisce
        # da `value` senza che il corrispondente incasso compensi `start_value`, generando
        # una "perdita" fittizia pari all'intera posizione chiusa quel giorno).
        positions = calculate_positions(txs_up_to, include_closed=True)

        value = 0.0
        priced_ids: set[int] = set()
        for asset_id, pos in positions.items():
            if pos.quantity > 1e-6:
                close = _last_price_on_or_before(price_map.get(asset_id, {}), d)
                if close is not None:
                    fx = avg_fx.get(asset_id, 1.0)
                    value += pos.quantity * close * fx
                else:
                    # Nessuno storico prezzi disponibile per questo asset (fonte dati priva
                    # di OHLCV, es. ISIN scarsamente scambiato): usa il costo di carico come
                    # stima, invece di escludere silenziosamente la posizione dal periodo.
                    value += pos.quantity * pos.pmc_eur
            priced_ids.add(asset_id)

        # TWRR: solo il cash flow degli asset priced oggi, coerente con value
        cf_today = sum(
            daily_cf_by_asset.get(aid, {}).get(d, 0.0) for aid in priced_ids
        )
        start_value = prev_value + cf_today
        if start_value > 0:
            running_twrr *= value / start_value
        prev_value = value

        # Capitale investito netto: conta solo gli asset per cui abbiamo un valore (reale
        # o stimato al costo), così pnl_eur resta sempre coerente con value_eur.
        invested = sum(
            tx.quantity * tx.price * tx.exchange_rate + tx.fee
            for tx in txs_up_to
            if tx.type == TransactionType.BUY and tx.asset_id in priced_ids
        ) - sum(
            tx.quantity * tx.price * tx.exchange_rate - tx.fee
            for tx in txs_up_to
            if tx.type == TransactionType.SELL and tx.asset_id in priced_ids
        )

        series.append(PerformancePoint(
            date=d,
            value_eur=round(value, 2),
            invested_eur=round(max(invested, 0.0), 2),
            pnl_eur=round(value - max(invested, 0.0), 2),
            twrr_pct=round((running_twrr - 1.0) * 100, 4),
        ))

    twrr_pct = (running_twrr - 1.0) * 100

    return PerformanceOut(period=period, twrr_pct=round(twrr_pct, 2), series=series)
