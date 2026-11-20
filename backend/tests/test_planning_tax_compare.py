"""Pianificazione fiscale, confronto titoli e backtest (funzioni pure, dati sintetici)."""
import datetime
import itertools
from types import SimpleNamespace

import pytest

from app.models.transaction import TransactionType as TT
from app.services.planning.compare import backtest, compare, holdings_overlap
from app.services.planning.tax_planning import Sale, simulate_sales, tax_overview

TODAY = datetime.date(2026, 11, 20)
_ids = itertools.count(1)
DECL = SimpleNamespace(id=1, name="Broker", is_sostituto_imposta=False, is_foreign=True)


def _asset(aid, type_="STOCK", name="Azione"):
    return SimpleNamespace(id=aid, type=type_, name=name, symbol=name[:6], isin=None, govt_bond_override=None,
                           govt_bond_share=None)


STOCK = _asset(1, "STOCK", "Enel")
ETF = _asset(2, "ETF", "World ETF")
LOSER = _asset(3, "STOCK", "Perdente")


def _tx(asset, kind, d, qty, price):
    return SimpleNamespace(id=next(_ids), account=DECL, account_id=DECL.id, asset=asset, asset_id=asset.id, type=kind,
                           date=datetime.date.fromisoformat(d), quantity=qty, price=price, exchange_rate=1.0, fee=0.0,
                           price_currency="EUR")


# ── Fisco ─────────────────────────────────────────────────────────────────────

def _history():
    return [
        # minusvalenza 2022 di 1.000 € (scade a fine 2026)
        _tx(LOSER, TT.BUY, "2022-01-10", 100, 20), _tx(LOSER, TT.SELL, "2022-06-10", 100, 10),
        _tx(STOCK, TT.BUY, "2024-01-10", 100, 10),     # +500 latenti a 15 €
        _tx(ETF, TT.BUY, "2024-01-10", 10, 100),        # +500 latenti a 150 € (ETF: non compensabile)
    ]


def test_expiring_losses_and_use_suggestion_excludes_etf():
    o = tax_overview(_history(), {1: 15.0, 2: 150.0}, today=TODAY)
    assert o.expiring_standard == pytest.approx(1000)
    assert o.pool_standard[0]["expiring"] is True
    names = {s["name"] for s in o.use_losses}
    assert names == {"Enel"}                       # l'ETF non usa lo zainetto
    s = o.use_losses[0]
    assert s["quantity"] == pytest.approx(100)     # tutta la plus (500 €) per assorbire parte dei 1.000 €
    assert s["losses_used_eur"] == pytest.approx(500)
    assert s["tax_saved_eur"] == pytest.approx(130)


def test_no_expiring_losses_no_suggestion():
    o = tax_overview(_history(), {1: 15.0, 2: 150.0}, today=datetime.date(2025, 6, 1))
    assert o.expiring_standard == 0 and o.use_losses == []


def test_harvest_losses_to_offset_realized_gains():
    txs = [_tx(STOCK, TT.BUY, "2026-01-10", 100, 10), _tx(STOCK, TT.SELL, "2026-03-10", 100, 20),   # +1.000 realizzati
           _tx(LOSER, TT.BUY, "2026-02-10", 100, 30)]                                                 # −10 €/quota latenti
    o = tax_overview(txs, {3: 20.0}, today=TODAY)
    h = o.harvest_losses[0]
    assert h["name"] == "Perdente" and h["quantity"] == pytest.approx(100)
    assert h["gains_offset_eur"] == pytest.approx(1000) and h["tax_saved_eur"] == pytest.approx(260)
    assert o.year_tax["capital_gains_tax_eur"] == pytest.approx(260)


def test_simulate_sales_before_after():
    r = simulate_sales(_history(), [Sale(asset_id=1, quantity=100, price_eur=15.0, account=DECL),
                                    Sale(asset_id=2, quantity=10, price_eur=150.0, account=DECL)], today=TODAY)
    assert r["before"]["total_tax_eur"] == 0
    # azione: +500 assorbiti dallo zainetto; ETF: +500 tassati al 26%
    assert r["after"]["carryforward_used_eur"] == pytest.approx(500)
    assert r["after"]["total_tax_eur"] == pytest.approx(130)
    assert r["delta_tax_eur"] == pytest.approx(130)
    assert {x["name"]: x["category"] for x in r["sales"]} == {"Enel": "standard", "World ETF": "fund"}


# ── Confronto ─────────────────────────────────────────────────────────────────

def _series(start, n, growth, every=1):
    return [{"date": (start + datetime.timedelta(days=i)).isoformat(), "close": 100 * (1 + growth) ** (i / 365)}
            for i in range(0, n, every)]


def test_compare_common_window_and_correlation():
    a = _series(datetime.date(2020, 1, 1), 365 * 4, 0.10)
    b = _series(datetime.date(2021, 1, 1), 365 * 3, 0.05)
    r = compare({"a": a, "b": b})
    assert r["start"] == "2021-01-01"
    assert r["normalized"]["a"][0] == 100 and r["normalized"]["b"][0] == 100
    assert r["metrics"]["a"]["window_ann_return_pct"] == pytest.approx(10, abs=0.1)
    assert r["metrics"]["b"]["window_ann_return_pct"] == pytest.approx(5, abs=0.1)
    assert r["correlation"]["a"]["a"] == pytest.approx(1.0)


def test_holdings_overlap():
    a = [{"name": "Apple Inc.", "weight": 0.05}, {"name": "Microsoft Corp", "weight": 0.04}, {"name": "Nestle SA", "weight": 0.01}]
    b = [{"name": "APPLE INC", "weight": 0.06}, {"name": "Microsoft Corporation", "weight": 0.02}]
    o = holdings_overlap(a, b)
    assert o["overlap_pct"] == pytest.approx(7.0)
    assert [c["name"] for c in o["common"]] == ["apple", "microsoft"]


# ── Backtest ──────────────────────────────────────────────────────────────────

def test_backtest_single_asset_known_return():
    s = _series(datetime.date(2020, 1, 1), 365 * 5 + 2, 0.08)
    r = backtest({"x": s}, {"x": 100}, initial=10_000)
    assert r["metrics"]["twrr_ann_pct"] == pytest.approx(8, abs=0.2)
    assert r["metrics"]["final_value"] == pytest.approx(10_000 * 1.08 ** ((datetime.date.fromisoformat(r["metrics"]["end"]) - datetime.date.fromisoformat(r["metrics"]["start"])).days / 365), rel=0.01)
    assert r["metrics"]["max_drawdown_pct"] == pytest.approx(0)


def test_backtest_contributions_do_not_change_twrr():
    s = _series(datetime.date(2020, 1, 1), 365 * 5 + 2, 0.08)
    plain = backtest({"x": s}, {"x": 1}, initial=10_000)
    with_pac = backtest({"x": s}, {"x": 1}, initial=10_000, monthly=500)
    assert with_pac["metrics"]["twrr_pct"] == pytest.approx(plain["metrics"]["twrr_pct"], abs=0.01)
    assert with_pac["metrics"]["invested"] == pytest.approx(10_000 + 500 * (len(with_pac["series"]) - 1))


def test_backtest_rebalancing_keeps_weights():
    a = _series(datetime.date(2020, 1, 1), 365 * 4, 0.20)
    b = _series(datetime.date(2020, 1, 1), 365 * 4, 0.00)
    no = backtest({"a": a, "b": b}, {"a": 50, "b": 50}, rebalance="none")
    yearly = backtest({"a": a, "b": b}, {"a": 50, "b": 50}, rebalance="annual")
    assert yearly["metrics"]["rebalances"] == 3 and no["metrics"]["rebalances"] == 0
    # con un titolo che cresce sempre, il ribilanciamento rende meno del lasciar correre
    assert yearly["metrics"]["final_value"] < no["metrics"]["final_value"]


def test_backtest_short_history_warns():
    s = _series(datetime.date(2025, 1, 1), 400, 0.05)
    assert backtest({"x": s}, {"x": 1})["warnings"]
