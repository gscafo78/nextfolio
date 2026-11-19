"""Unit tests for the Italian tax engine (pure functions — no DB required)."""
import datetime
from types import SimpleNamespace

import pytest

from app.models.asset import AssetType, Exchange
from app.models.transaction import TransactionType
from app.services.tax.calculator import (
    GOVT_WEIGHT,
    TaxEvent,
    _is_government_bond,
    build_annual_reports,
    compute_tax_events,
    crypto_rate,
    open_cost_pools,
    simulate_sell,
    tax_category,
)

W = 12.5 / 26  # ponderazione titoli di Stato (48,08%)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _asset(asset_type=AssetType.STOCK, exchange=Exchange.MIL, name="Test", isin=None, override=None):
    return SimpleNamespace(type=asset_type, exchange=exchange, name=name, symbol=name[:10],
                           isin=isin, govt_bond_override=override)


BTP = _asset(AssetType.BOND, Exchange.MOT, "BTP-1MZ35 3,5%", isin="IT0005001547")
CORP_IT = _asset(AssetType.BOND, Exchange.MOT, "Intesa Sanpaolo 4% 2030", isin="IT0005580003")
BUND = _asset(AssetType.BOND, Exchange.XETRA, "Bund 2,5% 2034", isin="DE0001102580")
EIB = _asset(AssetType.BOND, Exchange.MOT, "BEI Climate Awareness 2031", isin="XS2000000000")
ETF = _asset(AssetType.ETF, Exchange.MIL, "Vanguard FTSE All-World")
BTC = _asset(AssetType.CRYPTO, Exchange.CRYPTO, "Bitcoin")

# Conti: regime dichiarativo (default) e due conti amministrati
DECL = SimpleNamespace(id=1, is_sostituto_imposta=False, is_foreign=True)
ADM_A = SimpleNamespace(id=2, is_sostituto_imposta=True, is_foreign=False)
ADM_B = SimpleNamespace(id=3, is_sostituto_imposta=True, is_foreign=False)

_id_counter = 0


def _tx(asset_id, tx_type, date_str, qty, price, rate=1.0, fee=0.0, asset=None, account=None):
    global _id_counter
    _id_counter += 1
    account = account or DECL
    return SimpleNamespace(
        id=_id_counter,
        asset_id=asset_id,
        account=account,
        account_id=account.id,
        type=tx_type,
        date=datetime.date.fromisoformat(date_str),
        quantity=qty,
        price=price,
        exchange_rate=rate,
        fee=fee,
        asset=asset or _asset(),
    )


def _sell_event(year, gain_loss, govt=False, asset_type="STOCK", administered=False):
    return TaxEvent(
        date=datetime.date(year, 6, 1),
        asset_id=1,
        asset_name="Test",
        asset_type=asset_type,
        tx_type="SELL",
        quantity=1.0,
        proceeds_eur=max(0.0, gain_loss),
        cost_eur=max(0.0, -gain_loss),
        gain_loss_eur=gain_loss,
        is_government_bond=govt,
        is_sostituto_imposta=administered,
    )


def _one(events):
    reports = build_annual_reports(events)
    assert len(reports) == 1
    return reports[0]


# ── Titoli di Stato ───────────────────────────────────────────────────────────

def test_govt_weight_is_48_08_percent():
    assert GOVT_WEIGHT == pytest.approx(0.4808, abs=1e-4)


@pytest.mark.parametrize("asset", [
    BTP,
    _asset(AssetType.BOND, name="BOT 12M 14/08/2026"),
    _asset(AssetType.BOND, name="CCTEU 15/04/2032"),
    _asset(AssetType.BOND, name="BTP Italia 2030"),
    _asset(AssetType.BOND, name="BTP Valore Giu 2031"),
    BUND,
    _asset(AssetType.BOND, name="France OAT 3% 2033"),
    _asset(AssetType.BOND, name="US Treasury 4.25% 2034"),
    EIB,
    _asset(AssetType.BOND, name="World Bank (IBRD) 1% 2030"),
])
def test_government_bonds_recognized(asset):
    assert _is_government_bond(asset) is True
    assert tax_category(asset) == "government_bond"


def test_italian_corporate_bond_is_not_govt():
    """ISIN IT non basta: le obbligazioni societarie italiane sono al 26%."""
    assert _is_government_bond(CORP_IT) is False
    assert tax_category(CORP_IT) == "standard"


def test_non_bond_with_govt_like_name_is_not_govt():
    assert _is_government_bond(_asset(AssetType.ETF, name="iShares Italy Govt Bond (BTP)")) is False


def test_manual_override_wins():
    assert _is_government_bond(_asset(AssetType.BOND, name="Obbligazione XYZ", override=True)) is True
    assert _is_government_bond(_asset(AssetType.BOND, name="BTP 2030", override=False)) is False


def test_categories():
    assert tax_category(_asset()) == "standard"
    assert tax_category(ETF) == "fund"
    assert tax_category(BTC) == "crypto"


# ── Costo medio ponderato (PMC) ───────────────────────────────────────────────

def test_simple_gain():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 120.0),
    ]
    events = compute_tax_events(txs)
    assert len(events) == 1
    ev = events[0]
    assert ev.gain_loss_eur == pytest.approx(200.0)
    assert ev.tx_type == "SELL"
    assert ev.calculation_method == "PMC"
    assert ev.category == "standard"


def test_simple_loss():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 80.0),
    ]
    assert compute_tax_events(txs)[0].gain_loss_eur == pytest.approx(-200.0)


def test_declaratory_uses_weighted_average_not_fifo():
    """Art. 68 c.6 TUIR: costo medio ponderato anche in regime dichiarativo."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 5, 100.0),  # 500
        _tx(1, TransactionType.BUY,  "2023-03-01", 5, 200.0),  # 1000 → PMC 150
        _tx(1, TransactionType.SELL, "2023-06-01", 5, 150.0),  # ricavo 750, costo 750
    ]
    ev = compute_tax_events(txs)[0]
    assert ev.cost_eur == pytest.approx(750.0)
    assert ev.gain_loss_eur == pytest.approx(0.0)   # con FIFO sarebbe stato +250


def test_pmc_after_partial_sell_and_new_buy():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0),  # PMC 100
        _tx(1, TransactionType.SELL, "2023-02-01",  4, 120.0),  # restano 6 @100
        _tx(1, TransactionType.BUY,  "2023-03-01",  6, 140.0),  # 12 @120
        _tx(1, TransactionType.SELL, "2023-06-01", 12, 130.0),  # costo 1440
    ]
    first, second = compute_tax_events(txs)
    assert first.gain_loss_eur == pytest.approx(80.0)
    assert second.cost_eur == pytest.approx(1440.0)
    assert second.gain_loss_eur == pytest.approx(120.0)


def test_declaratory_pool_is_shared_across_declaratory_accounts():
    decl2 = SimpleNamespace(id=9, is_sostituto_imposta=False, is_foreign=True)
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0, account=DECL),
        _tx(1, TransactionType.BUY,  "2023-02-01", 10, 200.0, account=decl2),
        _tx(1, TransactionType.SELL, "2023-06-01", 10, 150.0, account=DECL),
    ]
    assert compute_tax_events(txs)[0].cost_eur == pytest.approx(1500.0)


def test_administered_pool_is_per_account():
    """Ogni intermediario in regime amministrato tiene il proprio costo medio."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0, account=ADM_A),
        _tx(1, TransactionType.BUY,  "2023-02-01", 10, 200.0, account=ADM_B),
        _tx(1, TransactionType.SELL, "2023-06-01", 10, 150.0, account=ADM_A),
        _tx(1, TransactionType.SELL, "2023-07-01", 10, 150.0, account=ADM_B),
    ]
    a, b = compute_tax_events(txs)
    assert a.gain_loss_eur == pytest.approx(500.0)
    assert b.gain_loss_eur == pytest.approx(-500.0)
    assert a.is_sostituto_imposta and b.is_sostituto_imposta


def test_administered_and_declaratory_pools_are_separate():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0, account=ADM_A),
        _tx(1, TransactionType.BUY,  "2023-02-01", 10, 300.0, account=DECL),
        _tx(1, TransactionType.SELL, "2023-06-01", 10, 200.0, account=DECL),
    ]
    assert compute_tax_events(txs)[0].gain_loss_eur == pytest.approx(-1000.0)


def test_fee_increases_buy_cost_and_reduces_proceeds():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0, fee=10.0),  # cost=1010
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 110.0, fee=5.0),   # proceeds=1095
    ]
    assert compute_tax_events(txs)[0].gain_loss_eur == pytest.approx(1095.0 - 1010.0)


def test_fx_rate_applied():
    """USD asset: cost = qty × price × rate."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0, rate=0.92),  # cost = 920
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 110.0, rate=0.91),  # proceeds = 1001
    ]
    ev = compute_tax_events(txs)[0]
    assert ev.cost_eur == pytest.approx(920.0)
    assert ev.proceeds_eur == pytest.approx(1001.0)


def test_buy_only_no_events():
    assert compute_tax_events([_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0)]) == []


def test_open_cost_pools():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0, account=ADM_A),
        _tx(1, TransactionType.BUY,  "2023-02-01",  4, 150.0, account=DECL),
        _tx(1, TransactionType.BUY,  "2023-02-02",  4, 250.0, account=DECL),
        _tx(1, TransactionType.SELL, "2023-03-01", 10, 120.0, account=ADM_A),  # pool A chiuso
    ]
    pools = open_cost_pools(txs)
    assert set(pools) == {("D", 1)}
    assert pools[("D", 1)].quantity == pytest.approx(8)
    assert pools[("D", 1)].avg_cost_per_unit == pytest.approx(200.0)


# ── Eventi di reddito ─────────────────────────────────────────────────────────

def test_dividend_event():
    events = compute_tax_events([_tx(1, TransactionType.DIVIDEND, "2023-05-01", 1, 50.0)])
    assert len(events) == 1
    assert events[0].tx_type == "DIVIDEND"
    assert events[0].gain_loss_eur == pytest.approx(50.0)
    assert events[0].is_government_bond is False
    assert events[0].tax_rate == pytest.approx(0.26)


def test_coupon_govt_bond_12_5():
    ev = compute_tax_events([_tx(2, TransactionType.COUPON, "2023-06-01", 1, 100.0, asset=BTP)])[0]
    assert ev.tx_type == "COUPON" and ev.is_government_bond is True
    assert ev.tax_rate == pytest.approx(0.125)


def test_coupon_italian_corporate_26():
    ev = compute_tax_events([_tx(2, TransactionType.COUPON, "2023-06-01", 1, 100.0, asset=CORP_IT)])[0]
    assert ev.is_government_bond is False
    assert ev.tax_rate == pytest.approx(0.26)


# ── Report annuale: redditi diversi 26% ──────────────────────────────────────

def test_report_simple_gain():
    r = _one([_sell_event(2023, 1000.0)])
    assert r.gains_standard == pytest.approx(1000.0)
    assert r.tax_standard == pytest.approx(260.0)
    assert r.total_tax_due == pytest.approx(260.0)
    assert r.new_carryforward_standard == pytest.approx(0.0)


def test_report_net_loss_generates_carryforward():
    r = _one([_sell_event(2023, -500.0)])
    assert r.losses_standard == pytest.approx(500.0)
    assert r.new_carryforward_standard == pytest.approx(500.0)
    assert r.tax_standard == pytest.approx(0.0)


def test_report_carryforward_offsets_next_year_gain():
    r22, r23 = build_annual_reports([_sell_event(2022, -500.0), _sell_event(2023, 1000.0)])
    assert r22.new_carryforward_standard == pytest.approx(500.0)
    assert r23.carryforward_applied_standard == pytest.approx(500.0)
    assert r23.net_taxable_standard == pytest.approx(500.0)
    assert r23.tax_standard == pytest.approx(130.0)
    assert [(e.year, e.amount, e.expires_year) for e in r23.prior_carryforward_standard] == [(2022, 500.0, 2026)]


def test_report_carryforward_usable_until_fourth_year():
    *_, last = build_annual_reports([_sell_event(2019, -500.0), _sell_event(2023, 1000.0)])
    assert last.carryforward_applied_standard == pytest.approx(500.0)


def test_report_carryforward_expires_after_4_years():
    *_, last = build_annual_reports([_sell_event(2018, -500.0), _sell_event(2023, 1000.0)])
    assert last.carryforward_applied_standard == pytest.approx(0.0)
    assert last.net_taxable_standard == pytest.approx(1000.0)
    assert last.prior_carryforward_standard == []


def test_report_carryforward_oldest_used_first():
    reports = build_annual_reports([
        _sell_event(2020, -300.0), _sell_event(2021, -400.0), _sell_event(2023, 500.0), _sell_event(2025, 1000.0),
    ])
    r23, r25 = reports[-2], reports[-1]
    assert r23.carryforward_applied_standard == pytest.approx(500.0)   # 300 (2020) + 200 (2021)
    # nel 2025 la perdita 2020 è già esaurita, restano 200 del 2021
    assert r25.carryforward_applied_standard == pytest.approx(200.0)
    assert r25.net_taxable_standard == pytest.approx(800.0)


def test_report_gain_and_loss_same_year():
    r = _one([_sell_event(2023, 800.0), _sell_event(2023, -300.0)])
    assert r.net_taxable_standard == pytest.approx(500.0)
    assert r.tax_standard == pytest.approx(130.0)
    assert r.new_carryforward_standard == pytest.approx(0.0)


# ── Report: titoli di Stato al 48,08% nello zainetto unico ───────────────────

def test_report_govt_gain_effective_12_5():
    r = _one([_sell_event(2023, 1000.0, govt=True)])
    assert r.gains_govt == pytest.approx(1000.0)
    assert r.taxable_gains_standard == pytest.approx(1000.0 * W)
    assert r.tax_standard == pytest.approx(125.0, abs=0.01)
    assert r.total_tax_due == pytest.approx(125.0, abs=0.01)


def test_report_standard_loss_offsets_govt_gain():
    """Zainetto unico: una minus 26% compensa una plus su BTP (ponderata)."""
    r = _one([_sell_event(2023, -1000.0), _sell_event(2023, 1000.0, govt=True)])
    assert r.tax_standard == pytest.approx(0.0)
    # 1000 - 480,77 = 519,23 di minusvalenza residua riportabile
    assert r.new_carryforward_standard == pytest.approx(1000.0 - 1000.0 * W)


def test_report_govt_loss_deductible_at_48_08():
    r = _one([_sell_event(2023, -1000.0, govt=True), _sell_event(2023, 1000.0)])
    assert r.taxable_losses_standard == pytest.approx(1000.0 * W)
    assert r.net_taxable_standard == pytest.approx(1000.0 - 1000.0 * W)
    assert r.tax_standard == pytest.approx((1000.0 - 1000.0 * W) * 0.26, abs=0.01)


# ── Report: ETF / OICR ────────────────────────────────────────────────────────

def test_report_etf_gain_not_offset_by_carryforward():
    """Le plus da ETF sono redditi di capitale: tassate al 26% pieno."""
    r22, r23 = build_annual_reports([_sell_event(2022, -1000.0), _sell_event(2023, 1000.0, asset_type="ETF")])
    assert r23.gains_funds == pytest.approx(1000.0)
    assert r23.tax_funds == pytest.approx(260.0)
    assert r23.carryforward_applied_standard == pytest.approx(0.0)
    assert r23.total_tax_due == pytest.approx(260.0)
    assert sum(e.amount for e in r23.prior_carryforward_standard) == pytest.approx(1000.0)


def test_report_etf_gain_not_offset_by_same_year_loss():
    r = _one([_sell_event(2023, -500.0), _sell_event(2023, 1000.0, asset_type="ETF")])
    assert r.tax_funds == pytest.approx(260.0)
    assert r.new_carryforward_standard == pytest.approx(500.0)


def test_report_etf_loss_goes_into_zainetto():
    """Le minus da ETF sono redditi diversi e compensano le plus su azioni."""
    r22, r23 = build_annual_reports([_sell_event(2022, -400.0, asset_type="ETF"), _sell_event(2023, 1000.0)])
    assert r22.losses_funds == pytest.approx(400.0)
    assert r22.new_carryforward_standard == pytest.approx(400.0)
    assert r23.carryforward_applied_standard == pytest.approx(400.0)
    assert r23.tax_standard == pytest.approx(600.0 * 0.26)


# ── Report: cripto-attività ───────────────────────────────────────────────────

def test_crypto_rate_by_year():
    assert crypto_rate(2025) == pytest.approx(0.26)
    assert crypto_rate(2026) == pytest.approx(0.33)


def test_report_crypto_2025_at_26_and_2026_at_33():
    r25, r26 = build_annual_reports([_sell_event(2025, 1000.0, asset_type="CRYPTO"),
                                     _sell_event(2026, 1000.0, asset_type="CRYPTO")])
    assert r25.tax_crypto == pytest.approx(260.0)
    assert r26.crypto_rate == pytest.approx(0.33)
    assert r26.tax_crypto == pytest.approx(330.0)
    assert r26.tax_standard == pytest.approx(0.0)


def test_crypto_event_rate():
    ev = _sell_event(2026, 100.0, asset_type="CRYPTO")
    assert ev.category == "crypto" and ev.tax_rate == pytest.approx(0.33)


def test_report_crypto_has_own_zainetto():
    r25, r26 = build_annual_reports([
        _sell_event(2025, -600.0, asset_type="CRYPTO"),
        _sell_event(2026, 1000.0, asset_type="CRYPTO"),
        _sell_event(2026, 1000.0),
    ])
    assert r25.new_carryforward_crypto == pytest.approx(600.0)
    assert r25.new_carryforward_standard == pytest.approx(0.0)
    assert r26.carryforward_applied_crypto == pytest.approx(600.0)
    assert r26.tax_crypto == pytest.approx(400.0 * 0.33)
    assert r26.tax_standard == pytest.approx(260.0)   # la minus cripto non tocca il 26%


# ── Report: breakdown per regime e redditi ───────────────────────────────────

def test_report_breakdown_by_regime():
    r = _one([
        _sell_event(2023, 1000.0, administered=True),
        _sell_event(2023, 1000.0, govt=True, administered=False),
        _sell_event(2023, 500.0, asset_type="ETF", administered=False),
    ])
    assert r.administered_tax_standard == pytest.approx(260.0)
    assert r.declaratory_taxable_gains == pytest.approx(1000.0 * W)
    assert r.declaratory_tax_standard == pytest.approx(125.0, abs=0.01)
    assert r.declaratory_tax_funds == pytest.approx(130.0)
    assert r.declaratory_total_tax == pytest.approx(255.0, abs=0.01)
    assert r.has_declaratory_accounts is True


def test_report_dividends_informative():
    ev = TaxEvent(
        date=datetime.date(2023, 5, 1), asset_id=1, asset_name="X", asset_type="STOCK", tx_type="DIVIDEND",
        quantity=None, proceeds_eur=100.0, cost_eur=None, gain_loss_eur=100.0, is_government_bond=False,
    )
    r = _one([ev])
    assert r.dividends_eur == pytest.approx(100.0)
    assert r.income_tax_eur == pytest.approx(26.0)
    assert r.tax_standard == pytest.approx(0.0)  # informativo, non aggiunge tasse sulle plusvalenze


def test_report_empty_events():
    assert build_annual_reports([]) == []


# ── simulate_sell ─────────────────────────────────────────────────────────────

def test_simulate_sell_standard_gain():
    r = simulate_sell(_asset(name="ENI"), 5, 130.0, 100.0, year=2025)
    assert r["gain_loss_eur"] == pytest.approx(150.0)
    assert r["estimated_tax_eur"] == pytest.approx(39.0)
    assert r["tax_rate"] == pytest.approx(0.26)
    assert r["net_proceeds_eur"] == pytest.approx(5 * 130.0 - 39.0)


def test_simulate_sell_govt_bond():
    r = simulate_sell(BTP, 1000, 100.0, 98.0, year=2025)
    assert r["gain_loss_eur"] == pytest.approx(2000.0)
    assert r["tax_bracket"] == "government_bond"
    assert r["tax_rate"] == pytest.approx(0.125)
    assert r["estimated_tax_eur"] == pytest.approx(250.0)


def test_simulate_sell_italian_corporate_bond_26():
    r = simulate_sell(CORP_IT, 10, 105.0, 100.0, year=2025)
    assert r["tax_rate"] == pytest.approx(0.26)


def test_simulate_sell_crypto_2026():
    r = simulate_sell(BTC, 1, 60000.0, 50000.0, year=2026)
    assert r["tax_bracket"] == "crypto"
    assert r["estimated_tax_eur"] == pytest.approx(3300.0)


def test_simulate_sell_loss_zero_tax():
    r = simulate_sell(_asset(), 10, 80.0, 100.0, year=2025)
    assert r["gain_loss_eur"] == pytest.approx(-200.0)
    assert r["estimated_tax_eur"] == pytest.approx(0.0)


# ── ETF con quota di titoli di Stato (base imponibile ridotta) ───────────────

def test_etf_govt_share_reduces_taxable_base():
    """ETF obbligazionario con 100% titoli di Stato white list: plus al 48,08% → 12,5% effettivo."""
    etf = _asset(AssetType.ETF, name="Xtrackers Eurozone Government Bond")
    etf.govt_bond_share = 1.0
    txs = [_tx(5, TransactionType.BUY, "2025-01-10", 10, 100.0, asset=etf),
           _tx(5, TransactionType.SELL, "2025-06-10", 10, 110.0, asset=etf)]
    ev = compute_tax_events(txs)[0]
    assert ev.taxable_fraction == pytest.approx(W)
    assert ev.tax_rate == pytest.approx(0.125)
    r = _one(compute_tax_events(txs))
    assert r.gains_funds == pytest.approx(100.0)
    assert r.tax_funds == pytest.approx(12.5, abs=0.01)


def test_etf_partial_govt_share():
    etf = _asset(AssetType.ETF, name="Aggregate Bond")
    etf.govt_bond_share = 0.6
    txs = [_tx(5, TransactionType.BUY, "2025-01-10", 10, 100.0, asset=etf),
           _tx(5, TransactionType.SELL, "2025-06-10", 10, 110.0, asset=etf)]
    r = _one(compute_tax_events(txs))
    assert r.tax_funds == pytest.approx(100 * (0.4 + 0.6 * W) * 0.26, abs=0.01)


def test_etf_loss_with_govt_share_reduced_in_zainetto():
    etf = _asset(AssetType.ETF, name="Govt Bond")
    etf.govt_bond_share = 1.0
    txs = [_tx(5, TransactionType.BUY, "2025-01-10", 10, 100.0, asset=etf),
           _tx(5, TransactionType.SELL, "2025-06-10", 10, 90.0, asset=etf)]
    r = _one(compute_tax_events(txs))
    assert r.losses_funds == pytest.approx(100.0)
    assert r.new_carryforward_standard == pytest.approx(100.0 * W)


def test_simulate_sell_etf_with_govt_share():
    etf = _asset(AssetType.ETF, name="Govt Bond")
    etf.govt_bond_share = 1.0
    assert simulate_sell(etf, 10, 110.0, 100.0, year=2025)["estimated_tax_eur"] == pytest.approx(12.5, abs=0.01)
