"""Classificazione per sottostante, allocazione look-through e regole X-Ray."""
import datetime
from types import SimpleNamespace

import pytest

from app.schemas.portfolio import PositionOut
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.classification import (
    BOND,
    EQUITY,
    MONEY_MARKET,
    OTHER,
    UNCLASSIFIED_CURRENCY,
    asset_class,
    asset_class_weights,
    currency_exposure,
    display_ticker,
    infer_broker,
    maturity_from_name,
)
from app.services.portfolio.xray import compute_xray

# Strumenti con nomi e look-through come nel portafoglio di esempio
WORLD = {"type": "ETF", "name": "iShares Core MSCI World UCITS ETF USD (Acc)", "currency": "EUR",
         "isin": "IE00B4L5Y983", "symbol": "IE00B4L5Y983", "yahoo_ticker": "SWDA.MI",
         "sectors": [{"name": "Technology", "weight": 0.3}, {"name": "Financial Services", "weight": 0.7}],
         "countries": [{"code": "US", "weight": 0.703}, {"code": "JP", "weight": 0.057},
                       {"code": "GB", "weight": 0.036}, {"code": "CA", "weight": 0.033}]}
EM = {"type": "ETF", "name": "Xtrackers MSCI Emerging Markets UCITS ETF 1C", "currency": "EUR",
      "sectors": [{"name": "Technology", "weight": 1.0}],
      "countries": [{"code": "TW", "weight": 0.267}, {"code": "KR", "weight": 0.235},
                    {"code": "CN", "weight": 0.172}, {"code": "IN", "weight": 0.112}]}
EUROPE = {"type": "ETF", "name": "Amundi Core Stoxx Europe 600 UCITS ETF Acc", "currency": "EUR",
          "sectors": [{"name": "Industrials", "weight": 1.0}],
          "countries": [{"code": "GB", "weight": 0.214}, {"code": "CH", "weight": 0.151},
                        {"code": "FR", "weight": 0.141}, {"code": "DE", "weight": 0.129}]}
GOVT_ETF = {"type": "ETF", "name": "Xtrackers II Eurozone Government Bond 5-7 UCITS ETF 1C", "currency": "EUR",
            "sectors": [], "countries": [{"code": "FR", "weight": 0.255}, {"code": "IT", "weight": 0.202},
                                         {"code": "DE", "weight": 0.18}, {"code": "ES", "weight": 0.166}]}
AGG_ETF = {"type": "ETF", "name": "iShares € Aggregate Bond ESG SRI UCITS ETF EUR (Acc)", "currency": "EUR",
           "sectors": [], "countries": [{"code": "FR", "weight": 0.182}, {"code": "IT", "weight": 0.115}]}
HY_USD = {"type": "ETF", "name": "iShares USD High Yield Corp Bond ESG (Acc)", "currency": "EUR",
          "sectors": [], "countries": []}
BTP = {"type": "BOND", "name": "Btp Tf 1,65% Dc30 Eur", "currency": "EUR", "isin": "IT0005413171",
       "sectors": [{"name": "Bonds", "weight": 1.0}], "countries": [{"code": "IT", "weight": 1.0}]}


# ── Asset class ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("info,expected", [
    (WORLD, EQUITY), (EM, EQUITY), (EUROPE, EQUITY),
    (GOVT_ETF, BOND), (AGG_ETF, BOND), (HY_USD, BOND), (BTP, BOND),
    ({"type": "ETF", "name": "Xtrackers II EUR Overnight Rate Swap UCITS ETF"}, MONEY_MARKET),
    ({"type": "ETF", "name": "Lyxor Smart Overnight Return"}, MONEY_MARKET),
    ({"type": "ETF", "name": "iShares Physical Gold ETC"}, OTHER),
    ({"type": "STOCK", "name": "ENI"}, EQUITY),
])
def test_asset_class(info, expected):
    assert asset_class(info) == expected


def test_balanced_fund_split():
    w = asset_class_weights({"type": "ETF", "name": "Vanguard LifeStrategy 60% Equity UCITS ETF"})
    assert w == {EQUITY: pytest.approx(0.6), BOND: pytest.approx(0.4)}


def test_override_wins():
    assert asset_class({**WORLD, "asset_class_override": "BOND"}) == BOND


# ── Valute ────────────────────────────────────────────────────────────────────

def test_world_etf_is_mostly_usd_despite_eur_listing():
    fx = currency_exposure(WORLD)
    assert fx["USD"] == pytest.approx(0.703)
    assert fx["JPY"] == pytest.approx(0.057)
    assert fx[UNCLASSIFIED_CURRENCY] == pytest.approx(1 - 0.829)


def test_hedged_etf_is_eur():
    assert currency_exposure({**WORLD, "name": "iShares Core MSCI World EUR Hedged UCITS ETF"}) == {"EUR": 1.0}


def test_bond_etf_currency_from_name():
    assert currency_exposure(HY_USD) == {"USD": 1.0}
    assert currency_exposure(AGG_ETF) == {"EUR": 1.0}
    assert currency_exposure(GOVT_ETF) == {"EUR": 1.0}


def test_em_currencies():
    assert currency_exposure(EM)["Valute emergenti"] == pytest.approx(0.786)


# ── Scadenze, ticker, broker ──────────────────────────────────────────────────

def test_maturity_from_italian_month_code():
    assert maturity_from_name("Btp Tf 1,65% Dc30 Eur") == datetime.date(2030, 12, 31)
    assert maturity_from_name("BOT 14/08/2026") == datetime.date(2026, 8, 14)
    assert maturity_from_name("Obbligazione senza data") is None


def test_display_ticker_never_isin():
    assert display_ticker(WORLD) == "SWDA"
    assert display_ticker({"symbol": "IT0005413171", "isin": "IT0005413171"}) == ""
    assert display_ticker({"symbol": "ENI", "isin": "IT0003132476"}) == "ENI"


def test_infer_broker():
    assert infer_broker("Trade Republic", "https://traderepublic.com/") == "Trade Republic"
    assert infer_broker("Conto", "https://de.scalable.capital/cockpit/") == "Scalable Capital"
    assert infer_broker("Conto principale") is None


# ── Allocazione + X-Ray sul portafoglio di esempio ────────────────────────────

# Pesi approssimati del portafoglio d'esempio (valore totale 10.000)
WEIGHTS = {1: (WORLD, 4470), 2: (GOVT_ETF, 400), 3: (EUROPE, 1520), 4: (AGG_ETF, 360),
           5: (EM, 1450), 6: (BTP, 1800)}


def _portfolio():
    positions = {aid: SimpleNamespace(quantity=v / 10.0) for aid, (_, v) in WEIGHTS.items()}
    info = {aid: i for aid, (i, _) in WEIGHTS.items()}
    price = {aid: 10.0 for aid in WEIGHTS}
    alloc = calculate_allocation(positions, info, price, {"Trade Republic": 3000, "Scalable": 7000})
    pos_out = [
        PositionOut(asset_id=aid, symbol=str(aid), name=i["name"], asset_type=i["type"], currency="EUR",
                    exchange="OTHER", quantity=v / 10, pmc_eur=10, total_invested_eur=v, realized_pnl_eur=0,
                    current_price=10, current_price_eur=10, current_value_eur=v, unrealized_pnl_eur=0,
                    unrealized_pnl_pct=0, change_pct=0)
        for aid, (i, v) in WEIGHTS.items()
    ]
    return alloc, pos_out, info


def _rule(xray, key):
    return next(r for r in xray.rules if r.key == key)


def test_allocation_by_asset_class():
    alloc, _, _ = _portfolio()
    classes = {i.label: i.pct for i in alloc.by_asset_class}
    assert classes["Azioni"] == pytest.approx(74.4, abs=0.1)
    assert classes["Obbligazioni"] == pytest.approx(25.6, abs=0.1)


def test_bond_etfs_are_bonds_in_sector_lookthrough():
    alloc, _, _ = _portfolio()
    sectors = {i.label: i.pct for i in alloc.by_sector}
    assert "Non classificato" not in sectors
    assert sectors["Bonds"] == pytest.approx(25.6, abs=0.1)


def test_geography_split_by_class():
    alloc, _, _ = _portfolio()
    eq = {i.label: i.pct for i in alloc.by_continent_equity}
    bd = {i.label: i.pct for i in alloc.by_continent_bond}
    assert eq["Nord America"] > 40
    assert bd["Europa"] == pytest.approx(100.0)
    assert alloc.italy_exposure_pct == pytest.approx((1800 + 400 * 0.202 + 360 * 0.115) / 100, abs=0.1)


def test_currency_exposure_not_100_eur():
    alloc, _, _ = _portfolio()
    fx = {i.label: i.pct for i in alloc.by_currency_exposure}
    assert fx["USD"] > 30
    assert fx["EUR"] < 50
    assert {i.label: i.pct for i in alloc.by_currency}["EUR"] == pytest.approx(100.0)  # quotazione invariata


def test_xray_on_example_portfolio():
    alloc, pos, info = _portfolio()
    x = compute_xray(positions=pos, allocation=alloc, transactions=[], total_value=10000, asset_info=info,
                     today=datetime.date(2026, 11, 19))
    single = _rule(x, "concentration_single_asset")
    assert single.status == "ok"                      # l'ETF MSCI World (44,7%) è escluso
    assert single.actual == pytest.approx(18.0)       # il BTP è il titolo singolo più pesante
    assert _rule(x, "asset_class_equity").status == "ok"
    assert _rule(x, "asset_class_equity").actual == pytest.approx(74.4, abs=0.1)
    assert _rule(x, "asset_class_fixed_income").actual == pytest.approx(25.6, abs=0.1)
    liquidity = _rule(x, "liquidity_emergency_fund")
    assert liquidity.actual == pytest.approx(0.0)     # un BTP 2030 non è liquidità
    assert liquidity.status == "warn"
    assert _rule(x, "asset_class_currency_eur").actual < 50
    assert _rule(x, "geo_italy_exposure").actual == pytest.approx(19.2, abs=0.2)


def test_short_bond_counts_as_liquidity():
    alloc, pos, info = _portfolio()
    x = compute_xray(positions=pos, allocation=alloc, transactions=[], total_value=10000, asset_info=info,
                     maturities={6: datetime.date(2027, 3, 31)}, today=datetime.date(2026, 11, 19))
    assert _rule(x, "liquidity_emergency_fund").actual == pytest.approx(18.0)


def test_single_stock_concentration_error():
    alloc, pos, info = _portfolio()
    pos[0] = pos[0].model_copy(update={"asset_type": "STOCK", "name": "NVIDIA"})
    info = {**info, 1: {**WORLD, "type": "STOCK"}}
    x = compute_xray(positions=pos, allocation=alloc, transactions=[], total_value=10000, asset_info=info)
    assert _rule(x, "concentration_single_asset").status == "error"


# ── Liquidità dei conti ───────────────────────────────────────────────────────

def _cash(value, currency="EUR", account="Trade Republic", account_id=2):
    from app.services.cash import CashBalance
    return CashBalance(account_id, account, currency, value, datetime.date(2026, 11, 19), value)


def test_allocation_includes_cash_as_money_market():
    positions = {aid: SimpleNamespace(quantity=v / 10.0) for aid, (_, v) in WEIGHTS.items()}
    info = {aid: i for aid, (i, _) in WEIGHTS.items()}
    alloc = calculate_allocation(positions, info, {aid: 10.0 for aid in WEIGHTS},
                                 {"Trade Republic": 3000, "Scalable": 7000}, cash=[_cash(1000)])
    assert alloc.total_value_eur == pytest.approx(11000)
    classes = {i.label: i.pct for i in alloc.by_asset_class}
    assert classes["Monetario"] == pytest.approx(9.1, abs=0.1)
    assert {i.label: i.value_eur for i in alloc.by_account}["Trade Republic"] == pytest.approx(4000)
    assert {i.label for i in alloc.by_type} >= {"Liquidità"}


def test_negative_cash_is_ignored():
    alloc = calculate_allocation({}, {}, {}, {}, cash=[_cash(-500)])
    assert alloc.total_value_eur == 0


def test_xray_liquidity_counts_cash():
    alloc, pos, info = _portfolio()
    x = compute_xray(positions=pos, allocation=alloc, transactions=[], total_value=10500, asset_info=info,
                     cash_eur=500, today=datetime.date(2026, 11, 19))
    rule = _rule(x, "liquidity_emergency_fund")
    assert rule.actual == pytest.approx(4.8, abs=0.1)
    assert rule.status == "ok"
