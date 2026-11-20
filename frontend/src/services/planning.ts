import { api } from "./api";
import type { AllocationOut } from "./portfolio";

export type PlanAssetType = "STOCK" | "ETF" | "BOND" | "CRYPTO" | "COMMODITY" | "REIT" | "OTHER";

export interface SearchResult {
  source: "local" | "yahoo";
  asset_id: number | null;
  symbol: string | null;
  ticker: string | null;
  name: string;
  isin: string | null;
  type: PlanAssetType;
  exchange: string | null;
  exchange_label: string | null;
  currency: string | null;
  in_portfolio: boolean;
  in_watchlist: boolean;
}

export interface SecurityCard {
  source: "local" | "yahoo";
  asset_id: number | null;
  symbol: string | null;
  ticker: string | null;
  name: string;
  isin: string | null;
  type: PlanAssetType;
  currency: string | null;
  price: number | null;
  price_eur: number | null;
  change_pct: number | null;
  asset_class: string;
  asset_class_weights: Record<string, number>;
  currency_exposure: Record<string, number>;
  sectors: { name: string; weight: number }[];
  countries: { code?: string; name?: string; weight: number }[];
  holdings: { symbol?: string; name?: string; weight?: number }[];
  history: { date: string; close: number }[];
  metrics: {
    return_1y_pct: number | null;
    return_3y_ann_pct: number | null;
    return_5y_ann_pct: number | null;
    volatility_1y_pct: number | null;
    max_drawdown_1y_pct: number | null;
    first_date: string | null;
  };
  in_portfolio: boolean;
  in_watchlist: boolean;
}

/** Acquisto ipotetico (nel carrello, in uno scenario o inviato alla simulazione). */
export interface PlanItem {
  id?: number | null;
  asset_id: number | null;
  symbol: string | null;
  name: string;
  type: PlanAssetType;
  isin?: string | null;
  amount_eur: number | null;
  quantity: number | null;
  price_eur?: number | null;
  fee_eur: number;
  account_id: number | null;
}

export interface RuleChange {
  key: string;
  name: string;
  category: string;
  before_status: string | null;
  after_status: string;
  before_actual: number | null;
  after_actual: number | null;
  changed: boolean;
}

export interface SimulationResult {
  items: {
    name: string; asset_id: number | null; symbol: string | null; price_eur: number; quantity: number;
    amount_eur: number; fee_eur: number; account_id: number | null; asset_class: string;
  }[];
  allocation_before: AllocationOut;
  allocation_after: AllocationOut;
  xray_before: { score: number };
  xray_after: { score: number };
  rule_changes: RuleChange[];
  weights: { name: string; before_pct: number; after_pct: number; delta_pct: number; new: boolean }[];
  total_before_eur: number;
  total_after_eur: number;
  invested_eur: number;
  fees_eur: number;
  cash_before_eur: number;
  cash_after_eur: number;
  warnings: string[];
}

export interface Scenario {
  id: number;
  name: string;
  notes: string | null;
  use_cash: boolean;
  status: "draft" | "executed";
  created_at: string;
  updated_at: string;
  executed_at: string | null;
  items: PlanItem[];
}

export interface ExecuteItem {
  item_id: number;
  quantity: number;
  price: number;
  price_currency?: string;
  exchange_rate?: number;
  fee: number;
  account_id?: number | null;
}


export type AssetClassKey = "EQUITY" | "BOND" | "MONEY_MARKET" | "CRYPTO" | "OTHER";
export const ASSET_CLASS_KEYS: AssetClassKey[] = ["EQUITY", "BOND", "MONEY_MARKET", "CRYPTO", "OTHER"];

export interface PreferredInstrument {
  asset_id: number | null;
  symbol: string | null;
  name: string;
  type: PlanAssetType;
  weight: number;
}

export interface Targets {
  weights: Partial<Record<AssetClassKey, number>>;   // percentuali, somma 100
  tolerance_pct: number;
  preferred: Partial<Record<AssetClassKey, PreferredInstrument[]>>;
}

export interface DriftRow {
  class: AssetClassKey; label: string; current_pct: number; target_pct: number; delta_pct: number; out_of_band: boolean;
}

export interface ContributionPlan {
  amount_eur: number;
  from_cash: boolean;
  per_class: { class: AssetClassKey; label: string; target_pct: number; before_pct: number; after_pct: number; allocated_eur: number }[];
  orders: { name: string; asset_class: string; amount_eur: number; quantity: number; price_eur: number; fee_eur: number;
    asset_id: number | null; symbol: string | null; type: PlanAssetType }[];
  uninvested_eur: number;
  warnings: string[];
}

export interface Assumptions {
  returns_pct?: Partial<Record<AssetClassKey, number>>;
  volatility_pct?: Partial<Record<AssetClassKey, number>>;
  weights_pct?: Partial<Record<AssetClassKey, number>> | null;
}

export interface Projection {
  months: number;
  probability: number;
  median_final: number;
  p10_final: number;
  p90_final: number;
  total_contributed: number;
  required_monthly_80: number | null;
  yearly: { year: number; p10: number; p25: number; p50: number; p75: number; p90: number; contributed: number }[];
  initial_amount: number;
  weights_pct: Partial<Record<AssetClassKey, number>>;
  expected_return_pct: number;
  volatility_pct: number;
}

export interface FireResult {
  target_capital: number;
  years_to_fire_median: number | null;
  years_to_fire_p10: number | null;
  success_probability: number;
  sustainable_withdrawal_90: number;
  current_amount: number;
  expected_return_pct: number;
  volatility_pct: number;
}

export interface Goal {
  id?: number;
  name: string;
  target_amount: number;
  target_date: string;
  monthly_contribution: number;
  initial_amount: number | null;
  inflation_pct: number;
}


export interface SecurityRef { asset_id?: number | null; symbol?: string | null; name?: string | null; type?: PlanAssetType }

export interface TaxOverview {
  year: number;
  pool_standard: { year: number; amount: number; expires_year: number; expiring: boolean }[];
  pool_crypto: { year: number; amount: number; expires_year: number; expiring: boolean }[];
  expiring_standard: number;
  expiring_crypto: number;
  use_losses: { asset_id: number; name: string; account: string; pool: string; quantity: number; price_eur: number;
    proceeds_eur: number; gain_eur: number; losses_used_eur: number; tax_saved_eur: number }[];
  harvest_losses: { asset_id: number; name: string; account: string; pool: string; quantity: number; price_eur: number;
    proceeds_eur: number; loss_eur: number; gains_offset_eur: number; tax_saved_eur: number }[];
  year_tax: { capital_gains_tax_eur: number; income_tax_eur: number; wealth_tax_eur: number; total_eur: number;
    net_taxable_standard_eur: number; gains_funds_eur: number };
  notes: string[];
}

export interface SalesSimulation {
  year: number;
  sales: { asset_id: number; name: string; quantity: number; proceeds_eur: number; cost_eur: number;
    gain_loss_eur: number; category: string; tax_rate: number }[];
  before: Record<string, number>;
  after: Record<string, number>;
  delta_tax_eur: number;
  proceeds_eur: number;
}

export interface CompareResult {
  dates: string[];
  normalized: Record<string, number[]>;
  metrics: Record<string, { window_return_pct: number; window_ann_return_pct: number | null; volatility_1y_pct: number | null;
    max_drawdown_1y_pct: number | null; return_1y_pct: number | null; return_3y_ann_pct: number | null }>;
  correlation: Record<string, Record<string, number>>;
  start: string | null;
  end: string | null;
  names: Record<string, string>;
  overlaps: { a: string; b: string; overlap_pct: number; common: { name: string; weight_a: number; weight_b: number }[] }[];
  notes: string[];
}

export interface BacktestRun {
  series: { date: string; value: number; invested: number }[];
  metrics: { start?: string; end?: string; final_value?: number; invested?: number; twrr_pct?: number;
    twrr_ann_pct?: number | null; volatility_pct?: number | null; max_drawdown_pct?: number; rebalances?: number };
  warnings: string[];
}

const toBody = (items: PlanItem[]) =>
  items.map((i) => ({
    asset_id: i.asset_id,
    symbol: i.asset_id ? null : i.symbol,
    name: i.name,
    type: i.type,
    isin: i.isin ?? null,
    amount_eur: i.amount_eur,
    quantity: i.quantity,
    price_eur: i.price_eur ?? null,
    fee_eur: i.fee_eur,
    account_id: i.account_id,
  }));

export const planningService = {
  async search(q: string, type?: PlanAssetType): Promise<SearchResult[]> {
    const { data } = await api.get<SearchResult[]>("/planning/search", { params: { q, type } });
    return data;
  },

  async security(r: { asset_id?: number | null; symbol?: string | null; type?: string; name?: string }): Promise<SecurityCard> {
    const params = r.asset_id ? { asset_id: r.asset_id } : { symbol: r.symbol, type: r.type, name: r.name };
    const { data } = await api.get<SecurityCard>("/planning/security", { params });
    return data;
  },

  async importSecurity(r: { symbol: string; name: string; type: string; isin?: string | null }): Promise<{ asset_id: number }> {
    const { data } = await api.post<{ asset_id: number }>("/planning/security/import", r);
    return data;
  },

  async simulate(items: PlanItem[], use_cash: boolean): Promise<SimulationResult> {
    const { data } = await api.post<SimulationResult>("/planning/simulate", { items: toBody(items), use_cash });
    return data;
  },

  async scenarios(): Promise<Scenario[]> {
    const { data } = await api.get<Scenario[]>("/planning/scenarios");
    return data;
  },

  async scenario(id: number): Promise<{ scenario: Scenario; simulation: SimulationResult | null }> {
    const { data } = await api.get(`/planning/scenarios/${id}`);
    return data;
  },

  async saveScenario(s: { id?: number; name: string; notes?: string | null; use_cash: boolean; items: PlanItem[] }): Promise<Scenario> {
    const body = { name: s.name, notes: s.notes ?? null, use_cash: s.use_cash, items: toBody(s.items) };
    const { data } = s.id
      ? await api.put<Scenario>(`/planning/scenarios/${s.id}`, body)
      : await api.post<Scenario>("/planning/scenarios", body);
    return data;
  },

  async deleteScenario(id: number): Promise<void> {
    await api.delete(`/planning/scenarios/${id}`);
  },

  async compare(ids: number[]): Promise<{ scenario: Scenario; simulation: SimulationResult | null }[]> {
    const { data } = await api.get("/planning/scenarios/compare", { params: { ids: ids.join(",") } });
    return data;
  },

  async execute(id: number, body: { account_id: number; date: string; items: ExecuteItem[] }) {
    const { data } = await api.post<{ created: number[]; skipped_rows: number[] }>(`/planning/scenarios/${id}/execute`, body);
    return data;
  },

  async targets(): Promise<Targets | null> {
    const { data } = await api.get<Targets | null>("/planning/targets");
    return data;
  },

  async saveTargets(t: Targets): Promise<Targets> {
    const { data } = await api.put<Targets>("/planning/targets", t);
    return data;
  },

  async drift(): Promise<{ configured: boolean; tolerance_pct: number | null; classes: DriftRow[]; out_of_band: boolean }> {
    const { data } = await api.get("/planning/drift");
    return data;
  },

  async contribution(body: { amount_eur?: number | null; from_cash: boolean; whole_units: boolean; min_order_eur: number; fee_per_order_eur: number }): Promise<ContributionPlan> {
    const { data } = await api.post<ContributionPlan>("/planning/contribution", body);
    return data;
  },

  async projection(body: Assumptions & { target_amount: number; target_date: string; monthly_contribution: number; initial_amount?: number | null; inflation_pct: number }): Promise<Projection> {
    const { data } = await api.post<Projection>("/planning/projection", body);
    return data;
  },

  async fire(body: Assumptions & { annual_expenses: number; withdrawal_rate_pct: number; monthly_contribution: number; current_amount?: number | null; inflation_pct: number; horizon_years: number }): Promise<FireResult> {
    const { data } = await api.post<FireResult>("/planning/fire", body);
    return data;
  },

  async goals(): Promise<Goal[]> {
    const { data } = await api.get<Goal[]>("/planning/goals");
    return data;
  },

  async saveGoal(g: Goal): Promise<Goal> {
    const { data } = g.id ? await api.put<Goal>(`/planning/goals/${g.id}`, g) : await api.post<Goal>("/planning/goals", g);
    return data;
  },

  async deleteGoal(id: number): Promise<void> {
    await api.delete(`/planning/goals/${id}`);
  },

  async taxOverview(): Promise<TaxOverview> {
    const { data } = await api.get<TaxOverview>("/planning/tax/overview");
    return data;
  },

  async simulateSales(sales: { asset_id: number; quantity: number; account_id?: number | null; price_eur?: number | null }[]): Promise<SalesSimulation> {
    const { data } = await api.post<SalesSimulation>("/planning/tax/simulate-sales", { sales });
    return data;
  },

  async compareSecurities(securities: SecurityRef[], years: number): Promise<CompareResult> {
    const { data } = await api.post<CompareResult>("/planning/compare", { securities, years });
    return data;
  },

  async backtest(body: { components: (SecurityRef & { weight: number })[]; years: number; initial_amount: number;
    monthly_contribution: number; rebalance: "none" | "annual" | "threshold"; benchmark?: SecurityRef | null }): Promise<{
    names: Record<string, string>; weights_pct: Record<string, number>; model: BacktestRun; benchmark: (BacktestRun & { name: string }) | null }> {
    const { data } = await api.post("/planning/backtest", body);
    return data;
  },
};
