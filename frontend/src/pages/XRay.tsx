import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, XCircle, Info, ScanSearch, Scale, ChevronDown, ChevronUp, TrendingUp, TrendingDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/Button";
import { api } from "@/services/api";

// ── Tipi ─────────────────────────────────────────────────────────────────────

interface XRayRule {
  key: string;
  name: string;
  category: string;
  description: string;
  status: "ok" | "warn" | "error" | "info";
  actual: number | null;
  threshold_min: number | null;
  threshold_max: number | null;
  unit: string;
}

interface XRayResponse {
  rules: XRayRule[];
  score: number;
  rules_total: number;
  rules_ok: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  ok:    { icon: CheckCircle2, color: "text-green-500",  bg: "bg-green-50  dark:bg-green-900/20",  border: "border-green-200 dark:border-green-800" },
  warn:  { icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50  dark:bg-amber-900/20",  border: "border-amber-200 dark:border-amber-800" },
  error: { icon: XCircle,       color: "text-red-500",   bg: "bg-red-50    dark:bg-red-900/20",    border: "border-red-200   dark:border-red-800"   },
  info:  { icon: Info,          color: "text-gray-400",  bg: "bg-gray-50   dark:bg-slate-800",     border: "border-gray-200  dark:border-slate-700" },
};

function scoreColor(score: number) {
  if (score >= 80) return "text-green-600 dark:text-green-400";
  if (score >= 50) return "text-amber-500 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function scoreBarColor(score: number) {
  if (score >= 80) return "bg-green-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-red-500";
}

function formatThreshold(rule: XRayRule): string {
  const u = rule.unit;
  if (rule.threshold_min != null && rule.threshold_max != null)
    return `${rule.threshold_min}${u} – ${rule.threshold_max}${u}`;
  if (rule.threshold_max != null) return `max ${rule.threshold_max}${u}`;
  if (rule.threshold_min != null) return `min ${rule.threshold_min}${u}`;
  return "";
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <div className="h-4 w-48 bg-gray-100 dark:bg-slate-700 rounded mb-3" />
        <div className="h-2.5 w-full bg-gray-100 dark:bg-slate-700 rounded-full mb-1" />
        <div className="h-3 w-24 bg-gray-100 dark:bg-slate-700 rounded" />
      </div>
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5 space-y-3">
          <div className="h-4 w-36 bg-gray-100 dark:bg-slate-700 rounded" />
          {[1, 2].map((j) => (
            <div key={j} className="h-14 bg-gray-50 dark:bg-slate-800 rounded-xl" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Singola regola ────────────────────────────────────────────────────────────

function RuleRow({ rule }: { rule: XRayRule }) {
  const cfg = STATUS_CONFIG[rule.status] ?? STATUS_CONFIG.info;
  const Icon = cfg.icon;
  const threshold = formatThreshold(rule);

  return (
    <div className={`flex items-start gap-3 rounded-xl border p-3.5 ${cfg.bg} ${cfg.border}`}>
      <Icon className={`w-4.5 h-4.5 mt-0.5 flex-shrink-0 ${cfg.color}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-900 dark:text-slate-100">{rule.name}</span>
          <div className="flex items-baseline gap-1.5 flex-shrink-0">
            {rule.actual != null && (
              <span className={`text-sm font-bold tabular-nums ${cfg.color}`}>
                {rule.actual}{rule.unit}
              </span>
            )}
            {threshold && (
              <span className="text-xs text-gray-400 dark:text-slate-500 tabular-nums">
                ({threshold})
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5 leading-relaxed">
          {rule.description}
        </p>
        {/* Barra visiva per le regole con valore numerico */}
        {rule.actual != null && rule.threshold_max != null && (
          <div className="mt-2 h-1.5 bg-white/60 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                rule.status === "ok" ? "bg-green-500" :
                rule.status === "warn" ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${Math.min((rule.actual / (rule.threshold_max * 1.5)) * 100, 100)}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sezione Ribilanciamento ───────────────────────────────────────────────────

interface RebalanceSuggestion {
  asset_id: number;
  symbol: string;
  name: string;
  action: "buy" | "sell";
  amount_eur: number;
  current_pct: number;
  target_pct: number;
  delta_pct: number;
}

const GROUPS = ["Azioni", "Obbligazioni", "Crypto", "Altro"] as const;
type Group = typeof GROUPS[number];
const GROUP_DEFAULTS: Record<Group, number> = { Azioni: 70, Obbligazioni: 20, Crypto: 5, Altro: 5 };

function RebalanceSection() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [targets, setTargets] = useState<Record<Group, number>>(GROUP_DEFAULTS);
  const [cash, setCash] = useState("0");
  const [suggestions, setSuggestions] = useState<RebalanceSuggestion[] | null>(null);

  const total = Object.values(targets).reduce((a, b) => a + b, 0);
  const valid = Math.abs(total - 100) < 0.5;

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.post<RebalanceSuggestion[]>("/portfolio/rebalance", {
      targets: Object.entries(targets).map(([label, pct]) => ({ label, pct })),
      cash_available: parseFloat(cash) || 0,
    }),
    onSuccess: (res) => setSuggestions(res.data),
  });

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 overflow-hidden">
      <button
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="text-sm font-bold text-gray-900 dark:text-slate-100">
            {t("xray.rebalance.title")}
          </span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100 dark:border-slate-700 pt-4">
          <p className="text-xs text-gray-500 dark:text-slate-400">{t("xray.rebalance.desc")}</p>

          {/* Slider allocazione target */}
          <div className="grid grid-cols-2 gap-3">
            {GROUPS.map((g) => (
              <div key={g}>
                <div className="flex justify-between mb-1">
                  <label className="text-xs font-medium text-gray-600 dark:text-slate-400">{g}</label>
                  <span className="text-xs font-bold tabular-nums text-gray-900 dark:text-slate-100">{targets[g]}%</span>
                </div>
                <input
                  type="range" min={0} max={100} step={1} value={targets[g]}
                  onChange={(e) => setTargets((p) => ({ ...p, [g]: Number(e.target.value) }))}
                  className="w-full h-1.5 accent-brand-600"
                />
              </div>
            ))}
          </div>

          {/* Totale e warning */}
          <div className="flex items-center justify-between">
            <span className={`text-xs font-medium ${valid ? "text-green-600" : "text-red-500"}`}>
              {t("xray.rebalance.total")}: {total.toFixed(0)}%
              {!valid && ` (${t("xray.rebalance.totalMustBe100")})`}
            </span>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">{t("xray.rebalance.cash")}</label>
              <input
                type="number" step="any" min={0} value={cash}
                onChange={(e) => setCash(e.target.value)}
                className="w-24 px-2 py-1 text-xs border border-gray-300 dark:border-slate-600 rounded-lg dark:bg-slate-800 dark:text-slate-100"
                placeholder="0"
              />
              <span className="text-xs text-gray-400">EUR</span>
            </div>
          </div>

          <Button onClick={() => mutate()} loading={isPending} disabled={!valid} className="w-full">
            {t("xray.rebalance.calculate")}
          </Button>

          {/* Risultati */}
          {suggestions && (
            suggestions.length === 0 ? (
              <p className="text-xs text-center text-gray-400 py-2">{t("xray.rebalance.alreadyBalanced")}</p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-gray-600 dark:text-slate-400 uppercase tracking-wide">{t("xray.rebalance.suggestions")}</p>
                {suggestions.map((s) => (
                  <div key={s.asset_id} className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
                    s.action === "buy"
                      ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                      : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
                  }`}>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {s.action === "buy"
                          ? <TrendingUp className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                          : <TrendingDown className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />}
                        <span className="text-sm font-medium text-gray-900 dark:text-slate-100">{s.symbol}</span>
                        <span className="text-xs text-gray-400 truncate hidden sm:inline">{s.name}</span>
                      </div>
                      <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5 ml-5">
                        {s.current_pct.toFixed(1)}% → {s.target_pct.toFixed(1)}%
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <span className={`text-sm font-bold tabular-nums ${s.action === "buy" ? "text-green-600" : "text-red-500"}`}>
                        {s.action === "buy" ? "+" : "−"} € {s.amount_eur.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <div className="text-xs text-gray-400">{s.action === "buy" ? t("xray.rebalance.buy") : t("xray.rebalance.sell")}</div>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

// ── Componente principale ─────────────────────────────────────────────────────

export function XRay() {
  const { t } = useTranslation();

  const { data, isLoading } = useQuery<XRayResponse>({
    queryKey: ["xray"],
    queryFn: async () => {
      const { data } = await api.get<XRayResponse>("/portfolio/xray");
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  // Raggruppa regole per categoria
  const byCategory = (data?.rules ?? []).reduce<Record<string, XRayRule[]>>((acc, rule) => {
    if (!acc[rule.category]) acc[rule.category] = [];
    acc[rule.category].push(rule);
    return acc;
  }, {});

  const categories = Object.entries(byCategory);

  return (
    <>
      <TopBar title={t("nav.xray")} />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-5 max-w-4xl mx-auto w-full">

        {isLoading ? (
          <Skeleton />
        ) : !data || data.rules.length === 0 ? (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-12 text-center">
            <ScanSearch className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-400">{t("xray.noData")}</p>
          </div>
        ) : (
          <>
            {/* ── Score header ── */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-base font-bold text-gray-900 dark:text-slate-100">
                    {t("xray.healthScore")}
                  </h2>
                  <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                    {t("xray.scoreDesc", { ok: data.rules_ok, total: data.rules_total })}
                  </p>
                </div>
                <span className={`text-3xl font-bold tabular-nums ${scoreColor(data.score)}`}>
                  {data.score}<span className="text-lg font-medium">%</span>
                </span>
              </div>
              <div className="h-2.5 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${scoreBarColor(data.score)}`}
                  style={{ width: `${data.score}%` }}
                />
              </div>
              <div className="flex justify-between mt-1.5 text-xs text-gray-400 dark:text-slate-500">
                <span>{t("xray.scoreLow")}</span>
                <span>{t("xray.scoreHigh")}</span>
              </div>
            </div>

            {/* ── Categorie e regole ── */}
            {categories.map(([category, rules]) => {
              const okCount = rules.filter((r) => r.status === "ok").length;
              return (
                <div
                  key={category}
                  className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 overflow-hidden"
                >
                  <div className="px-5 py-3.5 border-b border-gray-100 dark:border-slate-700 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-900 dark:text-slate-100">{category}</h3>
                    <span className="text-xs text-gray-400 dark:text-slate-500 tabular-nums">
                      {okCount}/{rules.length}
                    </span>
                  </div>
                  <div className="p-4 space-y-2.5">
                    {rules.map((rule) => (
                      <RuleRow key={rule.key} rule={rule} />
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Sezione ribilanciamento */}
            <RebalanceSection />
          </>
        )}
      </main>
    </>
  );
}
