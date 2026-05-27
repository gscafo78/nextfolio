"""Unit tests for the FIFO positions calculator (pure functions — no DB)."""
import datetime
from types import SimpleNamespace

import pytest

from app.models.transaction import TransactionType
from app.services.portfolio.positions import calculate_positions


# ── Helpers ───────────────────────────────────────────────────────────────────

_ctr = 0

def _tx(asset_id, tx_type, date_str, qty, price, rate=1.0, fee=0.0):
    global _ctr
    _ctr += 1
    return SimpleNamespace(
        id=_ctr,
        asset_id=asset_id,
        type=tx_type,
        date=datetime.date.fromisoformat(date_str),
        quantity=qty,
        price=price,
        exchange_rate=rate,
        fee=fee,
    )


# ── Single buy ────────────────────────────────────────────────────────────────

def test_single_buy_quantity():
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0)]
    pos = calculate_positions(txs)[1]
    assert pos.quantity == pytest.approx(10.0)


def test_single_buy_pmc():
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0)]
    pos = calculate_positions(txs)[1]
    assert pos.pmc_eur == pytest.approx(100.0)


def test_single_buy_invested():
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0)]
    pos = calculate_positions(txs)[1]
    assert pos.total_invested_eur == pytest.approx(1000.0)


def test_buy_fee_in_cost_basis():
    """Fee is added to cost basis, raising PMC."""
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0, fee=10.0)]
    pos = calculate_positions(txs)[1]
    assert pos.pmc_eur == pytest.approx(101.0)        # (1000 + 10) / 10
    assert pos.total_invested_eur == pytest.approx(1010.0)


def test_buy_fx_rate():
    """Foreign-currency buy: PMC = price × rate."""
    txs = [_tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0, rate=0.92)]
    pos = calculate_positions(txs)[1]
    assert pos.pmc_eur == pytest.approx(92.0)
    assert pos.total_invested_eur == pytest.approx(920.0)


# ── Sell ──────────────────────────────────────────────────────────────────────

def test_partial_sell_reduces_quantity():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15",  3, 120.0),
    ]
    pos = calculate_positions(txs)[1]
    assert pos.quantity == pytest.approx(7.0)


def test_full_sell_closes_position():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 120.0),
    ]
    assert 1 not in calculate_positions(txs)


def test_realized_pnl_gain():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),   # cost = 1000
        _tx(1, TransactionType.BUY,  "2023-03-01",  5, 100.0),   # keep 5 open
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 130.0),   # proceeds = 1300, cost = 1000
    ]
    pos = calculate_positions(txs)[1]
    assert pos.realized_pnl_eur == pytest.approx(300.0)


def test_realized_pnl_loss():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(1, TransactionType.BUY,  "2023-03-01",  5, 100.0),
        _tx(1, TransactionType.SELL, "2023-06-15", 10, 80.0),   # proceeds = 800
    ]
    pos = calculate_positions(txs)[1]
    assert pos.realized_pnl_eur == pytest.approx(-200.0)


# ── FIFO ordering ─────────────────────────────────────────────────────────────

def test_two_lots_pmc_weighted():
    """PMC is weighted average of remaining open lots."""
    txs = [
        _tx(1, TransactionType.BUY, "2023-01-01", 10, 100.0),  # lot1 @ 100
        _tx(1, TransactionType.BUY, "2023-03-01", 10, 200.0),  # lot2 @ 200
    ]
    pos = calculate_positions(txs)[1]
    # PMC = (10×100 + 10×200) / 20 = 150
    assert pos.pmc_eur == pytest.approx(150.0)


def test_fifo_sell_exhausts_first_lot():
    """After selling first lot entirely, PMC becomes second lot's price."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01", 10, 100.0),
        _tx(1, TransactionType.BUY,  "2023-03-01", 10, 200.0),
        _tx(1, TransactionType.SELL, "2023-06-01", 10, 150.0),  # consumes first lot
    ]
    pos = calculate_positions(txs)[1]
    assert pos.quantity == pytest.approx(10.0)
    assert pos.pmc_eur == pytest.approx(200.0)


def test_fifo_cross_lot_sell():
    """Sell spanning two lots splits cost correctly."""
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-01",  5, 100.0),  # 500
        _tx(1, TransactionType.BUY,  "2023-03-01",  5, 200.0),  # 1000
        _tx(1, TransactionType.BUY,  "2023-05-01",  5, 150.0),  # keep this
        _tx(1, TransactionType.SELL, "2023-06-01",  8, 180.0),  # spans lot1+lot2
    ]
    pos = calculate_positions(txs)[1]
    # Remaining: 2 units from lot2 (@200) + 5 from lot3 (@150)
    assert pos.quantity == pytest.approx(7.0)
    expected_pmc = (2 * 200.0 + 5 * 150.0) / 7
    assert pos.pmc_eur == pytest.approx(expected_pmc)


# ── Multiple assets ───────────────────────────────────────────────────────────

def test_multiple_assets_independent():
    txs = [
        _tx(1, TransactionType.BUY, "2023-01-10", 10, 100.0),
        _tx(2, TransactionType.BUY, "2023-01-15",  5, 200.0),
        _tx(2, TransactionType.BUY, "2023-02-01",  5, 220.0),
    ]
    positions = calculate_positions(txs)
    assert positions[1].quantity == pytest.approx(10.0)
    assert positions[2].quantity == pytest.approx(10.0)
    assert positions[1].pmc_eur == pytest.approx(100.0)
    assert positions[2].pmc_eur == pytest.approx(210.0)


def test_sell_one_asset_does_not_affect_other():
    txs = [
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
        _tx(2, TransactionType.BUY,  "2023-01-15",  5, 200.0),
        _tx(1, TransactionType.SELL, "2023-06-01", 10, 120.0),  # closes asset 1
    ]
    positions = calculate_positions(txs)
    assert 1 not in positions
    assert 2 in positions
    assert positions[2].quantity == pytest.approx(5.0)


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_transactions():
    assert calculate_positions([]) == {}


def test_dividend_does_not_create_position():
    txs = [_tx(1, TransactionType.DIVIDEND, "2023-05-01", 1, 50.0)]
    assert calculate_positions(txs) == {}


def test_chronological_order_enforced():
    """Transactions must be processed in date order regardless of input order."""
    txs = [
        _tx(1, TransactionType.SELL, "2023-06-15", 5, 120.0),  # given first but later
        _tx(1, TransactionType.BUY,  "2023-01-10", 10, 100.0),
    ]
    pos = calculate_positions(txs)
    assert 1 in pos
    assert pos[1].quantity == pytest.approx(5.0)
