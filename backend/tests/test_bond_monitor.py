"""Monitoraggio convenienza vendita delle obbligazioni — funzioni pure (senza DB)."""
import datetime as dt

import pytest
from dateutil.relativedelta import relativedelta

from app.services.bonds.monitor import (
    accrued_per_unit,
    break_even_price,
    evaluate_bond,
    next_notification_state,
)

TODAY = dt.date(2026, 11, 20)
MATURITY = dt.date(2031, 11, 15)


def _coupons(first=dt.date(2027, 5, 15), months=6, end=MATURITY):
    out, d = [], first
    while d <= end:
        out.append(d)
        d += relativedelta(months=months)
    return out


def _eval(price, **kw):
    base = dict(quantity=10, avg_cost=94.0, price=price, face_value=100.0, coupon_per_unit=1.25,
                future_coupon_dates=_coupons(), prev_coupon_date=dt.date(2026, 11, 15),
                collected_coupons_gross=10 * 1.25 * 5, tax_rate=0.0, maturity_date=MATURITY, today=TODAY)
    base.update(kw)
    return evaluate_bond(**base)


# ── Esempio dell'utente: comprato a 94, rimborso 100, 5 cedole al 2,5% incassate, prezzo 120 ──

def test_price_120_beats_holding_to_maturity():
    e = _eval(120.0)
    assert e.status == "ok" and e.should_sell is True
    assert e.advantage_eur > 0 and e.future_coupons == 10


def test_price_99_does_not_beat_holding():
    e = _eval(99.0)
    assert e.should_sell is False and e.advantage_eur < 0


def test_gross_numbers_match_hand_calculation():
    e = _eval(120.0)                      # lordo (tax 0): rateo 1,25·5/181 giorni ≈ 0,0345 per quota
    accr = 1.25 * 5 / (dt.date(2027, 5, 15) - dt.date(2026, 11, 15)).days
    assert e.sell_gross_eur == pytest.approx(10 * (120 + accr))
    assert e.hold_net_eur == pytest.approx(10 * 100 + 10 * 1.25 * 10)          # rimborso + 10 cedole future
    assert e.collected_coupons_net_eur == pytest.approx(62.5)
    assert e.total_gain_sell_eur == pytest.approx(10 * (120 + accr) + 62.5 - 940)
    assert e.total_gain_hold_eur == pytest.approx(1000 + 125 + 62.5 - 940)


def test_without_future_coupons_in_comparison_would_wrongly_sell():
    """Con 10 cedole ancora da incassare tenere a 110 conviene più di vendere (vale anche con tasse)."""
    assert _eval(110.0, tax_rate=0.125).should_sell is False


# ── Prezzo di pareggio ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tax", [0.0, 0.125, 0.26])
@pytest.mark.parametrize("cost", [94.0, 105.0])
def test_advantage_is_zero_at_break_even_price(tax, cost):
    e = _eval(100.0, tax_rate=tax, avg_cost=cost)
    at_be = _eval(e.break_even_price, tax_rate=tax, avg_cost=cost)
    assert at_be.advantage_eur == pytest.approx(0, abs=1e-6)
    assert _eval(e.break_even_price + 1, tax_rate=tax, avg_cost=cost).should_sell is True
    assert _eval(e.break_even_price - 1, tax_rate=tax, avg_cost=cost).should_sell is False


def test_break_even_helper_branches():
    # costo basso: al prezzo di pareggio c'è plusvalenza tassata → (150 − 0,26·130) / 0,74
    assert break_even_price(1, 130.0, 0.0, 0.26, 150.0) == pytest.approx((150 - 0.26 * 130) / 0.74)
    # costo alto (160): a quel prezzo non c'è plusvalenza → nessuna imposta di capitale
    assert break_even_price(1, 160.0, 0.0, 0.26, 150.0) == pytest.approx(150.0)


# ── Imposte e rateo ───────────────────────────────────────────────────────────

def test_taxes_reduce_both_sides_and_26_vs_125():
    g = _eval(120.0, tax_rate=0.0)
    t125 = _eval(120.0, tax_rate=0.125)
    t26 = _eval(120.0, tax_rate=0.26)
    assert t125.sell_net_eur < g.sell_net_eur and t125.hold_net_eur < g.hold_net_eur
    assert t26.sell_net_eur < t125.sell_net_eur
    assert t125.sell_tax_eur == pytest.approx(0.125 * (10 * (120 - 94) + 10 * t125.accrued_per_unit))
    assert t125.collected_coupons_net_eur == pytest.approx(62.5 * 0.875)


def test_no_tax_on_capital_loss():
    e = _eval(90.0, avg_cost=100.0, tax_rate=0.26)
    assert e.sell_tax_eur == pytest.approx(0.26 * 10 * e.accrued_per_unit)    # solo sul rateo
    assert e.hold_tax_eur == pytest.approx(0.26 * 10 * 1.25 * 10)             # a scadenza 100 − 100 = 0 di guadagno


def test_accrued_interest_actual_actual():
    assert accrued_per_unit(1.25, dt.date(2026, 11, 15), dt.date(2027, 5, 15), dt.date(2026, 11, 15)) == 0
    half = dt.date(2026, 11, 15) + dt.timedelta(days=(dt.date(2027, 5, 15) - dt.date(2026, 11, 15)).days // 2)
    assert accrued_per_unit(1.25, dt.date(2026, 11, 15), dt.date(2027, 5, 15), half) == pytest.approx(0.625, abs=0.01)
    assert accrued_per_unit(1.25, dt.date(2026, 11, 15), dt.date(2027, 5, 15), dt.date(2028, 1, 1)) == pytest.approx(1.25)


def test_fewer_future_coupons_lowers_hold_value():
    near = _eval(100.0, future_coupon_dates=_coupons(end=dt.date(2028, 5, 15)), maturity_date=dt.date(2028, 5, 15))
    far = _eval(100.0)
    assert near.future_coupons == 3 and far.future_coupons == 10
    assert near.hold_net_eur < far.hold_net_eur


# ── Casi limite ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kw,reason", [
    (dict(quantity=0.0), "Nessuna posizione aperta"),
    (dict(maturity_date=None), "Scadenza"),
    (dict(maturity_date=dt.date(2026, 11, 1)), "scaduto"),
    (dict(coupon_per_unit=0.0), "Cedole non configurate"),
])
def test_missing_data(kw, reason):
    e = _eval(100.0, **kw)
    assert e.status == "missing_data" and reason in e.reason and e.should_sell is False


# ── Macchina a stati dell'email ───────────────────────────────────────────────

def test_email_once_then_rearm_after_condition_clears():
    active, sent = False, []
    for should_sell in (False, True, True, True, False, True, True):
        send, active = next_notification_state(should_sell, active)
        sent.append(send)
    assert sent == [False, True, False, False, False, True, False]


def test_missing_price():
    e = _eval(0.0)
    assert e.status == "missing_data" and "Prezzo corrente non disponibile" in e.reason
