"""Versamento intelligente, scostamento, proiezione Monte Carlo e FIRE (funzioni pure)."""
import math

import pytest

from app.services.planning.contribution import Instrument, drift, plan_contribution
from app.services.planning.projection import (
    fire,
    portfolio_assumptions,
    project_goal,
    required_monthly,
    simulate_paths,
)

EQ = [Instrument(name="World", price_eur=100.0, asset_id=1)]
BD = [Instrument(name="Govt", price_eur=50.0, symbol="X13G.DE")]


def _cls(plan):
    return {c["class"]: c for c in plan.per_class}


# ── Versamento ────────────────────────────────────────────────────────────────

def test_amount_smaller_than_deficit_goes_to_underweight_class():
    """80/20 obiettivo, portafoglio 100% azioni: tutto il versamento va alle obbligazioni."""
    plan = plan_contribution({"EQUITY": 10_000}, {"EQUITY": 0.8, "BOND": 0.2}, 1000, {"EQUITY": EQ, "BOND": BD})
    assert _cls(plan)["BOND"]["allocated_eur"] == pytest.approx(1000)
    assert _cls(plan)["EQUITY"]["allocated_eur"] == pytest.approx(0)
    assert [o.name for o in plan.orders] == ["Govt"] and plan.orders[0].quantity == 20


def test_amount_larger_than_deficits_spreads_rest_by_weights():
    plan = plan_contribution({"EQUITY": 8000, "BOND": 1000}, {"EQUITY": 0.8, "BOND": 0.2}, 2000,
                             {"EQUITY": EQ, "BOND": BD})
    # dopo: totale 11.000 → obiettivo azioni 8.800 (deficit 800), obbligazioni 2.200 (deficit 1.200): esatto
    assert _cls(plan)["EQUITY"]["allocated_eur"] == pytest.approx(800)
    assert _cls(plan)["BOND"]["allocated_eur"] == pytest.approx(1200)
    assert _cls(plan)["EQUITY"]["after_pct"] == pytest.approx(80.0)
    plan2 = plan_contribution({"EQUITY": 8000, "BOND": 2000}, {"EQUITY": 0.8, "BOND": 0.2}, 1000,
                              {"EQUITY": EQ, "BOND": BD})
    assert _cls(plan2)["EQUITY"]["allocated_eur"] == pytest.approx(800)     # già in equilibrio: secondo i pesi


def test_whole_units_and_min_order_leave_cash():
    plan = plan_contribution({"EQUITY": 10_000}, {"EQUITY": 0.5, "BOND": 0.5}, 130,
                             {"BOND": [Instrument(name="Costly", price_eur=60.0)]}, whole_units=True, min_order_eur=100)
    assert plan.orders[0].quantity == 2 and plan.orders[0].amount_eur == 120
    assert plan.uninvested_eur == pytest.approx(10)
    plan2 = plan_contribution({"EQUITY": 10_000}, {"EQUITY": 0.5, "BOND": 0.5}, 50,
                              {"BOND": [Instrument(name="Costly", price_eur=60.0)]}, whole_units=True)
    assert not plan2.orders and plan2.uninvested_eur == pytest.approx(50)


def test_fees_reduce_invested_amount():
    plan = plan_contribution({"EQUITY": 10_000}, {"EQUITY": 0.5, "BOND": 0.5}, 1000, {"BOND": BD},
                             whole_units=False, fee_per_order_eur=5)
    assert plan.orders[0].amount_eur == pytest.approx(995)


def test_from_cash_reduces_money_market():
    plan = plan_contribution({"EQUITY": 7000, "MONEY_MARKET": 3000}, {"EQUITY": 0.8, "BOND": 0.2}, 3000,
                             {"EQUITY": EQ, "BOND": BD}, from_cash=True, whole_units=False)
    c = _cls(plan)
    assert c["EQUITY"]["allocated_eur"] + c["BOND"]["allocated_eur"] == pytest.approx(3000)
    assert c["MONEY_MARKET"]["after_pct"] == pytest.approx(0, abs=0.01)
    assert c["EQUITY"]["after_pct"] == pytest.approx(80, abs=0.01)
    over = plan_contribution({"EQUITY": 7000, "MONEY_MARKET": 100}, {"EQUITY": 1.0}, 500, {"EQUITY": EQ},
                             from_cash=True)
    assert any("inferiore" in w for w in over.warnings)


def test_missing_instrument_warns():
    plan = plan_contribution({"EQUITY": 10_000}, {"EQUITY": 0.5, "BOND": 0.5}, 1000, {"EQUITY": EQ})
    assert any("Obbligazioni" in w for w in plan.warnings) and plan.uninvested_eur == pytest.approx(1000)


def test_drift_band():
    rows = {r["class"]: r for r in drift({"EQUITY": 9000, "BOND": 1000}, {"EQUITY": 0.7, "BOND": 0.3}, 5)}
    assert rows["EQUITY"]["delta_pct"] == pytest.approx(20) and rows["EQUITY"]["out_of_band"]
    assert not {r["class"]: r for r in drift({"EQUITY": 7200, "BOND": 2800}, {"EQUITY": 0.7, "BOND": 0.3}, 5)}["EQUITY"]["out_of_band"]


# ── Proiezione ────────────────────────────────────────────────────────────────

def test_zero_volatility_matches_deterministic_pac():
    mu, months, c, v0 = 0.07, 120, 300, 5000
    paths = simulate_paths(v0, c, months, mu, 0.0, n_paths=3)
    r = (1 + mu) ** (1 / 12) - 1
    expected = v0 * (1 + r) ** months + c * ((1 + r) ** months - 1) / r
    assert paths[0, -1] == pytest.approx(expected, rel=1e-9)


def test_monte_carlo_mean_matches_expected_return():
    paths = simulate_paths(1000, 0, 12, 0.07, 0.16, n_paths=20_000)
    assert paths[:, -1].mean() == pytest.approx(1070, rel=0.01)


def test_projection_probability_and_determinism():
    a = project_goal(10_000, 500, 120, 80_000, 0.06, 0.12, inflation=0.02)
    b = project_goal(10_000, 500, 120, 80_000, 0.06, 0.12, inflation=0.02)
    assert a.probability == b.probability                       # seed fisso
    assert 0 < a.probability < 1
    assert a.yearly[0]["p50"] == pytest.approx(10_000) and a.yearly[-1]["year"] == 10
    easy = project_goal(10_000, 0, 120, 1_000, 0.06, 0.12)
    assert easy.probability == 1.0 and easy.required_monthly_80 == 0.0


def test_required_monthly_reaches_probability():
    req = required_monthly(0, 120, 50_000, 0.05, 0.10, 0.02, 0.8)
    assert req is not None and req > 0
    assert project_goal(0, req, 120, 50_000, 0.05, 0.10, 0.02).probability >= 0.78


def test_portfolio_assumptions_weighting():
    mu, sigma = portfolio_assumptions({"EQUITY": 1.0})
    assert mu == pytest.approx(0.07) and sigma == pytest.approx(0.16)
    mu2, sigma2 = portfolio_assumptions({"EQUITY": 0.6, "BOND": 0.4})
    assert mu2 == pytest.approx(0.6 * 0.07 + 0.4 * 0.03)
    assert sigma2 < 0.6 * 0.16 + 0.4 * 0.06                     # diversificazione
    assert sigma2 == pytest.approx(math.sqrt((0.6 * 0.16) ** 2 + (0.4 * 0.06) ** 2 + 2 * 0.6 * 0.4 * 0.16 * 0.06 * 0.1))


def test_fire_target_and_success():
    f = fire(500_000, 0, 20_000, 0.04, 0.05, 0.0, inflation=0.0, horizon_years=30, n_paths=10)
    assert f.target_capital == 500_000
    assert f.years_to_fire_median == 0.0
    assert f.success_probability == 1.0                       # 5% senza volatilità > 4% di prelievo
    # rendimento zero: 500.000 € non bastano per 30 anni a 20.000 €/anno; sostenibile = 500.000 / 30
    bad = fire(100_000, 0, 20_000, 0.04, 0.0, 0.0, inflation=0.0, horizon_years=30, n_paths=10)
    assert bad.success_probability == 0.0
    assert bad.sustainable_withdrawal_90 == pytest.approx(500_000 / 30, rel=0.01)
    assert bad.years_to_fire_median is None
