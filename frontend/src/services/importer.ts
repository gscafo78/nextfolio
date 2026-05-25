import { api } from "./api";

// ── Preview types ─────────────────────────────────────────────────────────────

export interface GfAccountInfo {
  ghostfolio_id: string;
  name: string;
  currency: string;
  broker: string | null;
  is_null: boolean;
  transaction_count: number;
  existing_match: { id: number; name: string } | null;
}

export interface GfAssetInfo {
  ghostfolio_symbol: string;
  name: string;
  currency: string;
  data_source: string;
  is_uuid: boolean;
  has_price_history: boolean;
  price_history_count: number;
  transaction_count: number;
  tx_types: string[];
  suggested_type: string;
  suggested_exchange: string;
  db_match: { id: number; symbol: string; name: string; type: string } | null;
  suggestions: { id: number; symbol: string; name: string; type: string }[];
}

export interface GhostfolioPreview {
  accounts: GfAccountInfo[];
  assets: GfAssetInfo[];
  total_transactions: number;
}

// ── Resolution types ──────────────────────────────────────────────────────────

export interface AccountResolution {
  ghostfolio_id: string;
  action: "create" | "use_existing";
  existing_id?: number;
  name?: string;
  broker?: string;
  currency: string;
}

export interface AssetResolution {
  ghostfolio_symbol: string;
  action: "create" | "use_existing" | "skip";
  existing_id?: number;
  name?: string;
  symbol?: string;
  type?: string;
  exchange?: string;
  currency?: string;
  isin?: string;
  wkn?: string;
  import_price_history?: boolean;
}

export interface ImportResult {
  accounts_created: number;
  assets_created: number;
  price_history_inserted: number;
  transactions_created: number;
  transactions_skipped: number;
  errors: string[];
}

// ── Service ───────────────────────────────────────────────────────────────────

export const importerService = {
  async preview(raw: unknown): Promise<GhostfolioPreview> {
    const { data } = await api.post<GhostfolioPreview>("/import/ghostfolio/preview", { raw });
    return data;
  },

  async execute(
    raw: unknown,
    accounts: AccountResolution[],
    assets: AssetResolution[],
  ): Promise<ImportResult> {
    const { data } = await api.post<ImportResult>("/import/ghostfolio/execute", {
      raw,
      accounts,
      assets,
    });
    return data;
  },
};
