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
    total_invested_eur: float          # costo di carico delle posizioni aperte
    total_pnl_eur: float               # non realizzato + realizzato + proventi netti
    total_pnl_pct: float
    realized_pnl_eur: float            # incluse le posizioni chiuse
    unrealized_pnl_eur: float
    daily_change_eur: float
    positions_count: int
    income_eur: float = 0.0            # dividendi + cedole + interessi − costi FEE
    cash_eur: float = 0.0              # liquidità dei conti (ultimo saldo, in EUR)
    net_worth_eur: float = 0.0         # valore investimenti + liquidità


class PerformancePoint(BaseModel):
    date: datetime.date
    value_eur: float
    invested_eur: float           # valore di apertura + flussi netti dall'inizio del periodo
    pnl_eur: float                # valore − investito + proventi
    twrr_pct: float               # cumulato dall'inizio del periodo, proventi inclusi
    daily_return_pct: float | None = None   # rendimento neutralizzato dai flussi
    reliable: bool = True         # False se la base del rendimento è troppo piccola
    flow_eur: float = 0.0         # acquisti − vendite dall'ultima data di valutazione
    income_eur: float = 0.0       # proventi netti dall'ultima data di valutazione


class PerformanceOut(BaseModel):
    period: str
    twrr_pct: float
    series: list[PerformancePoint]
    start_date: datetime.date | None = None            # inizio effettivo
    end_date: datetime.date | None = None
    requested_start_date: datetime.date | None = None
    history_truncated: bool = False    # storico più corto del periodo richiesto
    days: int = 0
    start_value_eur: float = 0.0
    end_value_eur: float = 0.0
    net_flows_eur: float = 0.0         # acquisti − vendite nel periodo
    income_eur: float = 0.0            # proventi netti nel periodo
    invested_eur: float = 0.0          # start_value + net_flows
    pnl_eur: float = 0.0               # end − start − net_flows + income
    twrr_annualized_pct: float | None = None   # solo per periodi ≥ 1 anno


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
    # Per sottostante (look-through)
    by_asset_class: list[AllocationItem] = []          # Azioni / Obbligazioni / Monetario / Crypto / Altro
    by_currency_exposure: list[AllocationItem] = []    # valute del sottostante (hedged → EUR)
    by_continent_equity: list[AllocationItem] = []     # geografia della sola parte azionaria
    by_continent_bond: list[AllocationItem] = []       # geografia della sola parte obbligazionaria
    italy_exposure_pct: float | None = None            # peso Italia sul totale (BTP inclusi)
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
    twrr_annualized_pct: float | None
    best_day_pct: float
    worst_day_pct: float
    positive_days_pct: float
    risk_free_pct: float = 0.0
    warnings: list[str] = []      # indicatori fuori da intervalli plausibili


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



class XRayRule(BaseModel):
    key: str
    name: str
    category: str
    description: str
    status: str          # "ok" | "warn" | "error" | "info"
    actual: float | None = None
    threshold_min: float | None = None
    threshold_max: float | None = None
    unit: str = "%"      # "%" | "EUR" | "mesi"


class XRayResponse(BaseModel):
    rules: list[XRayRule]
    score: int           # 0–100: percentuale regole superate (status == "ok")
    rules_total: int
    rules_ok: int
