"""
Serie temporale di performance del portafoglio.

Algoritmo (``compute_performance``, funzione pura e testabile):
1. Valore di apertura: posizioni detenute a fine giornata prima dell'inizio del
   periodo, valorizzate all'ultimo close disponibile.
2. Date di valutazione: solo i giorni in cui almeno metà del valore del
   portafoglio ha un prezzo *nuovo* (close di quel giorno). Weekend e festivi
   (es. giorni in cui quota solo una crypto) non diventano rendimenti nulli: la
   variazione viene attribuita alla data di valutazione successiva.
3. Rendimento giornaliero neutralizzato dai flussi, con tutti i flussi avvenuti
   dall'ultima data di valutazione (anche in giorni senza prezzi):

       r_t = (V_t + S_t + P_t) / (V_{t-1} + A_t) - 1

   A = acquisti (capitale entrato, a inizio giornata), S = vendite (capitale
   uscito, a fine giornata), P = proventi incassati (dividendi, cedole,
   interessi) al netto dei costi separati (FEE).
4. TWRR = prodotto dei (1 + r_t): identico con o senza versamenti e
   proventi inclusi (total return).
5. Rendimenti con base molto piccola (primi giorni) restano nel TWRR ma sono
   marcati come non affidabili e non entrano nelle metriche di rischio.

I prezzi in ``price_history`` sono già in EUR (conversione FX al salvataggio,
v1.9.2): non vanno moltiplicati per il cambio delle transazioni.
"""
import math
from dataclasses import dataclass
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

# Frazione minima del valore con prezzo "nuovo" perché un giorno sia di borsa
_FRESH_SHARE_MIN = 0.5
# Base minima (relativa al valore massimo della serie) per un rendimento affidabile
_MIN_BASE_FRACTION = 0.01
_MIN_BASE_EUR = 50.0


def _resolve_period_full(period: str, earliest_tx: date, today: date | None = None) -> tuple[date, date, date]:
    """(start effettivo, end, start richiesto)."""
    today = today or date.today()

    if period == "today":
        return today, today, today
    if period == "wtd":
        s = today - timedelta(days=today.weekday())
        return max(s, earliest_tx), today, s
    if period == "mtd":
        s = today.replace(day=1)
        return max(s, earliest_tx), today, s
    if period == "ytd":
        s = today.replace(month=1, day=1)
        return max(s, earliest_tx), today, s
    if period == "max":
        return earliest_tx, today, earliest_tx
    if period.isdigit() and len(period) == 4:
        year = int(period)
        s = date(year, 1, 1)
        end = date(year, 12, 31) if year < today.year else today
        return max(s, earliest_tx), end, s

    days = _PERIOD_DAYS.get(period)
    s = (today - timedelta(days=days)) if days else earliest_tx
    return max(s, earliest_tx), today, s


def _resolve_period(period: str, earliest_tx: date) -> tuple[date, date]:
    """(start, end) del periodo — compatibilità."""
    start, end, _ = _resolve_period_full(period, earliest_tx)
    return start, end


def _last_price_on_or_before(price_dict: dict[date, float], d: date) -> float | None:
    past = [k for k in price_dict if k <= d]
    return price_dict[max(past)] if past else None


def _amount(tx) -> float:
    return tx.quantity * tx.price * tx.exchange_rate


@dataclass
class _Flows:
    buys: float = 0.0     # capitale entrato (acquisti + commissioni)
    sells: float = 0.0    # capitale uscito (vendite al netto delle commissioni)
    income: float = 0.0   # proventi netti (dividendi, cedole, interessi) − costi FEE


def _flows_of(tx, f: _Flows) -> None:
    if tx.type == TransactionType.BUY:
        f.buys += _amount(tx) + tx.fee
    elif tx.type == TransactionType.SELL:
        f.sells += _amount(tx) - tx.fee
    elif tx.type in (TransactionType.DIVIDEND, TransactionType.COUPON, TransactionType.INTEREST):
        f.income += _amount(tx) - tx.fee
    elif tx.type == TransactionType.FEE:
        f.income -= _amount(tx) + tx.fee


class _PriceBook:
    """Ultimo close ≤ data, con ricerca incrementale per asset."""

    def __init__(self, price_map: dict[int, dict[date, float]]):
        self._dates = {aid: sorted(p) for aid, p in price_map.items()}
        self._prices = price_map

    def last(self, asset_id: int, d: date) -> float | None:
        ds = self._dates.get(asset_id)
        if not ds:
            return None
        # bisect manuale (liste piccole, evita import)
        lo, hi = 0, len(ds)
        while lo < hi:
            mid = (lo + hi) // 2
            if ds[mid] <= d:
                lo = mid + 1
            else:
                hi = mid
        return self._prices[asset_id][ds[lo - 1]] if lo else None

    def fresh(self, asset_id: int, d: date) -> bool:
        return d in self._prices.get(asset_id, {})


def _valuation(positions, book: _PriceBook, d: date) -> tuple[float, float]:
    """(valore, quota di valore con prezzo nuovo in data d)."""
    value = fresh_value = 0.0
    for asset_id, pos in positions.items():
        if pos.quantity <= 1e-9:
            continue
        close = book.last(asset_id, d)
        # senza storico: stima al costo di carico (non sparisce dal valore)
        v = pos.quantity * (close if close is not None else pos.pmc_eur)
        value += v
        if book.fresh(asset_id, d):
            fresh_value += v
    return value, (fresh_value / value if value > 0 else 0.0)


def compute_performance(
    transactions: list,
    price_map: dict[int, dict[date, float]],
    period: str = "1y",
    today: date | None = None,
) -> PerformanceOut:
    if not transactions:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[])

    today = today or date.today()
    txs = sorted(transactions, key=lambda t: (t.date, t.id))
    earliest_tx = txs[0].date
    start_date, end_date, requested_start = _resolve_period_full(period, earliest_tx, today)
    book = _PriceBook(price_map)

    # ── Apertura ─────────────────────────────────────────────────────────────
    before = [t for t in txs if t.date < start_date]
    open_positions = calculate_positions(before)
    open_value, _ = _valuation(open_positions, book, start_date - timedelta(days=1)) if before else (0.0, 0.0)

    # ── Date candidate: giorni con almeno un prezzo nel periodo + giorni con transazioni
    candidates = {d for p in price_map.values() for d in p if start_date <= d <= end_date}
    candidates |= {t.date for t in txs if start_date <= t.date <= end_date}
    if not candidates:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[], start_date=start_date,
                              end_date=end_date, start_value_eur=round(open_value, 2),
                              end_value_eur=round(open_value, 2), invested_eur=round(open_value, 2))

    period_txs = [t for t in txs if start_date <= t.date <= end_date]
    tx_idx = 0
    held_txs = list(before)

    prev_value = open_value
    running = 1.0
    cum = _Flows()
    pending = _Flows()
    raw_points: list[tuple] = []

    last_candidate = max(candidates)
    for d in sorted(candidates):
        while tx_idx < len(period_txs) and period_txs[tx_idx].date <= d:
            t = period_txs[tx_idx]
            _flows_of(t, pending)
            held_txs.append(t)
            tx_idx += 1

        positions = calculate_positions(held_txs, include_closed=True)
        value, fresh_share = _valuation(positions, book, d)

        # Giorno di valutazione: prezzi "nuovi" per almeno metà del valore.
        # Il primo giorno con valore (o l'ultimo del periodo) è sempre valutato.
        first_with_value = prev_value <= 0 and value > 0
        if not (fresh_share >= _FRESH_SHARE_MIN or first_with_value or d == last_candidate):
            continue

        base = prev_value + pending.buys
        r = None
        if base > 0:
            r = (value + pending.sells + pending.income) / base - 1.0
            running *= 1.0 + r

        cum.buys += pending.buys
        cum.sells += pending.sells
        cum.income += pending.income
        raw_points.append((d, value, base, r, pending.buys - pending.sells, pending.income))
        pending = _Flows()
        prev_value = value

    # ── Serie ────────────────────────────────────────────────────────────────
    max_value = max((p[1] for p in raw_points), default=0.0)
    min_base = max(_MIN_BASE_EUR, max_value * _MIN_BASE_FRACTION)

    series: list[PerformancePoint] = []
    chain = 1.0
    net_flows = income = 0.0
    for d, value, base, r, flow, inc in raw_points:
        if r is not None:
            chain *= 1.0 + r
        net_flows += flow
        income += inc
        invested = open_value + net_flows
        series.append(PerformancePoint(
            date=d,
            value_eur=round(value, 2),
            invested_eur=round(max(invested, 0.0), 2),
            pnl_eur=round(value - invested + income, 2),
            twrr_pct=round((chain - 1.0) * 100, 4),
            daily_return_pct=round(r * 100, 6) if r is not None else None,
            reliable=bool(r is not None and base >= min_base),
            flow_eur=round(flow, 2),
            income_eur=round(inc, 2),
        ))

    end_value = series[-1].value_eur if series else open_value
    actual_start = series[0].date if series else start_date
    days = (end_date - (start_date - timedelta(days=1) if before else actual_start)).days
    twrr = (running - 1.0) * 100
    twrr_ann = None
    if days >= 365 and running > 0:
        twrr_ann = round((running ** (365.0 / days) - 1.0) * 100, 2)

    return PerformanceOut(
        period=period,
        twrr_pct=round(twrr, 2),
        series=series,
        start_date=actual_start,
        end_date=end_date,
        requested_start_date=requested_start,
        history_truncated=requested_start < earliest_tx and period != "max",
        days=days,
        start_value_eur=round(open_value, 2),
        end_value_eur=round(end_value, 2),
        net_flows_eur=round(net_flows, 2),
        income_eur=round(income, 2),
        invested_eur=round(open_value + net_flows, 2),
        pnl_eur=round(end_value - open_value - net_flows + income, 2),
        twrr_annualized_pct=twrr_ann,
    )


async def get_portfolio_performance(
    db: AsyncSession,
    transactions: list[Transaction],
    period: str = "1y",
) -> PerformanceOut:
    if not transactions:
        return PerformanceOut(period=period, twrr_pct=0.0, series=[])

    earliest_tx = min(tx.date for tx in transactions)
    start_date, end_date, _ = _resolve_period_full(period, earliest_tx)
    asset_ids = list({tx.asset_id for tx in transactions})

    # 30 giorni di lookback: valore di apertura e asset con storico che parte dopo
    fetch_from = start_date - timedelta(days=30)
    result = await db.execute(
        select(PriceHistory.asset_id, PriceHistory.date, PriceHistory.close)
        .where(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date >= fetch_from,
            PriceHistory.date <= end_date,
        )
    )
    price_map: dict[int, dict[date, float]] = {}
    for asset_id, d, close in result.all():
        # NaN difensivo: la barra del giorno non ancora chiusa può arrivare come NaN
        if close is None or math.isnan(close):
            continue
        price_map.setdefault(asset_id, {})[d] = close

    return compute_performance(transactions, price_map, period)
