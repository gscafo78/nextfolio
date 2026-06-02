import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, XCircle, Info, ScanSearch } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
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
                  {/* Header categoria */}
                  <div className="px-5 py-3.5 border-b border-gray-100 dark:border-slate-700 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-900 dark:text-slate-100">{category}</h3>
                    <span className="text-xs text-gray-400 dark:text-slate-500 tabular-nums">
                      {okCount}/{rules.length}
                    </span>
                  </div>
                  {/* Lista regole */}
                  <div className="p-4 space-y-2.5">
                    {rules.map((rule) => (
                      <RuleRow key={rule.key} rule={rule} />
                    ))}
                  </div>
                </div>
              );
            })}
          </>
        )}
      </main>
    </>
  );
}
