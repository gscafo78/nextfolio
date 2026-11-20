"""Pagina Pianifica: ricerca Yahoo (mapping), metriche di prezzo, simulatore d'acquisto (senza DB)."""
import datetime
from types import SimpleNamespace

import pytest

from app.services.cash import CashBalance
from app.services.market_data import external
from app.services.planning.metrics import price_metrics
from app.services.planning.simulate import SimItem, simulate
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.positions import Lot, PositionCalc

WORLD = {"type": "ETF", "name": "iShares Core MSCI World UCITS ETF", "currency": "EUR", "symbol": "SWDA",
         "countries": [{"code": "US", "weight": 0.7}, {"code": "JP", "weight": 0.3}],
         "sectors": [{"name": "Technology", "weight": 1.0}]}
BOND_ETF = {"type": "ETF", "name": "Xtrackers II Eurozone Government Bond 1-3", "currency": "EUR",
            "countries": [{"code": "FR", "weight": 0.5}, {"code": "IT", "weight": 0.5}], "sectors": []}


# ── Ricerca Yahoo ─────────────────────────────────────────────────────────────

def test_map_yahoo_quote_types():
    etf = external.map_yahoo_quote({"symbol": "EUNL.DE", "shortname": "iShs Core MSCI World", "quoteType": "ETF",
                                    "exchange": "GER", "exchDisp": "XETRA"})
    assert etf["type"] == "ETF" and etf["exchange"] == "XETRA" and etf["ticker"] == "EUNL"
    assert external.map_yahoo_quote({"symbol": "AAPL", "longname": "Apple Inc.", "quoteType": "EQUITY",
                                     "exchange": "NMS"})["type"] == "STOCK"
    assert external.map_yahoo_quote({"symbol": "BTC-EUR", "quoteType": "CRYPTOCURRENCY"})["type"] == "CRYPTO"
    assert external.map_yahoo_quote({"symbol": "^990100", "quoteType": "INDEX"}) is None   # non acquistabile


async def test_search_yahoo_uses_injected_search_and_filters(monkeypatch):
    async def no_cache(*a, **k):
        return None
    monkeypatch.setattr(external, "_cache_get", no_cache)
    monkeypatch.setattr(external, "_cache_set", no_cache)
    fake = lambda q, n: [{"symbol": "IWDA.AS", "shortname": "iShares MSCI World", "quoteType": "ETF"},  # noqa: E731
                         {"symbol": "^MSCI", "quoteType": "INDEX"}]
    res = await external.search_yahoo("msci world", search_fn=fake)
    assert [r["symbol"] for r in res] == ["IWDA.AS"]


def test_currency_of_pence():
    assert external._currency_of("GBp") == ("GBP", 0.01)
    assert external._currency_of("USD") == ("USD", 1.0)


# ── Metriche ──────────────────────────────────────────────────────────────────

def test_price_metrics_known_series():
    start = datetime.date(2021, 1, 1)
    series = [{"date": (start + datetime.timedelta(days=i)).isoformat(), "close": 100 * (1.10 ** (i / 365))}
              for i in range(0, 365 * 4 + 1)]
    m = price_metrics(series)
    assert m["return_1y_pct"] == pytest.approx(10.0, abs=0.1)
    assert m["return_3y_ann_pct"] == pytest.approx(10.0, abs=0.1)
    assert m["return_5y_ann_pct"] is None          # storico di 4 anni
    assert m["max_drawdown_1y_pct"] == pytest.approx(0.0)


# ── Simulatore ────────────────────────────────────────────────────────────────

def _snapshot(cash_eur=0.0):
    positions = {1: PositionCalc(asset_id=1, lots=[Lot(quantity=100, cost_per_unit_eur=80.0)])}
    info = {1: WORLD}
    price = {1: 100.0}
    account_values = {"Broker": 10_000.0}
    cash = [CashBalance(7, "Broker", "EUR", cash_eur, datetime.date(2026, 11, 1), cash_eur)] if cash_eur else []
    alloc = calculate_allocation(positions, info, price, account_values, cash=cash)
    return SimpleNamespace(positions=positions, asset_info=info, price_eur=price, account_values=account_values,
                           cash=cash, allocation=alloc, transactions=[],
                           accounts=[SimpleNamespace(id=7, name="Broker")])


def _classes(alloc):
    return {i.label: i.pct for i in alloc.by_asset_class}


def test_buying_bond_etf_changes_asset_class_and_xray():
    snap = _snapshot()
    res = simulate(snap, [SimItem(name="Govt 1-3", info=BOND_ETF, price_eur=50.0, quantity=50, symbol="X13G.DE",
                                  account_id=7)])
    assert _classes(res.allocation_before) == {"Azioni": 100.0}
    assert _classes(res.allocation_after)["Obbligazioni"] == pytest.approx(20.0)
    changes = {c["key"]: c for c in res.rule_changes}
    assert changes["asset_class_fixed_income"]["before_status"] == "warn"
    assert changes["asset_class_fixed_income"]["after_status"] == "ok" and changes["asset_class_fixed_income"]["changed"]
    new = next(w for w in res.weights if w["new"])
    assert new["after_pct"] == pytest.approx(20.0) and new["before_pct"] == 0
    assert res.invested_eur == pytest.approx(2500.0)
    assert res.total_after_eur == pytest.approx(12_500.0)   # denaro nuovo


def test_use_cash_moves_money_from_cash_to_securities():
    snap = _snapshot(cash_eur=3000.0)
    res = simulate(snap, [SimItem(name="Govt", info=BOND_ETF, price_eur=50.0, quantity=40, fee_eur=1.0,
                                  account_id=7)], use_cash=True)
    assert res.cash_before_eur == 3000.0 and res.cash_after_eur == pytest.approx(999.0)
    assert res.total_after_eur == pytest.approx(res.total_before_eur - 1.0)   # solo la commissione esce
    assert not res.warnings


def test_insufficient_cash_is_reported():
    snap = _snapshot(cash_eur=100.0)
    res = simulate(snap, [SimItem(name="Govt", info=BOND_ETF, price_eur=50.0, quantity=40, account_id=7)],
                   use_cash=True)
    assert any("insufficiente" in w for w in res.warnings)


def test_adding_to_existing_position_keeps_current_price_valuation():
    snap = _snapshot()
    res = simulate(snap, [SimItem(name="World", info=WORLD, price_eur=100.0, quantity=10, asset_id=1)])
    w = res.weights[0]
    assert w["new"] is False and w["after_pct"] == pytest.approx(100.0)
    assert res.total_after_eur == pytest.approx(11_000.0)
    # la simulazione non modifica lo snapshot originale
    assert snap.positions[1].quantity == 100


def test_invalid_item_ignored_with_warning():
    res = simulate(_snapshot(), [SimItem(name="Zero", info=WORLD, price_eur=0.0, quantity=1)])
    assert res.warnings and res.invested_eur == 0
