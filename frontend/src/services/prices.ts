import { api } from "./api";

export interface PriceOut {
  asset_id: number;
  symbol: string;
  price: number;
  prev_close: number | null;
  change_pct: number;
  currency: string;
}

export interface OHLCVOut {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}

export type Period = "1w" | "1mo" | "3mo" | "6mo" | "1y" | "3y" | "5y" | "max";

export const priceService = {
  async getPrice(assetId: number, refresh = false): Promise<PriceOut> {
    const { data } = await api.get<PriceOut>(`/assets/${assetId}/price`, {
      params: { refresh },
    });
    return data;
  },

  async getHistory(assetId: number, period: Period = "1y", source: "db" | "live" = "db"): Promise<OHLCVOut[]> {
    const { data } = await api.get<OHLCVOut[]>(`/assets/${assetId}/history`, {
      params: { period, source },
    });
    return data;
  },

  async backfill(assetId: number, period: Period = "1y"): Promise<void> {
    await api.post(`/assets/${assetId}/backfill`, null, { params: { period } });
  },
};
