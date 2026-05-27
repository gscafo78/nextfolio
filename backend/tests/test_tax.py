"""Unit tests for the Italian tax engine (pure functions — no DB required)."""
import datetime
from types import SimpleNamespace

import pytest

from app.models.asset import AssetType, Exchange
from app.models.transaction import TransactionType
from app.services.tax.calculator import (
    _Lot,
    _is_government_bond,
    build_annual_reports,
    compute_tax_events,
    simulate_sell,
    TaxEvent,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _asset(asset_type=AssetType.STOCK, exchange=Exchange.MIL, name="Test"):
    return SimpleNamespace(type=asset_type, exchange=exchange, name=name)


_id_counter = 0

def _tx(asset_id, tx_type, date_str, qty, price, rate=1.0, fee=0.0, asset=None):
    global _id_counter
    _id_counter += 1
    return SimpleNamespace(
        id=_id_counter,
        asset_id=asset_id,
        type=tx_type,
        date=datetime.date.fromisoformat(date_str),
        quantity=qty,
        price=price,
        exchange_rate=rate,
        fee=fee,
        asset=asset or _asset(),
    )


def _sell_event(year, gain_loss, govt=False):
    return TaxEvent(
        date=datetime.date(year, 6, 1),
        asset_id=1,
        asset_name="Test",
        asset_type="STOCK",
        tx_type="SELL",
        quantity=1.0,
        proceeds_eur=max(0.0, gain_loss),
        cost_eur=max(0.0, -gain_loss),
        gain_loss_eur=gain_loss,
        is_government_bond=govt,
    )


# ── _is_government_bond ───────────────────────────────────────────────────────

def test_government_bond_mot():
    assert _is_government_bond(_asset(AssetType.BOND, Exchange.MOT)) is True


def test_bond_not_mot_is_not_govt():
    assert _is_government_bond(_asset(AssetType.BOND, Exchange.MIL)) is False


def test_etf_is_not_govt():
    assert _is_government_bond(_asset(AssetType.ETF, Exchange.MIL)) is False


def test_stock_is_not_govt():
    assert _is_government_bond(_asset(AssetType.STOCK, Exchange.MIL)) is False


# ── compute_tax_events — FIFO ─────────────────────────────────────────────────

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
    assert ev.is_government_bond is False


def test_simple_loss():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 80.0),
    ]
    events = compute_tax_events(txs)
    assert events[0].gain_loss_eur == pytest.approx(-200.0)


def test_partial_sell_uses_fifo_cost():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),   # cost = 1000, 100/unit
        _tx(1, TransactionType.SELL, "2023-06-15",  5, 150.0),   # proceeds = 750, cost = 500
    ]
    events = compute_tax_events(txs)
    assert len(events) == 1
    assert events[0].gain_loss_eur == pytest.approx(250.0)


def test_two_lots_fifo_order():
    """FIFO exhausts the first (cheaper) lot before using the second."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01",  5, 100.0),  # lot1: 5 × 100
        _tx(1, TransactionType.BUY,  "2023-03-01",  5, 200.0),  # lot2: 5 × 200
        _tx(1, TransactionType.SELL, "2023-06-01",  5, 150.0),  # uses lot1 (cheaper)
    ]
    events = compute_tax_events(txs)
    assert len(events) == 1
    # proceeds=750, cost=500 (first lot at 100/unit)
    assert events[0].gain_loss_eur == pytest.approx(250.0)


def test_cross_lot_fifo_partial():
    """Sell spanning two lots."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01",  5, 100.0),  # 500
        _tx(1, TransactionType.BUY,  "2023-03-01",  5, 200.0),  # 1000
        _tx(1, TransactionType.SELL, "2023-06-01",  8, 180.0),  # spans both lots
    ]
    events = compute_tax_events(txs)
    # proceeds = 8 × 180 = 1440
    # cost = 5×100 + 3×200 = 500 + 600 = 1100
    assert events[0].proceeds_eur == pytest.approx(1440.0)
    assert events[0].cost_eur == pytest.approx(1100.0)
    assert events[0].gain_loss_eur == pytest.approx(340.0)


def test_govt_bond_sell_flagged():
    btp = _asset(AssetType.BOND, Exchange.MOT, "BTP 2026")
    txs = [
        _tx(2, TransactionType.BUY,  "2023-01-10", 1000, 98.0, asset=btp),
        _tx(2, TransactionType.SELL, "2023-10-01", 1000, 100.0, asset=btp),
    ]
    events = compute_tax_events(txs)
    assert events[0].is_government_bond is True
    assert events[0].gain_loss_eur == pytest.approx(2000.0)
    assert events[0].tax_rate == pytest.approx(0.125)


def test_fee_increases_buy_cost():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0, fee=10.0),  # cost=1010
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 110.0, fee=5.0),   # proceeds=1095
    ]
    events = compute_tax_events(txs)
    assert events[0].gain_loss_eur == pytest.approx(1095.0 - 1010.0)


def test_dividend_event():
    txs = [_tx(1, TransactionType.DIVIDEND, "2023-05-01", 1, 50.0)]
    events = compute_tax_events(txs)
    assert len(events) == 1
    assert events[0].tx_type == "DIVIDEND"
    assert events[0].gain_loss_eur == pytest.approx(50.0)
    assert events[0].is_government_bond is False  # dividends always 26%


def test_coupon_govt_bond():
    btp = _asset(AssetType.BOND, Exchange.MOT, "BTP")
    txs = [_tx(2, TransactionType.COUPON, "2023-06-01", 1, 100.0, asset=btp)]
    events = compute_tax_events(txs)
    assert events[0].tx_type == "COUPON"
    assert events[0].is_government_bond is True


def test_buy_only_no_events():
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0)]
    events = compute_tax_events(txs)
    assert events == []


def test_fx_rate_applied():
    """USD asset: cost = qty × price × rate."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0, rate=0.92),  # cost = 920
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 110.0, rate=0.91),  # proceeds = 1001
    ]
    events = compute_tax_events(txs)
    assert events[0].cost_eur == pytest.approx(920.0)
    assert events[0].proceeds_eur == pytest.approx(1001.0)


# ── build_annual_reports ──────────────────────────────────────────────────────

def test_report_simple_gain():
    events = [_sell_event(2023, 1000.0)]
    reports = build_annual_reports(events)
    assert len(reports) == 1
    r = reports[0]
    assert r.gains_standard == pytest.approx(1000.0)
    assert r.tax_standard == pytest.approx(260.0)
    assert r.total_tax_due == pytest.approx(260.0)
    assert r.new_carryforward_standard == pytest.approx(0.0)


def test_report_govt_bond_rate():
    events = [_sell_event(2023, 1000.0, govt=True)]
    reports = build_annual_reports(events)
    assert reports[0].tax_govt == pytest.approx(125.0)
    assert reports[0].total_tax_due == pytest.approx(125.0)


def test_report_net_loss_generates_carryforward():
    events = [_sell_event(2023, -500.0)]
    reports = build_annual_reports(events)
    r = reports[0]
    assert r.losses_standard == pytest.approx(500.0)
    assert r.new_carryforward_standard == pytest.approx(500.0)
    assert r.tax_standard == pytest.approx(0.0)


def test_report_carryforward_offsets_next_year_gain():
    events = [
        _sell_event(2022, -500.0),   # perdita → carryforward 500
        _sell_event(2023, 1000.0),   # guadagno 1000 → compensato 500
    ]
    reports = build_annual_reports(events)
    r22, r23 = reports
    assert r22.new_carryforward_standard == pytest.approx(500.0)
    assert r23.carryforward_applied_standard == pytest.approx(500.0)
    assert r23.net_taxable_standard == pytest.approx(500.0)
    assert r23.tax_standard == pytest.approx(130.0)


def test_report_carryforward_expires_after_4_years():
    events = [
        _sell_event(2018, -500.0),   # scade dopo 2022
        _sell_event(2023, 1000.0),   # non può usare la perdita del 2018
    ]
    reports = build_annual_reports(events)
    r2023 = reports[-1]
    assert r2023.carryforward_applied_standard == pytest.approx(0.0)
    assert r2023.net_taxable_standard == pytest.approx(1000.0)


def test_report_gain_and_loss_same_year():
    events = [
        _sell_event(2023, 800.0),
        _sell_event(2023, -300.0),
    ]
    reports = build_annual_reports(events)
    r = reports[0]
    assert r.gains_standard == pytest.approx(800.0)
    assert r.losses_standard == pytest.approx(300.0)
    assert r.net_taxable_standard == pytest.approx(500.0)
    assert r.tax_standard == pytest.approx(130.0)
    assert r.new_carryforward_standard == pytest.approx(0.0)


def test_report_brackets_independent():
    """Standard and govt losses don't cross brackets."""
    events = [
        _sell_event(2023, -1000.0, govt=False),  # standard loss
        _sell_event(2023, 500.0,   govt=True),   # govt gain — NOT offset by standard loss
    ]
    reports = build_annual_reports(events)
    r = reports[0]
    assert r.tax_standard == pytest.approx(0.0)
    assert r.tax_govt == pytest.approx(500.0 * 0.125)


def test_report_dividends_informative():
    events = [
        TaxEvent(
            date=datetime.date(2023, 5, 1), asset_id=1, asset_name="X",
            asset_type="STOCK", tx_type="DIVIDEND",
            quantity=None, proceeds_eur=100.0, cost_eur=None,
            gain_loss_eur=100.0, is_government_bond=False,
        )
    ]
    reports = build_annual_reports(events)
    r = reports[0]
    assert r.dividends_eur == pytest.approx(100.0)
    assert r.tax_standard == pytest.approx(0.0)  # informativo, non aggiunge tasse dirette


def test_report_empty_events():
    assert build_annual_reports([]) == []


# ── simulate_sell ─────────────────────────────────────────────────────────────

def test_simulate_sell_standard_gain():
    asset = _asset(AssetType.STOCK, Exchange.MIL, "ENI")
    lots = [_Lot(quantity=10, cost_per_unit_eur=100.0)]
    r = simulate_sell(asset, 5, 130.0, lots)
    assert r["gain_loss_eur"] == pytest.approx(150.0)   # (130-100)*5
    assert r["estimated_tax_eur"] == pytest.approx(39.0)  # 150*0.26
    assert r["tax_rate"] == pytest.approx(0.26)
    assert r["net_proceeds_eur"] == pytest.approx(5 * 130.0 - 39.0)


def test_simulate_sell_govt_bond():
    asset = _asset(AssetType.BOND, Exchange.MOT, "BTP")
    lots = [_Lot(quantity=1000, cost_per_unit_eur=98.0)]
    r = simulate_sell(asset, 1000, 100.0, lots)
    assert r["gain_loss_eur"] == pytest.approx(2000.0)
    assert r["tax_rate"] == pytest.approx(0.125)
    assert r["estimated_tax_eur"] == pytest.approx(250.0)


def test_simulate_sell_loss_zero_tax():
    asset = _asset()
    lots = [_Lot(quantity=10, cost_per_unit_eur=100.0)]
    r = simulate_sell(asset, 10, 80.0, lots)
    assert r["gain_loss_eur"] == pytest.approx(-200.0)
    assert r["estimated_tax_eur"] == pytest.approx(0.0)


def test_simulate_sell_multiple_lots_fifo():
    """Simulation uses FIFO order across lots."""
    lots = [
        _Lot(quantity=5, cost_per_unit_eur=100.0),
        _Lot(quantity=5, cost_per_unit_eur=200.0),
    ]
    asset = _asset()
    r = simulate_sell(asset, 7, 150.0, lots)
    # cost = 5*100 + 2*200 = 900
    # proceeds = 7*150 = 1050
    assert r["cost_basis_eur"] == pytest.approx(900.0)
    assert r["gain_loss_eur"] == pytest.approx(150.0)
