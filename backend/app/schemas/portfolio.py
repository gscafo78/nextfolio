import datetime

from pydantic import BaseModel


class PositionOut(BaseModel):
    asset_id: int
    symbol: str
    name: str
    asset_type: str
    currency: str
    exchange: str
    quantity: float
    pmc_eur: float
    total_invested_eur: float
    realized_pnl_eur: float
    current_price: float | None
    current_price_eur: float | None
    current_value_eur: float | None
    unrealized_pnl_eur: float | None
    unrealized_pnl_pct: float | None
    change_pct: float | None


class PortfolioSummaryOut(BaseModel):
    total_value_eur: float
    total_invested_eur: float
    total_pnl_eur: float
    total_pnl_pct: float
    realized_pnl_eur: float
    unrealized_pnl_eur: float
    daily_change_eur: float
    positions_count: int


class PerformancePoint(BaseModel):
    date: datetime.date
    value_eur: float
    invested_eur: float
    pnl_eur: float


class PerformanceOut(BaseModel):
    period: str
    twrr_pct: float
    series: list[PerformancePoint]


class AllocationItem(BaseModel):
    label: str
    value_eur: float
    pct: float
    count: int


class AllocationOut(BaseModel):
    by_type: list[AllocationItem]
    by_currency: list[AllocationItem]
    by_account: list[AllocationItem]
    total_value_eur: float


class DividendOut(BaseModel):
    id: int
    date: datetime.date
    asset_id: int
    symbol: str
    name: str
    type: str
    amount_eur: float
    account_name: str
    account_id: int
