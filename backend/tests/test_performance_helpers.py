"""Unit tests for performance period resolution and price lookup helpers."""
import datetime

import pytest

from app.services.portfolio.performance import _last_price_on_or_before, _resolve_period

D = datetime.date.fromisoformat
TODAY = datetime.date.today()


# ── _last_price_on_or_before ──────────────────────────────────────────────────

def test_exact_date_match():
    prices = {D("2023-06-01"): 100.0, D("2023-06-15"): 110.0}
    assert _last_price_on_or_before(prices, D("2023-06-01")) == pytest.approx(100.0)


def test_date_between_entries():
    prices = {D("2023-06-01"): 100.0, D("2023-06-15"): 110.0}
    # Weekend / holiday between the two → returns the earlier one
    assert _last_price_on_or_before(prices, D("2023-06-10")) == pytest.approx(100.0)


def test_date_after_all_entries():
    prices = {D("2023-06-01"): 100.0, D("2023-06-15"): 110.0}
    assert _last_price_on_or_before(prices, D("2023-12-31")) == pytest.approx(110.0)


def test_date_before_all_entries_returns_none():
    prices = {D("2023-06-15"): 110.0}
    assert _last_price_on_or_before(prices, D("2023-06-01")) is None


def test_single_entry_exact():
    prices = {D("2023-01-01"): 50.0}
    assert _last_price_on_or_before(prices, D("2023-01-01")) == pytest.approx(50.0)


def test_empty_price_dict():
    assert _last_price_on_or_before({}, D("2023-06-01")) is None


# ── _resolve_period ───────────────────────────────────────────────────────────

EARLY = D("2020-01-01")


def test_period_max_uses_earliest():
    start, end = _resolve_period("max", EARLY)
    assert start == EARLY
    assert end == TODAY


def test_period_1y():
    start, end = _resolve_period("1y", EARLY)
    assert start == TODAY - datetime.timedelta(days=365)
    assert end == TODAY


def test_period_3m():
    start, end = _resolve_period("3m", EARLY)
    assert start == TODAY - datetime.timedelta(days=90)
    assert end == TODAY


def test_period_1m():
    start, end = _resolve_period("1m", EARLY)
    assert start == TODAY - datetime.timedelta(days=30)
    assert end == TODAY


def test_period_1w():
    start, end = _resolve_period("1w", EARLY)
    assert start == TODAY - datetime.timedelta(days=7)
    assert end == TODAY


def test_period_ytd():
    start, end = _resolve_period("ytd", EARLY)
    assert start == TODAY.replace(month=1, day=1)
    assert end == TODAY


def test_period_mtd():
    start, end = _resolve_period("mtd", EARLY)
    assert start == TODAY.replace(day=1)
    assert end == TODAY


def test_period_wtd():
    start, end = _resolve_period("wtd", EARLY)
    expected_start = TODAY - datetime.timedelta(days=TODAY.weekday())
    assert start == expected_start
    assert end == TODAY


def test_period_calendar_year_past():
    start, end = _resolve_period("2021", EARLY)
    assert start == D("2021-01-01")
    assert end == D("2021-12-31")   # past year → full year


def test_period_calendar_year_current():
    year = str(TODAY.year)
    start, end = _resolve_period(year, EARLY)
    assert start == TODAY.replace(month=1, day=1)
    assert end == TODAY             # current year → up to today


def test_period_capped_by_earliest():
    """Even 3y period cannot start before first transaction."""
    recent_earliest = TODAY - datetime.timedelta(days=10)
    start, end = _resolve_period("3y", recent_earliest)
    assert start == recent_earliest


def test_period_today():
    start, end = _resolve_period("today", EARLY)
    assert start == TODAY
    assert end == TODAY
