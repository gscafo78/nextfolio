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
  total_value_eur: number;
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
}

export const portfolioService = {
  async getDashboard(): Promise<DashboardOut> {
    const { data } = await api.get<DashboardOut>("/portfolio/dashboard");
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
};
