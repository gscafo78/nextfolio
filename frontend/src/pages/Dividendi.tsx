import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { Coins, TrendingUp, TrendingDown, CalendarClock, CheckCircle2, Clock, Plus, History, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getIntlLocale } from "@/utils/format";
import i18n from "@/i18n";
import { TopBar } from "@/components/layout/TopBar";
import { useZenMode } from "@/context/ThemeContext";
import { api } from "@/services/api";
import { bondService, type UpcomingCouponEntry, type BackfillSummary } from "@/services/bonds";
import { accountService, transactionService } from "@/services/transactions";

// ── Tipi ──────────────────────────────────────────────────────────────────────

interface YocEntry {
  asset_id: number;
  symbol: string;
  name: string;
  total_income_eur: number;
  cost_basis_eur: number;
  yield_on_cost_pct: number | null;
}

interface YoyEntry {
  year: number;
  amount_eur: number;
  growth_pct: number | null;
}

interface MonthlyEntry {
  month: string;
  amount_eur: number;
}

interface DividendAnalysis {
  total_income_eur: number;
  by_year: YoyEntry[];
  by_month: MonthlyEntry[];
  yield_on_cost: YocEntry[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, d = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: d, maximumFractionDigits: d });
}

// ── Componente principale ──────────────────────────────────────────────────────

function CouponBadge({ entry }: { entry: UpcomingCouponEntry }) {
  if (entry.already_recorded) return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
      <CheckCircle2 className="w-3 h-3" /> Incassata
    </span>
  );
  if (entry.days_until <= 30) return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Clock className="w-3 h-3" /> In arrivo
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
      Futura
    </span>
  );
}

function BackfillModal({ result, onClose }: { result: BackfillSummary; onClose: () => void }) {
  const created = result.details.filter(d => d.created);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-bold text-gray-900">Backfill cedole completato</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {result.created_count} cedole create · € {result.total_amount_eur.toFixed(2)} totale
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
          {created.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-700 uppercase tracking-wider mb-2">✅ Create ({created.length})</p>
              <div className="space-y-1.5">
                {created.map((d, i) => (
                  <div key={i} className="flex justify-between items-center text-sm bg-green-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="font-medium text-gray-800">{d.asset_name}</span>
                      <span className="text-xs text-gray-500 ml-2">{new Date(d.coupon_date).toLocaleDateString("it-IT")}</span>
                    </div>
                    <span className="font-semibold text-green-700">€ {d.amount_eur.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {result.skipped_count > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">⏭ Saltate ({result.skipped_count})</p>
              <div className="space-y-1">
                {result.details.filter(d => !d.created).slice(0, 10).map((d, i) => (
                  <div key={i} className="flex justify-between items-center text-xs text-gray-500 px-3 py-1.5 bg-gray-50 rounded-lg">
                    <span>{d.asset_name} · {new Date(d.coupon_date).toLocaleDateString("it-IT")}</span>
                    <span className="text-gray-400">{d.skipped_reason}</span>
                  </div>
                ))}
                {result.details.filter(d => !d.created).length > 10 && (
                  <p className="text-xs text-gray-400 text-center">…e altri {result.details.filter(d => !d.created).length - 10}</p>
                )}
              </div>
            </div>
          )}
          {result.created_count === 0 && result.skipped_count === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">Nessun BTP con bond_detail configurato trovato.</p>
          )}
        </div>
        <div className="px-6 py-4 border-t border-gray-100">
          <button onClick={onClose} className="w-full bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium py-2.5 rounded-xl transition-colors">
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}

function RegisterCouponInline({ coupon, onDone }: { coupon: UpcomingCouponEntry; onDone: () => void }) {
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });
  const qc = useQueryClient();
  const [accountId, setAccountId] = useState<number>(accounts[0]?.id ?? 0);
  const [qty, setQty] = useState(coupon.quantity);
  const [price, setPrice] = useState(coupon.coupon_per_unit);
  const [error, setError] = useState<string | null>(null);

  const { mutate, isPending } = useMutation({
    mutationFn: () => transactionService.create({
      account_id: accountId,
      asset_id: coupon.asset_id,
      type: "COUPON",
      date: coupon.date,
      quantity: qty,
      price,
      exchange_rate: 1,
      fee: 0,
      price_currency: "EUR",
      fee_currency: "EUR",
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["upcoming-coupons"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dividend-analysis"] });
      onDone();
    },
    onError: () => setError("Errore durante il salvataggio. Riprova."),
  });

  return (
    <tr className="bg-amber-50">
      <td colSpan={6} className="px-4 py-3">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Conto</label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
            >
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Quantità</label>
            <input type="number" step="any" value={qty} onChange={(e) => setQty(Number(e.target.value))}
              className="w-24 border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">€/unità</label>
            <input type="number" step="0.001" value={price} onChange={(e) => setPrice(Number(e.target.value))}
              className="w-24 border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
          </div>
          <div className="text-xs text-gray-500">
            Totale: <strong className="text-gray-800">€ {(qty * price).toFixed(2)}</strong>
          </div>
          <button
            onClick={() => mutate()}
            disabled={isPending || !accountId}
            className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
          >
            {isPending ? "Salvo…" : "Salva"}
          </button>
          <button onClick={onDone} className="text-xs text-gray-400 hover:text-gray-600 px-1">Annulla</button>
          {error && <span className="text-xs text-red-600">{error}</span>}
        </div>
      </td>
    </tr>
  );
}

function UpcomingCouponsSection() {
  const { t } = useTranslation();
  const zenMode = useZenMode();
  const [days, setDays] = useState(365);
  const [registeringIdx, setRegisteringIdx] = useState<number | null>(null);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillResult, setBackfillResult] = useState<BackfillSummary | null>(null);
  const qc = useQueryClient();

  const { data: coupons = [], isLoading } = useQuery({
    queryKey: ["upcoming-coupons", days],
    queryFn: () => bondService.upcomingCoupons(days),
  });

  const handleBackfill = async () => {
    setBackfilling(true);
    try {
      const result = await bondService.backfillCoupons();
      setBackfillResult(result);
      qc.invalidateQueries({ queryKey: ["upcoming-coupons"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dividend-analysis"] });
    } catch {
      alert("Errore durante il backfill. Assicurati di aver configurato i bond_detail per i tuoi BTP.");
    } finally {
      setBackfilling(false);
    }
  };

  if (!isLoading && coupons.length === 0) return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm p-5 flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-amber-700">
        <CalendarClock className="w-4 h-4 text-amber-500" />
        <span>Nessuna cedola in arrivo — <span className="text-gray-400">configura i BTP dal tab "Cedole" nel dettaglio holding</span></span>
      </div>
      <button
        onClick={handleBackfill}
        disabled={backfilling}
        className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 px-3 py-1.5 text-xs font-medium text-white transition-colors"
      >
        <History className="w-3.5 h-3.5" />
        {backfilling ? "Elaboro…" : "Inserisci cedole storiche"}
      </button>
      {backfillResult && <BackfillModal result={backfillResult} onClose={() => setBackfillResult(null)} />}
    </div>
  );

  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-2">
          <CalendarClock className="w-4 h-4 text-amber-600" />
          <h3 className="text-sm font-semibold text-amber-800">{t("bonds.upcomingCoupons")}</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleBackfill}
            disabled={backfilling}
            title="Inserisce le cedole storiche mancanti per tutti i BTP configurati"
            className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white hover:bg-amber-50 disabled:opacity-50 px-2.5 py-1 text-xs font-medium text-amber-700 transition-colors"
          >
            <History className="w-3.5 h-3.5" />
            {backfilling ? "Elaboro…" : "Storico"}
          </button>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value={30}>30 gg</option>
          <option value={90}>90 gg</option>
          <option value={365}>12 mesi</option>
          <option value={1825}>5 anni</option>
        </select>
        </div>
      </div>
      {backfillResult && <BackfillModal result={backfillResult} onClose={() => setBackfillResult(null)} />}
      {isLoading ? (
        <div className="py-6 text-center text-sm text-gray-400">{t("common.loading")}</div>
      ) : (
        <div className="overflow-x-auto border-t border-amber-100">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-amber-50 text-left text-gray-600 text-xs">
                <th className="px-4 py-2 font-medium">Data</th>
                <th className="px-4 py-2 font-medium">{t("common.asset")}</th>
                <th className="px-4 py-2 font-medium text-right">€/unità</th>
                <th className="px-4 py-2 font-medium text-right">{t("bonds.totalCoupon")}</th>
                <th className="px-4 py-2 font-medium">Stato</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-50">
              {coupons.map((c, i) => (
                <>
                  <tr key={i} className="hover:bg-amber-50 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap text-gray-500 text-xs">
                      {new Date(c.date).toLocaleDateString(getIntlLocale(i18n.language))}
                      {c.days_until >= 0 && (
                        <span className="block text-gray-400">tra {c.days_until} gg</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 truncate max-w-[160px]">{c.asset_name}</div>
                      {c.isin && <div className="text-xs text-gray-400 font-mono">{c.isin}</div>}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {zenMode ? "•••••" : `€ ${fmt(c.coupon_per_unit, 3)}`}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-amber-800">
                      {zenMode ? "•••••" : `€ ${fmt(c.total_coupon_eur)}`}
                    </td>
                    <td className="px-4 py-3">
                      <CouponBadge entry={c} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!c.already_recorded && (
                        <button
                          onClick={() => setRegisteringIdx(registeringIdx === i ? null : i)}
                          className="inline-flex items-center gap-1 rounded-lg bg-amber-100 hover:bg-amber-200 px-2 py-1 text-xs font-medium text-amber-800 transition-colors"
                        >
                          <Plus className="w-3 h-3" /> Registra
                        </button>
                      )}
                    </td>
                  </tr>
                  {registeringIdx === i && (
                    <RegisterCouponInline key={`reg-${i}`} coupon={c} onDone={() => setRegisteringIdx(null)} />
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function Dividendi() {
  const zenMode = useZenMode();
  const zen = (v: string) => zenMode ? "•••••" : v;
  const { t } = useTranslation();

  const { data, isLoading } = useQuery<DividendAnalysis>({
    queryKey: ["dividend-analysis"],
    queryFn: async () => {
      const { data } = await api.get("/portfolio/dividend-analysis");
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <>
        <TopBar title={t("dividends.title")} />
        <main className="flex-1 p-4 md:p-6 flex items-center justify-center">
          <p className="text-sm text-gray-400">{t("common.loading")}</p>
        </main>
      </>
    );
  }

  const isEmpty = !data || data.total_income_eur === 0;

  // Prendi gli ultimi 24 mesi per il grafico mensile
  const monthlyData = (data?.by_month ?? []).slice(-24);

  return (
    <>
      <TopBar title={t("dividends.title")} />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-6">

        {/* Cedole BTP in arrivo */}
        <UpcomingCouponsSection />

        {isEmpty ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <Coins className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">{t("dividends.noData")}</p>
          </div>
        ) : (
          <>
            {/* KPI */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{t("dividends.totalIncome")}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{zen(`€ ${fmt(data!.total_income_eur)}`)}</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{t("dividends.currentYear")}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {zen(`€ ${fmt((data!.by_year.find((y) => y.year === new Date().getFullYear())?.amount_eur ?? 0))}`)}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{t("dividends.avgAnnual")}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {zen(`€ ${fmt(data!.by_year.length > 0 ? data!.total_income_eur / data!.by_year.length : 0)}`)}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{t("dividends.payingAssets")}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{data!.yield_on_cost.length}</p>
              </div>
            </div>

            {/* Grafico mensile */}
            {monthlyData.length > 1 && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">{t("dividends.monthlyIncome")}</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={monthlyData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tickFormatter={(d) => {
                        const [y, m] = d.split("-");
                        return `${m}/${y.slice(2)}`;
                      }}
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => zenMode ? "•••" : `€${v}`}
                      width={50}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                      formatter={(v: number) => [zenMode ? "•••••" : `€ ${fmt(v)}`, t("dividends.incomeLabel")]}
                    />
                    <Bar dataKey="amount_eur" radius={[3, 3, 0, 0]}>
                      {monthlyData.map((_, i) => (
                        <Cell key={i} fill="#10b981" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Performance annuale */}
            {data!.by_year.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">{t("dividends.incomeByYear")}</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-left">{t("dividends.year")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.amountEur")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.yoyGrowth")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {[...data!.by_year].reverse().map((y) => (
                        <tr key={y.year} className="hover:bg-gray-50">
                          <td className="px-5 py-3 font-semibold text-gray-900">{y.year}</td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            {zenMode ? "•••••" : `+ € ${fmt(y.amount_eur)}`}
                          </td>
                          <td className="px-5 py-3 text-right">
                            {y.growth_pct !== null ? (
                              <span className={`flex items-center justify-end gap-1 text-xs font-semibold ${y.growth_pct >= 0 ? "text-green-600" : "text-red-500"}`}>
                                {y.growth_pct >= 0
                                  ? <TrendingUp className="w-3.5 h-3.5" />
                                  : <TrendingDown className="w-3.5 h-3.5" />}
                                {y.growth_pct >= 0 ? "+" : ""}{fmt(y.growth_pct, 1)}%
                              </span>
                            ) : (
                              <span className="text-xs text-gray-300">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Yield on cost per asset */}
            {data!.yield_on_cost.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">{t("dividends.yieldOnCost")}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">{t("dividends.yocDesc")}</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-left">{t("common.asset")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.costBasis")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.totalIncome")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.yocPct")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {data!.yield_on_cost.map((entry) => (
                        <tr key={entry.asset_id} className="hover:bg-gray-50">
                          <td className="px-5 py-3">
                            <div className="font-medium text-gray-900">{entry.symbol}</div>
                            <div className="text-xs text-gray-400 truncate max-w-[200px]">{entry.name}</div>
                          </td>
                          <td className="px-5 py-3 text-right text-gray-600">
                            {zen(`€ ${fmt(entry.cost_basis_eur)}`)}
                          </td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            {zenMode ? "•••••" : `+ € ${fmt(entry.total_income_eur)}`}
                          </td>
                          <td className="px-5 py-3 text-right">
                            {entry.yield_on_cost_pct !== null ? (
                              <span className={`font-semibold ${
                                entry.yield_on_cost_pct >= 4 ? "text-green-600"
                                  : entry.yield_on_cost_pct >= 2 ? "text-amber-500"
                                  : "text-gray-600"
                              }`}>
                                {fmt(entry.yield_on_cost_pct, 2)}%
                              </span>
                            ) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
