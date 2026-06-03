import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { X, TrendingUp, TrendingDown, Pencil, CalendarClock, CheckCircle2, Clock, Sparkles, Settings } from "lucide-react";
import { format, parseISO } from "date-fns";
import { useTranslation } from "react-i18next";
import { portfolioService } from "@/services/portfolio";
import { accountService } from "@/services/transactions";
import { AccountFavicon } from "@/components/AccountFavicon";
import { AssetEditModal } from "./AssetEditModal";
import { useZenMode } from "@/context/ThemeContext";
import { getIntlLocale, getDateFnsLocale } from "@/utils/format";
import i18n from "@/i18n";
import { useQueryClient } from "@tanstack/react-query";
import { bondService, type BondDetail, type BondDetailCreate, type CouponFrequency, type CouponScheduleEntry, FREQUENCY_LABELS } from "@/services/bonds";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, d = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtSign(v: number, d = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: d, maximumFractionDigits: d, signDisplay: "always" });
}
function color(v: number | null) {
  if (v === null) return "text-gray-400";
  return v >= 0 ? "text-green-600" : "text-red-600";
}

const TX_BADGE: Record<string, string> = {
  BUY: "bg-green-50 text-green-700",
  SELL: "bg-red-50 text-red-700",
  DIVIDEND: "bg-blue-50 text-blue-700",
  COUPON: "bg-blue-50 text-blue-700",
  FEE: "bg-gray-100 text-gray-600",
  INTEREST: "bg-blue-50 text-blue-700",
};

type Tab = "overview" | "activities" | "accounts" | "coupons";

// ── Modal ─────────────────────────────────────────────────────────────────────

export function HoldingDetailModal({ assetId, onClose }: { assetId: number; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [showEdit, setShowEdit] = useState(false);
  const [editingBond, setEditingBond] = useState(false);
  const [bondForm, setBondForm] = useState<BondDetailCreate>({
    face_value: 100, coupon_rate: 0, coupon_frequency: "SEMI_ANNUAL",
    first_coupon_date: "", maturity_date: "", issue_date: "",
  });
  const [enriching, setEnriching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [bondMsg, setBondMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const zenMode = useZenMode();
  const zen = (v: string) => zenMode ? "•••••" : v;
  const { t, i18n } = useTranslation();
  const dfLocale = getDateFnsLocale(i18n.language);
  const qc = useQueryClient();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["holding-detail", assetId],
    queryFn: () => portfolioService.getHoldingDetail(assetId),
    staleTime: 60_000,
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
    staleTime: 300_000,
  });
  const accountUrlById = Object.fromEntries(accounts.map((a) => [a.id, a.url]));

  const isBond = data?.asset_type === "BOND";

  const { data: bondDetail } = useQuery<BondDetail | null>({
    queryKey: ["bond-detail", assetId],
    queryFn: () => bondService.get(assetId),
    enabled: isBond,
    staleTime: 300_000,
  });

  const { data: couponSchedule = [] } = useQuery<CouponScheduleEntry[]>({
    queryKey: ["coupon-schedule", assetId, data?.quantity],
    queryFn: () => bondService.schedule(assetId, data?.quantity ?? 1),
    enabled: isBond && !!bondDetail && !!data?.quantity,
    staleTime: 300_000,
  });

  const openBondEdit = () => {
    if (bondDetail) {
      setBondForm({
        face_value: bondDetail.face_value,
        coupon_rate: bondDetail.coupon_rate * 100,    // decimale → %
        coupon_frequency: bondDetail.coupon_frequency,
        first_coupon_date: bondDetail.first_coupon_date,
        maturity_date: bondDetail.maturity_date ?? "",
        issue_date: bondDetail.issue_date ?? "",
      });
    }
    setBondMsg(null);
    setEditingBond(true);
  };

  const handleEnrichModal = async () => {
    if (!data?.isin) return;
    setEnriching(true);
    setBondMsg(null);
    try {
      const bd = await bondService.enrich(assetId);
      setBondForm({
        face_value: bd.face_value,
        coupon_rate: bd.coupon_rate * 100,
        coupon_frequency: bd.coupon_frequency,
        first_coupon_date: bd.first_coupon_date,
        maturity_date: bd.maturity_date ?? "",
        issue_date: bd.issue_date ?? "",
      });
      qc.invalidateQueries({ queryKey: ["bond-detail", assetId] });
      qc.invalidateQueries({ queryKey: ["coupon-schedule", assetId] });
      qc.invalidateQueries({ queryKey: ["upcoming-coupons"] });
      setBondMsg({ type: "ok", text: "Dati caricati da Borsa Italiana" });
      setEditingBond(false);
    } catch {
      setBondMsg({ type: "err", text: "Borsa Italiana non disponibile — inserisci manualmente" });
    } finally {
      setEnriching(false);
    }
  };

  const handleSaveBond = async () => {
    if (!bondForm.first_coupon_date || bondForm.coupon_rate <= 0) {
      setBondMsg({ type: "err", text: "Inserisci tasso e data prima cedola" });
      return;
    }
    setSaving(true);
    setBondMsg(null);
    try {
      await bondService.upsert(assetId, {
        ...bondForm,
        coupon_rate: bondForm.coupon_rate / 100,   // % → decimale
        maturity_date: bondForm.maturity_date || null,
        issue_date: bondForm.issue_date || null,
      });
      qc.invalidateQueries({ queryKey: ["bond-detail", assetId] });
      qc.invalidateQueries({ queryKey: ["coupon-schedule", assetId] });
      qc.invalidateQueries({ queryKey: ["upcoming-coupons"] });
      setBondMsg({ type: "ok", text: "Dettagli cedola salvati" });
      setEditingBond(false);
    } catch {
      setBondMsg({ type: "err", text: "Errore durante il salvataggio" });
    } finally {
      setSaving(false);
    }
  };

  const chartData = (data?.price_history ?? []).map((p, i, arr) => {
    const year = String(p.date).slice(0, 4);
    const prevYear = i > 0 ? String(arr[i - 1].date).slice(0, 4) : null;
    return { ...p, dateLabel: year !== prevYear ? year : "" };
  });
  const isPositive = (data?.unrealized_pnl_eur ?? 0) >= 0;
  const chartColor = isPositive ? "#10b981" : "#ef4444";

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-stretch md:justify-end">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      {/* Panel: bottom sheet on mobile, side panel on desktop */}
      <div className="relative z-10 h-[88vh] md:h-full w-full md:max-w-[440px] bg-white flex flex-col shadow-2xl md:border-l border-t md:border-t-0 border-gray-200 overflow-hidden rounded-t-2xl md:rounded-none">

        {/* Drag handle (mobile only) */}
        <div className="md:hidden flex justify-center pt-3 pb-1 flex-shrink-0">
          <div className="w-10 h-1 rounded-full bg-gray-200" />
        </div>

        {/* Header */}
        <div className="px-6 pt-3 md:pt-5 pb-4 border-b border-gray-100 flex-shrink-0">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              {data && (
                <span className="inline-block text-xs font-medium text-brand-600 bg-brand-50 rounded px-2 py-0.5 mb-1">
                  {data.asset_type} · {data.exchange}
                </span>
              )}
              <h2 className="text-base font-bold text-gray-900 leading-tight truncate">
                {data?.name ?? t("common.loading")}
              </h2>
              {data?.isin && <p className="text-xs text-gray-400 mt-0.5">{data.isin}</p>}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowEdit(true)}
                title={t("holdingDetail.editTitle")}
                className="flex-shrink-0 p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                onClick={onClose}
                className="flex-shrink-0 p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Valore corrente */}
          {data?.current_value_eur != null && (
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-3xl font-bold text-gray-900">
                {zen(`€ ${fmt(data.current_value_eur)}`)}
              </span>
              {data.change_pct != null && (
                <span className={`flex items-center gap-1 text-sm font-semibold ${color(data.change_pct)}`}>
                  {data.change_pct >= 0
                    ? <TrendingUp className="w-3.5 h-3.5" />
                    : <TrendingDown className="w-3.5 h-3.5" />}
                  {fmtSign(data.change_pct)}%
                </span>
              )}
            </div>
          )}
          {isLoading && <div className="mt-3 h-9 w-40 bg-gray-100 rounded-lg animate-pulse" />}
        </div>

        {isError && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-red-500">{t("holdingDetail.loadError")}</p>
          </div>
        )}

        {data && (
          <>
            {/* Chart */}
            <div className="flex-shrink-0 px-0 py-0 border-b border-gray-100" style={{ height: 180 }}>
              {chartData.length >= 2 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="hd-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={chartColor} stopOpacity={0.12} />
                        <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="dateLabel"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      width={42}
                      domain={["auto", "auto"]}
                    />
                    {data.pmc_eur > 0 && (
                      <ReferenceLine
                        y={data.pmc_eur}
                        stroke="#3b82f6"
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        label={{ value: "PMC", position: "right", fontSize: 10, fill: "#3b82f6" }}
                      />
                    )}
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                      formatter={(v: number) => [`${fmt(v, 2)} ${data.currency}`, t("common.price")]}
                      labelFormatter={(l) => l}
                    />
                    <Area
                      type="monotone"
                      dataKey="price"
                      stroke={chartColor}
                      strokeWidth={2}
                      fill="url(#hd-grad)"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-gray-400 px-6 text-center">
                  {t("holdingDetail.noPriceHistory")}
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-100 flex-shrink-0 px-2">
              {(["overview", "activities", "accounts", ...(isBond ? ["coupons"] : [])] as Tab[]).map((tabKey) => (
                <button
                  key={tabKey}
                  onClick={() => setTab(tabKey)}
                  className={`px-3 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
                    tab === tabKey
                      ? "border-brand-600 text-brand-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {tabKey === "overview" ? t("holdingDetail.overview")
                    : tabKey === "activities" ? t("holdingDetail.activities")
                    : tabKey === "accounts" ? t("holdingDetail.accounts")
                    : "📅 Cedole"}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto">

              {/* ── Overview ── */}
              {tab === "overview" && (
                <div className="p-5 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <StatCard
                      label={t("holdingDetail.changeLabel")}
                      value={data.unrealized_pnl_eur != null ? zen(`€ ${fmtSign(data.unrealized_pnl_eur)}`) : "—"}
                      positive={data.unrealized_pnl_eur != null ? data.unrealized_pnl_eur >= 0 : undefined}
                    />
                    <StatCard
                      label={t("holdingDetail.performance")}
                      value={data.unrealized_pnl_pct != null ? `${fmtSign(data.unrealized_pnl_pct)} %` : "—"}
                      positive={data.unrealized_pnl_pct != null ? data.unrealized_pnl_pct >= 0 : undefined}
                    />
                    <StatCard
                      label={t("holdingDetail.avgCost")}
                      value={`${fmt(data.pmc_eur, 4)} ${data.currency}`}
                    />
                    <StatCard
                      label={t("holdingDetail.marketPrice")}
                      value={data.current_price != null ? `${fmt(data.current_price, 4)} ${data.currency}` : "—"}
                    />
                    <StatCard
                      label={t("holdingDetail.minPrice")}
                      value={data.min_price != null ? `${fmt(data.min_price, 4)} ${data.currency}` : "—"}
                    />
                    <StatCard
                      label={t("holdingDetail.maxPrice")}
                      value={data.max_price != null ? `${fmt(data.max_price, 4)} ${data.currency}` : "—"}
                      positive={data.max_price != null && data.current_price != null && data.current_price >= data.max_price * 0.99 ? true : undefined}
                    />
                    <StatCard
                      label={t("common.quantity")}
                      value={data.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 6 })}
                    />
                    <StatCard
                      label={t("holdingDetail.totalInvested")}
                      value={zen(`€ ${fmt(data.total_invested_eur)}`)}
                    />
                    <StatCard
                      label={t("holdingDetail.totalFees")}
                      value={zen(`€ ${fmt(data.total_fees)}`)}
                    />
                    <StatCard
                      label={t("holdingDetail.activities")}
                      value={String(data.activities_count)}
                    />
                    {data.realized_pnl_eur !== 0 && (
                      <StatCard
                        label={t("holdingDetail.realizedPnl")}
                        value={zen(`€ ${fmtSign(data.realized_pnl_eur)}`)}
                        positive={data.realized_pnl_eur >= 0}
                      />
                    )}
                    {data.first_buy_date && (
                      <StatCard
                        label={t("holdingDetail.firstActivity")}
                        value={format(parseISO(String(data.first_buy_date)), "dd MMM yyyy", { locale: dfLocale })}
                      />
                    )}
                    <StatCard label={t("holdingDetail.assetClass")} value={data.asset_type} />
                    <StatCard label={t("holdingDetail.exchange")} value={data.exchange} />
                  </div>

                  {/* Settori */}
                  {data.sectors && data.sectors.length > 0 && (
                    <WeightList title={t("holdingDetail.sectors")} items={data.sectors.map(s => ({ label: s.name, weight: s.weight }))} />
                  )}

                  {/* Paesi */}
                  {data.countries && data.countries.length > 0 && (
                    <WeightList title={t("holdingDetail.countries")} items={data.countries.map(c => ({ label: c.name || c.code, weight: c.weight }))} />
                  )}
                </div>
              )}

              {/* ── Activities ── */}
              {tab === "activities" && (
                <div className="divide-y divide-gray-50">
                  {data.activities.length === 0 ? (
                    <p className="p-8 text-sm text-gray-400 text-center">{t("holdingDetail.noActivities")}</p>
                  ) : data.activities.map((a) => (
                    <div key={a.id} className="px-5 py-3.5 flex items-start justify-between gap-3 hover:bg-gray-50 transition-colors">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${TX_BADGE[a.type] ?? "bg-gray-100 text-gray-600"}`}>
                            {t(`transactions.types.${a.type}`, { defaultValue: a.type })}
                          </span>
                          <span className="text-xs text-gray-400">
                            {format(parseISO(String(a.date)), "dd MMM yyyy", { locale: dfLocale })}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {a.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 6 })} ×{" "}
                          {fmt(a.price, 4)} {a.price_currency}
                          {a.fee > 0 && <span className="text-gray-400"> · fee {zen(`€ ${fmt(a.fee)}`)}</span>}
                        </p>
                        <p className="text-xs text-gray-400 flex items-center gap-1">
                          <AccountFavicon url={accountUrlById[a.account_id]} size={3} />
                          {a.account_name}
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-gray-800 whitespace-nowrap">
                        {zen(`€ ${fmt(a.total_eur)}`)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Cedole ── */}
              {tab === "coupons" && isBond && (
                <div className="p-5 space-y-4">

                  {/* ── Messaggio feedback ── */}
                  {bondMsg && (
                    <div className={`rounded-lg px-4 py-2 text-sm ${bondMsg.type === "ok" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                      {bondMsg.text}
                    </div>
                  )}

                  {/* ── Caso A: nessun bond_detail — form di configurazione ── */}
                  {!bondDetail && !editingBond && (
                    <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-5 text-center space-y-3">
                      <p className="text-sm text-amber-800 font-medium">Cedole non ancora configurate per questo BTP</p>
                      <p className="text-xs text-amber-600">Configura i parametri cedola per vedere il calendario automatico e ricevere notifiche alle scadenze.</p>
                      <div className="flex justify-center gap-2 flex-wrap">
                        {data?.isin && (
                          <button
                            onClick={handleEnrichModal}
                            disabled={enriching}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 px-3 py-1.5 text-xs font-medium text-white transition-colors"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                            {enriching ? "Carico…" : "Carica da Borsa Italiana"}
                          </button>
                        )}
                        <button
                          onClick={() => { setBondForm({ face_value: 100, coupon_rate: 0, coupon_frequency: "SEMI_ANNUAL", first_coupon_date: "", maturity_date: "", issue_date: "" }); setEditingBond(true); }}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-white border border-amber-300 hover:bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700 transition-colors"
                        >
                          <Settings className="w-3.5 h-3.5" />
                          Inserisci manualmente
                        </button>
                      </div>
                    </div>
                  )}

                  {/* ── Form modifica/inserimento ── */}
                  {editingBond && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-amber-800">
                          {bondDetail ? "Modifica dettagli cedola" : "Configura dettagli cedola"}
                        </p>
                        {data?.isin && (
                          <button
                            onClick={handleEnrichModal}
                            disabled={enriching}
                            className="inline-flex items-center gap-1 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 px-2.5 py-1 text-xs font-medium text-white transition-colors"
                          >
                            <Sparkles className="w-3 h-3" />
                            {enriching ? "…" : "Da Borsa Italiana"}
                          </button>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">Tasso annuo (%)</label>
                          <input type="number" step="0.001" min="0" max="100"
                            value={bondForm.coupon_rate}
                            onChange={(e) => setBondForm(p => ({ ...p, coupon_rate: Number(e.target.value) }))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                            placeholder="es. 1.65"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">Frequenza</label>
                          <select
                            value={bondForm.coupon_frequency}
                            onChange={(e) => setBondForm(p => ({ ...p, coupon_frequency: e.target.value as CouponFrequency }))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                          >
                            <option value="ANNUAL">Annuale</option>
                            <option value="SEMI_ANNUAL">Semestrale</option>
                            <option value="QUARTERLY">Trimestrale</option>
                            <option value="MONTHLY">Mensile</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">Data prima cedola</label>
                          <input type="date"
                            value={bondForm.first_coupon_date}
                            onChange={(e) => setBondForm(p => ({ ...p, first_coupon_date: e.target.value }))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">Data scadenza</label>
                          <input type="date"
                            value={bondForm.maturity_date ?? ""}
                            onChange={(e) => setBondForm(p => ({ ...p, maturity_date: e.target.value }))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                          />
                        </div>
                      </div>
                      {bondForm.coupon_rate > 0 && (
                        <p className="text-xs text-amber-700">
                          Cedola per unità: <strong>€ {((bondForm.face_value ?? 100) * bondForm.coupon_rate / 100 / (bondForm.coupon_frequency === "SEMI_ANNUAL" ? 2 : bondForm.coupon_frequency === "QUARTERLY" ? 4 : bondForm.coupon_frequency === "MONTHLY" ? 12 : 1)).toFixed(3)}</strong>
                        </p>
                      )}
                      <div className="flex gap-2 justify-end">
                        <button onClick={() => { setEditingBond(false); setBondMsg(null); }} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5">Annulla</button>
                        <button
                          onClick={handleSaveBond}
                          disabled={saving}
                          className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
                        >
                          {saving ? "Salvo…" : "Salva"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* ── Caso B: bond_detail presente — riepilogo + pulsante modifica ── */}
                  {bondDetail && !editingBond && (
                    <>
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2 text-sm">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-xs font-semibold text-amber-800 uppercase tracking-wider">Parametri cedola</p>
                          <button onClick={openBondEdit} className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800 transition-colors">
                            <Pencil className="w-3 h-3" /> Modifica
                          </button>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Tasso annuo</span>
                          <span className="font-semibold">{(bondDetail.coupon_rate * 100).toFixed(3)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Frequenza</span>
                          <span className="font-semibold">{FREQUENCY_LABELS[bondDetail.coupon_frequency]}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Cedola per unità</span>
                          <span className="font-semibold text-amber-800">€ {bondDetail.coupon_per_unit.toFixed(3)}</span>
                        </div>
                        {data?.quantity && (
                          <div className="flex justify-between border-t border-amber-200 pt-2">
                            <span className="text-gray-700 font-medium">Cedola totale ({data.quantity.toLocaleString()} unità)</span>
                            <span className="font-bold text-amber-800">
                              {zenMode ? "•••••" : `€ ${(data.quantity * bondDetail.coupon_per_unit).toFixed(2)}`}
                            </span>
                          </div>
                        )}
                        {bondDetail.maturity_date && (
                          <div className="flex justify-between text-xs text-gray-500 pt-1">
                            <span>Scadenza</span>
                            <span>{new Date(bondDetail.maturity_date).toLocaleDateString(getIntlLocale(i18n.language))}</span>
                          </div>
                        )}
                        {bondDetail.enriched_from_bi && (
                          <p className="text-xs text-amber-600 pt-1">✓ Dati da Borsa Italiana</p>
                        )}
                      </div>

                      {/* Calendario cedole */}
                      {couponSchedule.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Prossime cedole</p>
                          <div className="space-y-1.5">
                            {couponSchedule.slice(0, 12).map((entry, i) => (
                              <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2 bg-gray-50 border border-gray-100">
                                <div className="flex items-center gap-2">
                                  {entry.already_recorded
                                    ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                                    : entry.days_until <= 30
                                      ? <Clock className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                                      : <CalendarClock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                                  }
                                  <div>
                                    <span className="text-sm text-gray-700">
                                      {new Date(entry.date).toLocaleDateString(getIntlLocale(i18n.language), { day: "2-digit", month: "long", year: "numeric" })}
                                    </span>
                                    {entry.days_until > 0 && (
                                      <span className="text-xs text-gray-400 ml-2">tra {entry.days_until} gg</span>
                                    )}
                                  </div>
                                </div>
                                <div className="text-right">
                                  <span className="text-sm font-semibold text-gray-800">
                                    {zenMode ? "•••••" : `€ ${entry.total_coupon_eur.toFixed(2)}`}
                                  </span>
                                  {entry.already_recorded && (
                                    <span className="block text-xs text-green-600">Incassata</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ── Accounts ── */}
              {tab === "accounts" && (
                <div className="p-5 space-y-3">
                  {data.accounts.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-8">{t("holdingDetail.noAccounts")}</p>
                  ) : data.accounts.map((acc) => (
                    <div key={acc.account_id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                      <div className="flex items-baseline justify-between">
                        <span className="text-sm font-semibold text-gray-800 flex items-center gap-1.5">
                          <AccountFavicon url={accountUrlById[acc.account_id]} size={4} />
                          {acc.account_name}
                        </span>
                        {acc.value_eur != null && (
                          <span className="text-sm font-bold text-gray-900">{zen(`€ ${fmt(acc.value_eur)}`)}</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-xs text-gray-500">
                          {acc.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 6 })} {t("holdingDetail.units")}
                        </span>
                        {acc.pct != null && (
                          <span className="text-xs text-gray-400">{acc.pct}%</span>
                        )}
                      </div>
                      {acc.pct != null && (
                        <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-brand-500 rounded-full"
                            style={{ width: `${Math.min(acc.pct, 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {isLoading && !data && (
          <div className="flex-1 p-5 space-y-3 animate-pulse">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-14 bg-gray-100 rounded-xl" />
            ))}
          </div>
        )}
      </div>

      {showEdit && data && (
        <AssetEditModal
          assetId={assetId}
          initialData={{
            name: data.name,
            symbol: data.symbol,
            isin: data.isin ?? null,
            asset_type: data.asset_type,
            exchange: data.exchange,
            currency: data.currency,
          }}
          onClose={() => setShowEdit(false)}
          onSaved={() => setShowEdit(false)}
        />
      )}
    </div>
  );
}

// ── Sub-componenti ────────────────────────────────────────────────────────────

function StatCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="bg-gray-50 rounded-xl border border-gray-100 px-4 py-3">
      <p className="text-xs text-gray-400 truncate">{label}</p>
      <p className={`text-sm font-semibold mt-0.5 ${
        positive === undefined ? "text-gray-900" : positive ? "text-green-600" : "text-red-600"
      }`}>
        {value}
      </p>
    </div>
  );
}

function WeightList({ title, items }: { title: string; items: { label: string; weight: number }[] }) {
  const top = items.slice(0, 8).sort((a, b) => b.weight - a.weight);
  const maxW = top[0]?.weight ?? 1;
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 space-y-2">
      <p className="text-xs font-semibold text-gray-500">{title}</p>
      {top.map((item, i) => (
        <div key={i}>
          <div className="flex justify-between text-xs text-gray-600 mb-0.5">
            <span className="truncate max-w-[70%]">{item.label}</span>
            <span className="tabular-nums text-gray-500">{(item.weight * 100).toFixed(1)}%</span>
          </div>
          <div className="h-1 rounded-full bg-gray-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-brand-500"
              style={{ width: `${(item.weight / maxW) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
