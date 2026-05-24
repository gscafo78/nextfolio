import { api } from "./api";

export type AssetType = "STOCK" | "ETF" | "BOND" | "CRYPTO" | "COMMODITY" | "REIT";
export type Exchange = "MIL" | "EuroTLX" | "MOT" | "XETRA" | "NYSE" | "NASDAQ" | "CRYPTO" | "OTHER";
export type TransactionType = "BUY" | "SELL" | "DIVIDEND" | "COUPON" | "FEE" | "INTEREST";
export type AccountType = "BROKERAGE" | "BANK" | "CRYPTO" | "PENSION" | "OTHER";
export type BrokerFormat = "fineco" | "directa" | "degiro";

export interface Asset {
  id: number;
  isin: string | null;
  symbol: string;
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
  currency: string;
}

export interface Transaction {
  id: number;
  account_id: number;
  asset_id: number;
  type: TransactionType;
  date: string;
  quantity: number;
  price: number;
  fee: number;
  currency: string;
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
  fee?: number;
  currency?: string;
  notes?: string;
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

export const accountService = {
  async list(): Promise<Account[]> {
    const { data } = await api.get<Account[]>("/accounts");
    return data;
  },

  async create(body: { name: string; type?: AccountType; broker?: string; currency?: string }): Promise<Account> {
    const { data } = await api.post<Account>("/accounts", body);
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
};
