import { api } from "./api";

export type AssetType = "STOCK" | "ETF" | "BOND" | "CRYPTO" | "COMMODITY" | "REIT";
export type Exchange = "MIL" | "EuroTLX" | "MOT" | "XETRA" | "NYSE" | "NASDAQ" | "CRYPTO" | "OTHER";
export type TransactionType = "BUY" | "SELL" | "DIVIDEND" | "COUPON" | "FEE" | "INTEREST";
export type AccountType = "BROKERAGE" | "BANK" | "CRYPTO" | "PENSION" | "OTHER";
export type BrokerFormat = "fineco" | "directa" | "degiro" | "ibkr";

export interface Asset {
  id: number;
  isin: string | null;
  wkn: string | null;
  symbol: string;
  yahoo_ticker: string | null;
  name: string;
  type: AssetType;
  exchange: Exchange;
  currency: string;
  sector: string | null;
}

export interface Account {
  id: number;
  name: string;
  type: AccountType;
  broker: string | null;
  url: string | null;
  currency: string;
  transaction_count: number;
}

export interface Transaction {
  id: number;
  account_id: number;
  asset_id: number;
  type: TransactionType;
  date: string;
  quantity: number;
  price: number;
  price_currency: string;
  exchange_rate: number;
  fee: number;
  fee_currency: string;
  total_eur: number;
  notes: string | null;
  asset: Asset;
}

export interface TransactionCreate {
  account_id: number;
  asset_id: number;
  type: TransactionType;
  date: string;
  quantity: number;
  price: number;
  price_currency?: string;
  exchange_rate?: number;
  fee?: number;
  fee_currency?: string;
  notes?: string;
}

export interface ExchangeRate {
  from_currency: string;
  to_currency: string;
  rate: number;
  date: string;
}

export const transactionService = {
  async list(params?: {
    account_id?: number;
    type?: TransactionType;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<Transaction[]> {
    const { data } = await api.get<Transaction[]>("/transactions", { params });
    return data;
  },

  async create(body: TransactionCreate): Promise<Transaction> {
    const { data } = await api.post<Transaction>("/transactions", body);
    return data;
  },

  async update(id: number, body: Partial<Omit<TransactionCreate, "asset_id">>): Promise<Transaction> {
    const { data } = await api.put<Transaction>(`/transactions/${id}`, body);
    return data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/transactions/${id}`);
  },

  async importCsv(accountId: number, broker: BrokerFormat, file: File): Promise<Transaction[]> {
    const form = new FormData();
    form.append("account_id", String(accountId));
    form.append("broker", broker);
    form.append("file", file);
    const { data } = await api.post<Transaction[]>("/transactions/import-csv", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
};

export const fxService = {
  async getRate(fromCurrency: string, date?: string): Promise<ExchangeRate> {
    const { data } = await api.get<ExchangeRate>("/fx/rate", {
      params: { from_currency: fromCurrency, to_currency: "EUR", on_date: date },
    });
    return data;
  },
};

export const accountService = {
  async list(): Promise<Account[]> {
    const { data } = await api.get<Account[]>("/accounts");
    return data;
  },

  async create(body: { name: string; type?: AccountType; broker?: string; url?: string; currency?: string }): Promise<Account> {
    const { data } = await api.post<Account>("/accounts", body);
    return data;
  },

  async update(id: number, body: { name?: string; type?: AccountType; broker?: string; url?: string; currency?: string }): Promise<Account> {
    const { data } = await api.patch<Account>(`/accounts/${id}`, body);
    return data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/accounts/${id}`);
  },
};

export const assetService = {
  async search(q: string): Promise<Asset[]> {
    const { data } = await api.get<Asset[]>("/assets/search", { params: { q } });
    return data;
  },

  async update(id: number, body: { yahoo_ticker?: string | null; symbol?: string; name?: string; exchange?: Exchange; isin?: string | null; wkn?: string | null }): Promise<Asset> {
    const { data } = await api.patch<Asset>(`/assets/${id}`, body);
    return data;
  },

  async create(body: { isin?: string; symbol: string; name: string; type: AssetType; exchange: Exchange; currency: string }): Promise<Asset> {
    const { data } = await api.post<Asset>("/assets", body);
    return data;
  },
};
