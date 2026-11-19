import { api } from "./api";

export interface IVAFEPosition {
  asset_id: number;
  asset_name: string;
  asset_type: string;
  quantity: number;
  price_eur: number;
  market_value_eur: number;
  ivafe_eur: number;
  price_date: string | null;
}

export interface IVAFEReport {
  year: number;
  total_market_value_eur: number;
  ivafe_eur: number;
  positions: IVAFEPosition[];
  rate: number;
  has_foreign_accounts: boolean;
}

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
  tax_bracket: TaxBracket;
  tax_rate: number;
  is_sostituto_imposta: boolean;
  calculation_method: "PMC" | "FIFO";
}

export type TaxBracket = "standard" | "government_bond" | "fund" | "crypto";

export interface CarryForwardEntry {
  year: number;
  amount: number;
  expires_year: number;
}

export interface AnnualTaxReport {
  year: number;

  // Redditi diversi 26% — importi reali
  gains_standard: number;
  losses_standard: number;
  // Titoli di Stato — importi reali, nello zainetto al 48,08% (govt_weight)
  gains_govt: number;
  losses_govt: number;
  govt_weight: number;
  // ETF/OICR: minus nello zainetto, plus tassate a parte (redditi di capitale)
  losses_funds: number;
  gains_funds: number;
  tax_funds: number;

  // Zainetto unico 26% (importi ponderati)
  taxable_gains_standard: number;
  taxable_losses_standard: number;
  carryforward_applied_standard: number;
  net_taxable_standard: number;
  tax_standard: number;
  new_carryforward_standard: number;
  prior_carryforward_standard: CarryForwardEntry[];

  // Cripto-attività
  gains_crypto: number;
  losses_crypto: number;
  crypto_rate: number;
  carryforward_applied_crypto: number;
  net_taxable_crypto: number;
  tax_crypto: number;
  new_carryforward_crypto: number;
  prior_carryforward_crypto: CarryForwardEntry[];

  dividends_eur: number;
  coupons_govt_eur: number;
  coupons_standard_eur: number;
  interests_eur: number;

  total_tax_due: number;

  events: TaxEvent[];

  administered_gains_standard: number;
  administered_losses_standard: number;
  administered_gains_govt: number;
  administered_losses_govt: number;
  administered_gains_funds: number;
  administered_losses_funds: number;
  administered_gains_crypto: number;
  administered_losses_crypto: number;
  administered_taxable_gains: number;
  administered_taxable_losses: number;
  administered_tax_standard: number;
  administered_tax_funds: number;
  administered_tax_crypto: number;
  administered_dividends_eur: number;
  administered_income_tax: number;
  administered_total_tax: number;

  declaratory_gains_standard: number;
  declaratory_losses_standard: number;
  declaratory_gains_govt: number;
  declaratory_losses_govt: number;
  declaratory_gains_funds: number;
  declaratory_losses_funds: number;
  declaratory_gains_crypto: number;
  declaratory_losses_crypto: number;
  declaratory_taxable_gains: number;
  declaratory_taxable_losses: number;
  declaratory_tax_standard: number;
  declaratory_tax_funds: number;
  declaratory_tax_crypto: number;
  declaratory_dividends_eur: number;
  declaratory_income_tax: number;
  declaratory_total_tax: number;

  income_tax_eur: number;
  has_declaratory_accounts: boolean;
  ivafe: IVAFEReport;
}

export interface SimulateSellOut {
  asset_name: string;
  asset_type: string;
  quantity: number;
  current_price_eur: number;
  proceeds_eur: number;
  cost_basis_eur: number;
  gain_loss_eur: number;
  tax_bracket: TaxBracket;
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
