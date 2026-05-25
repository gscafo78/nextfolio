import { api } from "./api";

export type AlertType = "PRICE_ABOVE" | "PRICE_BELOW" | "CHANGE_PCT_UP" | "CHANGE_PCT_DOWN";

export interface AlertOut {
  id: number;
  asset_id: number;
  asset_name: string;
  asset_symbol: string;
  alert_type: AlertType;
  threshold: number;
  is_active: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export interface AlertCreate {
  asset_id: number;
  alert_type: AlertType;
  threshold: number;
}

export interface AlertUpdate {
  is_active?: boolean;
  threshold?: number;
}

export const alertService = {
  async list(): Promise<AlertOut[]> {
    const { data } = await api.get<AlertOut[]>("/alerts");
    return data;
  },

  async create(body: AlertCreate): Promise<AlertOut> {
    const { data } = await api.post<AlertOut>("/alerts", body);
    return data;
  },

  async update(id: number, body: AlertUpdate): Promise<AlertOut> {
    const { data } = await api.patch<AlertOut>(`/alerts/${id}`, body);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/alerts/${id}`);
  },
};
