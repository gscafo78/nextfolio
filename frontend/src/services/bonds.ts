import { api } from "./api";

export type CouponFrequency = "ANNUAL" | "SEMI_ANNUAL" | "QUARTERLY" | "MONTHLY";

export interface BondDetail {
  id: number;
  asset_id: number;
  face_value: number;
  coupon_rate: number;           // decimale (es. 0.0165 per 1,65%)
  coupon_frequency: CouponFrequency;
  first_coupon_date: string;
  maturity_date: string | null;
  issue_date: string | null;
  coupon_per_unit: number;
  enriched_from_bi: boolean;
}

export interface BondDetailCreate {
  face_value?: number;
  coupon_rate: number;
  coupon_frequency: CouponFrequency;
  first_coupon_date: string;
  maturity_date?: string | null;
  issue_date?: string | null;
}

export interface CouponScheduleEntry {
  date: string;
  coupon_per_unit: number;
  total_coupon_eur: number;
  days_until: number;
  already_recorded: boolean;
}

export interface UpcomingCouponEntry {
  asset_id: number;
  asset_name: string;
  isin: string | null;
  date: string;
  coupon_per_unit: number;
  quantity: number;
  total_coupon_eur: number;
  days_until: number;
  already_recorded: boolean;
}

export const FREQUENCY_LABELS: Record<CouponFrequency, string> = {
  ANNUAL:      "Annuale",
  SEMI_ANNUAL: "Semestrale",
  QUARTERLY:   "Trimestrale",
  MONTHLY:     "Mensile",
};

export const bondService = {
  async get(assetId: number): Promise<BondDetail | null> {
    try {
      const { data } = await api.get<BondDetail>(`/assets/${assetId}/bond-detail`);
      return data;
    } catch {
      return null;
    }
  },

  async upsert(assetId: number, body: BondDetailCreate): Promise<BondDetail> {
    const { data } = await api.post<BondDetail>(`/assets/${assetId}/bond-detail`, body);
    return data;
  },

  async enrich(assetId: number): Promise<BondDetail> {
    const { data } = await api.get<{ bond_detail: BondDetail }>(`/assets/${assetId}/bond-detail/enrich`);
    return data.bond_detail;
  },

  async schedule(assetId: number, quantity: number): Promise<CouponScheduleEntry[]> {
    const { data } = await api.get<CouponScheduleEntry[]>(`/assets/${assetId}/coupon-schedule`, {
      params: { quantity },
    });
    return data;
  },

  async upcomingCoupons(days = 365): Promise<UpcomingCouponEntry[]> {
    const { data } = await api.get<UpcomingCouponEntry[]>("/portfolio/upcoming-coupons", {
      params: { days },
    });
    return data;
  },

  async backfillCoupons(): Promise<BackfillSummary> {
    const { data } = await api.post<BackfillSummary>("/bonds/backfill-coupons");
    return data;
  },
};

export interface BackfillDetail {
  asset_id: number;
  asset_name: string;
  isin: string | null;
  coupon_date: string;
  quantity: number;
  amount_eur: number;
  account_id: number;
  created: boolean;
  skipped_reason: string | null;
}

export interface BackfillSummary {
  created_count: number;
  skipped_count: number;
  total_amount_eur: number;
  details: BackfillDetail[];
}
