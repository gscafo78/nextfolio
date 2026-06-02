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
    period_pnl_eur: float | None = None
    period_pnl_pct: float | None = None


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
    twrr_pct: float


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
    by_sector: list[AllocationItem] = []
    by_continent: list[AllocationItem] = []
    total_value_eur: float


class ETFHoldingItem(BaseModel):
    symbol: str
    name: str
    weight: float


class CountryItem(BaseModel):
    code: str
    name: str
    weight: float


class ETFHoldingOut(BaseModel):
    asset_id: int
    symbol: str
    name: str
    value_eur: float | None
    holdings: list[ETFHoldingItem]
    is_override: bool
    countries_override: list[CountryItem] | None = None


class DashboardOut(BaseModel):
    summary: PortfolioSummaryOut
    positions: list[PositionOut]
    allocation: AllocationOut


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


class RiskMetricsOut(BaseModel):
    period: str
    trading_days: int
    annualized_volatility_pct: float
    max_drawdown_pct: float
    max_drawdown_start: datetime.date | None
    max_drawdown_end: datetime.date | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    twrr_annualized_pct: float
    best_day_pct: float
    worst_day_pct: float
    positive_days_pct: float


class HoldingPricePoint(BaseModel):
    date: datetime.date
    price: float


class HoldingActivityOut(BaseModel):
    id: int
    type: str
    date: datetime.date
    quantity: float
    price: float
    price_currency: str
    total_eur: float
    fee: float
    account_name: str
    account_id: int


class HoldingAccountOut(BaseModel):
    account_id: int
    account_name: str
    quantity: float
    value_eur: float | None
    pct: float | None


class SectorItem(BaseModel):
    name: str
    weight: float


class HoldingDetailOut(BaseModel):
    asset_id: int
    symbol: str
    name: str
    asset_type: str
    currency: str
    exchange: str
    isin: str | None
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
    min_price: float | None
    max_price: float | None
    total_fees: float
    activities_count: int
    first_buy_date: datetime.date | None
    price_history: list[HoldingPricePoint]
    activities: list[HoldingActivityOut]
    accounts: list[HoldingAccountOut]
    sectors: list[SectorItem] | None = None
    countries: list[CountryItem] | None = None
