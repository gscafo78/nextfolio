"""
Performance e rischio su serie sintetiche a rendimento noto.

Convenzione dei flussi (performance.compute_performance): acquisti a inizio
giornata, vendite e proventi a fine giornata. Con acquisti eseguiti al close
precedente e vendite al close del giorno, il rendimento del portafoglio deve
coincidere esattamente con quello del titolo, con o senza versamenti.
"""
import itertools
import math
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.transaction import TransactionType as TT
from app.services.portfolio.performance import compute_performance
from app.services.portfolio.risk import compute_risk_metrics

TODAY = date(2026, 6, 30)
_ids = itertools.count(1)


def _tx(asset_id, kind, d, qty, price, fee=0.0):
    return SimpleNamespace(id=next(_ids), asset_id=asset_id, type=kind, date=d,
                           quantity=qty, price=price, exchange_rate=1.0, fee=fee)


def _weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


# Rendimenti giornalieri noti: +1%, −0,5%, +0,3%, −0,8%, +0,6% ripetuti
PATTERN = [0.01, -0.005, 0.003, -0.008, 0.006]
DAYS = _weekdays(date(2025, 1, 6), 260)
CLOSES = [100.0]
for i in range(1, len(DAYS)):
    CLOSES.append(CLOSES[-1] * (1 + PATTERN[i % len(PATTERN)]))
PRICES = {1: dict(zip(DAYS, CLOSES))}
ASSET_TWRR = (CLOSES[-1] / CLOSES[0] - 1) * 100


def _buy_at_prev_close(i, qty):
    """Acquisto nel giorno i al close del giorno precedente."""
    return _tx(1, TT.BUY, DAYS[i], qty, CLOSES[i - 1])


def _perf(txs, prices=PRICES, period="max"):
    return compute_performance(txs, prices, period, today=TODAY)


SINGLE = [_tx(1, TT.BUY, DAYS[0], 100, CLOSES[0])]
WITH_DEPOSITS = [
    _tx(1, TT.BUY, DAYS[0], 5, CLOSES[0]),          # inizio con poco capitale
    _buy_at_prev_close(40, 50),                      # versamento grande
    _buy_at_prev_close(120, 200),
    _tx(1, TT.SELL, DAYS[180], 100, CLOSES[180]),    # disinvestimento al close
    _buy_at_prev_close(200, 30),
]


# ── TWRR ──────────────────────────────────────────────────────────────────────

def test_twrr_matches_asset_return_without_flows():
    assert _perf(SINGLE).twrr_pct == pytest.approx(ASSET_TWRR, abs=0.01)


def test_twrr_identical_with_and_without_deposits():
    assert _perf(WITH_DEPOSITS).twrr_pct == pytest.approx(_perf(SINGLE).twrr_pct, abs=0.01)


def test_daily_returns_equal_asset_returns_on_flow_days():
    p = _perf(WITH_DEPOSITS)
    by_date = {pt.date: pt.daily_return_pct for pt in p.series}
    for i in (40, 120, 180, 200):
        expected = (CLOSES[i] / CLOSES[i - 1] - 1) * 100
        assert by_date[DAYS[i]] == pytest.approx(expected, abs=1e-6)


def test_flow_on_day_without_prices_is_not_a_return():
    """Acquisto di sabato (nessun prezzo): il lunedì non deve mostrare un balzo."""
    friday = next(d for d in DAYS[50:] if d.weekday() == 4)
    i = DAYS.index(friday)
    saturday = friday + timedelta(days=1)
    txs = SINGLE + [_tx(1, TT.BUY, saturday, 400, CLOSES[i])]
    monday = DAYS[i + 1]
    r = {pt.date: pt.daily_return_pct for pt in _perf(txs).series}[monday]
    assert r == pytest.approx((CLOSES[i + 1] / CLOSES[i] - 1) * 100, abs=1e-6)
    assert _perf(txs).twrr_pct == pytest.approx(ASSET_TWRR, abs=0.01)


def test_income_counts_as_return():
    """Una cedola del 1% del valore aggiunge ~1% al TWRR (total return)."""
    i = 100
    value = 100 * CLOSES[i]
    txs = SINGLE + [_tx(1, TT.COUPON, DAYS[i], 1, value * 0.01)]
    p = _perf(txs)
    assert p.twrr_pct == pytest.approx(((1 + ASSET_TWRR / 100) * 1.01 - 1) * 100, abs=0.01)
    assert p.income_eur == pytest.approx(value * 0.01, abs=0.01)


def test_price_history_not_multiplied_by_tx_fx():
    """Lo storico è già in EUR: un acquisto in USD non va riconvertito."""
    tx = _tx(1, TT.BUY, DAYS[0], 100, CLOSES[0] / 0.9)
    tx.exchange_rate = 0.9
    tx.price_currency = "USD"
    p = _perf([tx])
    assert p.series[-1].value_eur == pytest.approx(100 * CLOSES[-1], rel=1e-6)


# ── Giorni di borsa ───────────────────────────────────────────────────────────

def test_weekends_from_small_crypto_are_not_trading_days():
    btc_days = [DAYS[0] + timedelta(days=k) for k in range((DAYS[-1] - DAYS[0]).days + 1)]
    prices = {**PRICES, 2: {d: 50000.0 for d in btc_days}}   # prezzo piatto, anche nel weekend
    txs = SINGLE + [_tx(2, TT.BUY, DAYS[0], 0.001, 50000.0)]  # 50 € su ~10.000 €
    p = _perf(txs, prices)
    assert all(pt.date.weekday() < 5 for pt in p.series)
    assert len(p.series) == len(DAYS)


# ── Statistiche per periodo ───────────────────────────────────────────────────

def test_period_pnl_and_invested_are_period_specific():
    txs = SINGLE + [_buy_at_prev_close(240, 10)]
    one_month = _perf(txs, period="1m")
    full = _perf(txs, period="max")
    assert one_month.start_value_eur != full.start_value_eur
    assert one_month.pnl_eur == pytest.approx(
        one_month.end_value_eur - one_month.start_value_eur - one_month.net_flows_eur + one_month.income_eur, abs=0.02)
    assert one_month.invested_eur == pytest.approx(one_month.start_value_eur + one_month.net_flows_eur, abs=0.02)
    assert one_month.pnl_eur != pytest.approx(full.pnl_eur, abs=1)


def test_3y_truncated_when_history_shorter():
    p = _perf(SINGLE, period="3y")
    assert p.history_truncated is True
    assert p.start_date == DAYS[0]
    assert _perf(SINGLE, period="max").history_truncated is False


def test_annualized_only_for_one_year_or_more():
    assert _perf(SINGLE, period="3m").twrr_annualized_pct is None
    assert _perf(SINGLE, period="max").twrr_annualized_pct is not None


# ── Rischio ───────────────────────────────────────────────────────────────────

def _expected_vol():
    rets = [CLOSES[i] / CLOSES[i - 1] - 1 for i in range(1, len(CLOSES))]
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    return sd * math.sqrt(252) * 100, rets


def test_volatility_matches_asset_and_ignores_deposits():
    vol, rets = _expected_vol()
    r1 = compute_risk_metrics("max", _perf(SINGLE).series)
    r2 = compute_risk_metrics("max", _perf(WITH_DEPOSITS).series)
    assert r1.annualized_volatility_pct == pytest.approx(vol, abs=0.05)
    assert r2.annualized_volatility_pct == pytest.approx(vol, abs=0.05)
    assert r2.best_day_pct == pytest.approx(max(rets) * 100, abs=0.01)
    assert r2.positive_days_pct == pytest.approx(r1.positive_days_pct, abs=0.5)
    assert r2.warnings == r1.warnings == []


def test_small_initial_base_excluded_from_risk():
    """Prima settimana con 5 € investiti: esclusa dalle metriche, ma non dal TWRR."""
    txs = [_tx(1, TT.BUY, DAYS[0], 0.05, CLOSES[0]), _buy_at_prev_close(10, 100)]
    p = _perf(txs)
    assert not all(pt.reliable for pt in p.series)
    risk = compute_risk_metrics("max", p.series)
    assert risk.trading_days < len(p.series)
    assert any("esclusi" in w for w in risk.warnings)


def test_sanity_warnings_on_implausible_series():
    prices = {1: dict(PRICES[1])}
    prices[1][DAYS[100]] = CLOSES[100] * 1.5       # spike +50%
    risk = compute_risk_metrics("max", _perf(SINGLE, prices).series)
    assert any("Dati sospetti" in w for w in risk.warnings)


def test_risk_free_lowers_sharpe():
    s = _perf(SINGLE).series
    assert compute_risk_metrics("max", s, 0.03).sharpe_ratio < compute_risk_metrics("max", s, 0.0).sharpe_ratio


def test_drawdown_on_twrr_index_not_on_value():
    """Una vendita del 90% non è un drawdown."""
    txs = SINGLE + [_tx(1, TT.SELL, DAYS[100], 90, CLOSES[100])]
    r = compute_risk_metrics("max", _perf(txs).series)
    assert r.max_drawdown_pct == pytest.approx(compute_risk_metrics("max", _perf(SINGLE).series).max_drawdown_pct, abs=0.01)
