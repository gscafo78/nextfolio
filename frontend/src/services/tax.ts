import { api } from "./api";

export interface TaxEvent {
  date: string;
  asset_id: number;
  asset_name: string;
  asset_type: string;
  tx_type: "SELL" | "DIVIDEND" | "COUPON" | "INTEREST";
  quantity: number | null;
  proceeds_eur: number;
  cost_eur: number | null;
  gain_loss_eur: number;
  tax_bracket: "standard" | "government_bond";
  tax_rate: number;
}

export interface CarryForwardEntry {
  year: number;
  amount: number;
  expires_year: number;
}

export interface AnnualTaxReport {
  year: number;

  gains_standard: number;
  losses_standard: number;
  carryforward_applied_standard: number;
  net_taxable_standard: number;
  tax_standard: number;

  gains_govt: number;
  losses_govt: number;
  carryforward_applied_govt: number;
  net_taxable_govt: number;
  tax_govt: number;

  dividends_eur: number;
  coupons_govt_eur: number;
  coupons_standard_eur: number;
  interests_eur: number;

  total_tax_due: number;

  new_carryforward_standard: number;
  new_carryforward_govt: number;

  prior_carryforward_standard: CarryForwardEntry[];
  prior_carryforward_govt: CarryForwardEntry[];

  events: TaxEvent[];
}

export interface SimulateSellOut {
  asset_name: string;
  asset_type: string;
  quantity: number;
  current_price_eur: number;
  proceeds_eur: number;
  cost_basis_eur: number;
  gain_loss_eur: number;
  tax_bracket: "standard" | "government_bond";
  tax_rate: number;
  estimated_tax_eur: number;
  net_proceeds_eur: number;
}

export const taxService = {
  async getYears(): Promise<number[]> {
    const { data } = await api.get<number[]>("/tax/years");
    return data;
  },

  async getReport(year: number): Promise<AnnualTaxReport> {
    const { data } = await api.get<AnnualTaxReport>("/tax/report", { params: { year } });
    return data;
  },

  async simulateSell(assetId: number, quantity: number): Promise<SimulateSellOut> {
    const { data } = await api.get<SimulateSellOut>("/tax/simulate", {
      params: { asset_id: assetId, quantity },
    });
    return data;
  },
};
