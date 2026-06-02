import { api } from "./api";

export interface PositionOut {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  exchange: string;
  quantity: number;
  pmc_eur: number;
  total_invested_eur: number;
  realized_pnl_eur: number;
  current_price: number | null;
  current_price_eur: number | null;
  current_value_eur: number | null;
  unrealized_pnl_eur: number | null;
  unrealized_pnl_pct: number | null;
  change_pct: number | null;
  period_pnl_eur: number | null;
  period_pnl_pct: number | null;
}

export interface PortfolioSummaryOut {
  total_value_eur: number;
  total_invested_eur: number;
  total_pnl_eur: number;
  total_pnl_pct: number;
  realized_pnl_eur: number;
  unrealized_pnl_eur: number;
  daily_change_eur: number;
  positions_count: number;
}

export interface PerformancePoint {
  date: string;
  value_eur: number;
  invested_eur: number;
  pnl_eur: number;
  twrr_pct: number;
}

export interface PerformanceOut {
  period: string;
  twrr_pct: number;
  series: PerformancePoint[];
}

export interface AllocationItem {
  label: string;
  value_eur: number;
  pct: number;
  count: number;
}

export interface AllocationOut {
  by_type: AllocationItem[];
  by_currency: AllocationItem[];
  by_account: AllocationItem[];
  by_sector: AllocationItem[];
  by_continent: AllocationItem[];
  total_value_eur: number;
}

export interface ETFHoldingItem {
  symbol: string;
  name: string;
  weight: number;
}

export interface CountryItem {
  code: string;
  name: string;
  weight: number;
}

export interface ETFHoldingOut {
  asset_id: number;
  symbol: string;
  name: string;
  value_eur: number | null;
  holdings: ETFHoldingItem[];
  is_override: boolean;
  countries_override: CountryItem[] | null;
}

export interface DashboardOut {
  summary: PortfolioSummaryOut;
  positions: PositionOut[];
  allocation: AllocationOut;
}

export interface DividendOut {
  id: number;
  date: string;
  asset_id: number;
  symbol: string;
  name: string;
  type: string;
  amount_eur: number;
  account_name: string;
  account_id: number;
}

export interface HoldingPricePoint {
  date: string;
  price: number;
}

export interface HoldingActivityOut {
  id: number;
  type: string;
  date: string;
  quantity: number;
  price: number;
  price_currency: string;
  total_eur: number;
  fee: number;
  account_name: string;
  account_id: number;
}

export interface HoldingAccountOut {
  account_id: number;
  account_name: string;
  quantity: number;
  value_eur: number | null;
  pct: number | null;
}

export interface SectorItem {
  name: string;
  weight: number;
}

export interface HoldingDetailOut {
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  exchange: string;
  isin: string | null;
  quantity: number;
  pmc_eur: number;
  total_invested_eur: number;
  realized_pnl_eur: number;
  current_price: number | null;
  current_price_eur: number | null;
  current_value_eur: number | null;
  unrealized_pnl_eur: number | null;
  unrealized_pnl_pct: number | null;
  change_pct: number | null;
  min_price: number | null;
  max_price: number | null;
  total_fees: number;
  activities_count: number;
  first_buy_date: string | null;
  price_history: HoldingPricePoint[];
  activities: HoldingActivityOut[];
  accounts: HoldingAccountOut[];
  sectors: SectorItem[] | null;
  countries: CountryItem[] | null;
}

export interface RiskMetricsOut {
  period: string;
  trading_days: number;
  annualized_volatility_pct: number;
  max_drawdown_pct: number;
  max_drawdown_start: string | null;
  max_drawdown_end: string | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  twrr_annualized_pct: number;
  best_day_pct: number;
  worst_day_pct: number;
  positive_days_pct: number;
}

export const portfolioService = {
  async getDashboard(period = "ytd"): Promise<DashboardOut> {
    const { data } = await api.get<DashboardOut>("/portfolio/dashboard", { params: { period } });
    return data;
  },

  async getSummary(): Promise<PortfolioSummaryOut> {
    const { data } = await api.get<PortfolioSummaryOut>("/portfolio/summary");
    return data;
  },

  async getPositions(): Promise<PositionOut[]> {
    const { data } = await api.get<PositionOut[]>("/portfolio/positions");
    return data;
  },

  async getPerformance(period: string, accountId?: number): Promise<PerformanceOut> {
    const { data } = await api.get<PerformanceOut>("/portfolio/performance", {
      params: { period, ...(accountId != null ? { account_id: accountId } : {}) },
    });
    return data;
  },

  async getAllocation(): Promise<AllocationOut> {
    const { data } = await api.get<AllocationOut>("/portfolio/allocation");
    return data;
  },

  async getDividends(): Promise<DividendOut[]> {
    const { data } = await api.get<DividendOut[]>("/portfolio/dividends");
    return data;
  },

  async getHoldingDetail(assetId: number): Promise<HoldingDetailOut> {
    const { data } = await api.get<HoldingDetailOut>(`/portfolio/holding/${assetId}`);
    return data;
  },

  async getEtfHoldings(): Promise<ETFHoldingOut[]> {
    const { data } = await api.get<ETFHoldingOut[]>("/portfolio/etf-holdings");
    return data;
  },

  async getRisk(period: string, accountId?: number): Promise<RiskMetricsOut> {
    const { data } = await api.get<RiskMetricsOut>("/portfolio/risk", {
      params: { period, ...(accountId != null ? { account_id: accountId } : {}) },
    });
    return data;
  },

  async getXirr(): Promise<{ xirr_pct: number | null }> {
    const { data } = await api.get<{ xirr_pct: number | null }>("/portfolio/xirr");
    return data;
  },

  async getBenchmark(index: string, period: string): Promise<{ index: string; ticker: string; period: string; series: { date: string; value: number }[] }> {
    const { data } = await api.get("/portfolio/benchmark", { params: { index, period } });
    return data;
  },

  async getCorrelation(period: string): Promise<{ labels: string[]; matrix: number[][]; period: string }> {
    const { data } = await api.get("/portfolio/correlation", { params: { period } });
    return data;
  },

  async getCountryAllocation(): Promise<{
    countries: { code: string; name: string; value_eur: number; pct: number; market_type: "developed" | "emerging" | "other" }[];
    totals: { developed_pct: number; emerging_pct: number; other_pct: number; no_data_pct: number };
  }> {
    const { data } = await api.get("/portfolio/country-allocation");
    return data;
  },
};
