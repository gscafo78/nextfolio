import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
  BarChart, Bar, ReferenceLine, Cell as BarCell, LineChart, Line,
} from "recharts";
import { TrendingUp, TrendingDown, Minus, BarChart2, Coins, ShieldAlert, AlertTriangle, GitFork } from "lucide-react";
import { format, parseISO } from "date-fns";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { useZenMode } from "@/context/ThemeContext";
import { getIntlLocale, getDateFnsLocale } from "@/utils/format";
import i18n from "@/i18n";
import { portfolioService, type PositionOut, type AllocationItem, type PortfolioSummaryOut, type AllocationOut, type PerformancePoint } from "@/services/portfolio";

// ── Costanti ─────────────────────────────────────────────────────────────────

const PERIODS = [
  { value: "1w", label: "1S" },
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "1y", label: "1A" },
  { value: "3y", label: "3A" },
  { value: "max", label: "Max" },
];

const PIE_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
  "#ef4444", "#06b6d4", "#84cc16", "#f97316",
];

// TYPE_LABELS and DIV_LABELS are now provided by t() inside components

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, digits = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtSign(v: number, digits = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: digits, maximumFractionDigits: digits, signDisplay: "always" });
}

function colorClass(v: number | null) {
  if (v === null) return "text-gray-400";
  return v >= 0 ? "text-green-600" : "text-red-600";
}

// ── Sub-componenti ────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, positive }: {
  label: string; value: string; sub?: string; positive?: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${positive === undefined ? "text-gray-900" : positive ? "text-green-600" : "text-red-600"}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function AllocationPie({ title, items }: { title: string; items: AllocationItem[] }) {
  if (!items.length) return null;
  const zenMode = useZenMode();
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">{title}</h3>
      <div className="flex gap-6 items-center">
        <ResponsiveContainer width={160} height={160}>
          <PieChart>
            <Pie data={items} dataKey="value_eur" nameKey="label" cx="50%" cy="50%" outerRadius={70} strokeWidth={1}>
              {items.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => [zenMode ? "•••••" : `€ ${fmt(v)}`, ""]}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5 min-w-0">
          {items.map((item, i) => (
            <div key={item.label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
              />
              <span className="text-xs text-gray-600 truncate flex-1">{item.label}</span>
              <span className="text-xs font-medium text-gray-800">{item.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const RISK_PERIODS = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "1y", label: "1A" },
  { value: "3y", label: "3A" },
  { value: "max", label: "Max" },
];

function riskColor(value: number | null, good: "high" | "low"): string {
  if (value === null) return "text-gray-400";
  if (good === "high") return value >= 1 ? "text-green-600" : value >= 0 ? "text-amber-500" : "text-red-600";
  return value <= -20 ? "text-red-600" : value <= -10 ? "text-amber-500" : "text-gray-700";
}

function RiskCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-4 py-4">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold ${color ?? "text-gray-900"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function RiskMetricsSection() {
  const [riskPeriod, setRiskPeriod] = useState("3y");
  const { t, i18n } = useTranslation();
  const dfLocale = getDateFnsLocale(i18n.language);

  const { data: risk, isLoading } = useQuery({
    queryKey: ["portfolio-risk", riskPeriod],
    queryFn: () => portfolioService.getRisk(riskPeriod),
  });

  const fmtRatio = (v: number | null) => (v === null ? "—" : v.toFixed(2));
  const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">{t("performance.riskMetrics")}</h3>
        <div className="ml-auto flex gap-1">
          {RISK_PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setRiskPeriod(p.value)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                riskPeriod === p.value
                  ? "bg-brand-600 text-white"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading || !risk ? (
        <div className="p-6 text-center text-sm text-gray-400">{t("performance.calculating")}</div>
      ) : risk.trading_days < 10 ? (
        <div className="p-6 text-center text-sm text-gray-400">
          {t("performance.insufficientData")}
        </div>
      ) : (
        <div className="p-5 space-y-4">
          {/* Metriche principali */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <RiskCard
              label={t("performance.annVolatility")}
              value={`${risk.annualized_volatility_pct.toFixed(1)}%`}
              sub={t("performance.annVolatilityDesc")}
              color={
                risk.annualized_volatility_pct > 25
                  ? "text-red-600"
                  : risk.annualized_volatility_pct > 15
                  ? "text-amber-500"
                  : "text-green-600"
              }
            />
            <RiskCard
              label={t("performance.maxDrawdown")}
              value={`${risk.max_drawdown_pct.toFixed(1)}%`}
              sub={
                risk.max_drawdown_start && risk.max_drawdown_end
                  ? `${format(parseISO(risk.max_drawdown_start.toString()), "MMM yy", { locale: dfLocale })} → ${format(parseISO(risk.max_drawdown_end.toString()), "MMM yy", { locale: dfLocale })}`
                  : t("performance.maxDrawdownDesc")
              }
              color={riskColor(risk.max_drawdown_pct, "low")}
            />
            <RiskCard
              label={t("performance.sharpe")}
              value={fmtRatio(risk.sharpe_ratio)}
              sub={t("performance.sharpeDesc")}
              color={riskColor(risk.sharpe_ratio, "high")}
            />
            <RiskCard
              label={t("performance.sortino")}
              value={fmtRatio(risk.sortino_ratio)}
              sub={t("performance.sortinoDesc")}
              color={riskColor(risk.sortino_ratio, "high")}
            />
          </div>

          {/* Metriche secondarie */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            <div className="bg-gray-50 rounded-lg px-3 py-2.5">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.annReturn")}</p>
              <p className={`text-sm font-semibold ${risk.twrr_annualized_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                {fmtPct(risk.twrr_annualized_pct)}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2.5">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.calmar")}</p>
              <p className={`text-sm font-semibold ${riskColor(risk.calmar_ratio, "high")}`}>
                {fmtRatio(risk.calmar_ratio)}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2.5">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.bestDay")}</p>
              <p className="text-sm font-semibold text-green-600">+{risk.best_day_pct.toFixed(2)}%</p>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2.5">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.worstDay")}</p>
              <p className="text-sm font-semibold text-red-600">{risk.worst_day_pct.toFixed(2)}%</p>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2.5 col-span-2 sm:col-span-2">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.positiveDays")}</p>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full"
                    style={{ width: `${risk.positive_days_pct}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-gray-700">{risk.positive_days_pct.toFixed(0)}%</span>
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2.5 col-span-2 sm:col-span-2">
              <p className="text-xs text-gray-400 mb-0.5">{t("performance.tradingDays")}</p>
              <p className="text-sm font-semibold text-gray-700">{risk.trading_days.toLocaleString(getIntlLocale(i18n.language))}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const BENCHMARK_OPTIONS = [
  { value: "MSCI_WORLD", label: "MSCI World (IWDA)" },
  { value: "FTSE_MIB", label: "FTSE MIB" },
  { value: "SP500", label: "S&P 500" },
  { value: "NASDAQ", label: "NASDAQ" },
];

function corrColor(v: number): string {
  if (v >= 0.8) return "#1e3a5f";
  if (v >= 0.5) return "#1d4ed8";
  if (v >= 0.2) return "#60a5fa";
  if (v >= -0.2) return "#d1d5db";
  if (v >= -0.5) return "#fca5a5";
  return "#dc2626";
}

// ── Bar chart mensile ─────────────────────────────────────────────────────────

function buildMonthlyReturns(series: PerformancePoint[]): { month: string; pct: number }[] {
  if (series.length < 2) return [];
  const byMonth = new Map<string, PerformancePoint[]>();
  for (const p of series) {
    const key = p.date.toString().substring(0, 7);
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key)!.push(p);
  }
  const sortedKeys = [...byMonth.keys()].sort();
  const result: { month: string; pct: number }[] = [];
  for (const key of sortedKeys) {
    const pts = byMonth.get(key)!.sort((a, b) => a.date.toString().localeCompare(b.date.toString()));
    const first = pts[0];
    const last = pts[pts.length - 1];
    if (first.value_eur > 0) {
      result.push({ month: key, pct: Math.round(((last.value_eur - first.value_eur) / first.value_eur) * 10000) / 100 });
    }
  }
  return result;
}

function MonthlyBarChart({ series }: { series: PerformancePoint[] }) {
  const { t } = useTranslation();
  const data = buildMonthlyReturns(series);
  if (data.length < 2) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">{t("performance.monthlyPerf")}</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
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
            tickFormatter={(v) => `${v}%`}
            width={40}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            formatter={(v: number) => [`${v >= 0 ? "+" : ""}${v.toFixed(2)}%`, t("performance.monthlyReturn")]}
            labelFormatter={(d) => {
              const [y, m] = d.split("-");
              return `${m}/${y}`;
            }}
          />
          <ReferenceLine y={0} stroke="#e2e8f0" />
          <Bar dataKey="pct" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <BarCell key={i} fill={entry.pct >= 0 ? "#10b981" : "#ef4444"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Sezione Benchmark ─────────────────────────────────────────────────────────

function BenchmarkSection({ perfSeries, period }: { perfSeries: PerformancePoint[]; period: string }) {
  const [benchIndex, setBenchIndex] = useState("MSCI_WORLD");
  const { t, i18n } = useTranslation();
  const dfLocale = getDateFnsLocale(i18n.language);

  const { data: bench, isLoading } = useQuery({
    queryKey: ["benchmark", benchIndex, period],
    queryFn: () => portfolioService.getBenchmark(benchIndex, period),
    staleTime: 15 * 60 * 1000,
  });

  if (perfSeries.length < 2) return null;

  // Normalizza la serie del portafoglio a 100
  const base = perfSeries[0].value_eur;
  const portfolioNorm = base > 0
    ? perfSeries.map((p) => ({ date: p.date.toString(), portfolio: Math.round((p.value_eur / base) * 10000) / 100 }))
    : [];

  // Unisci con dati benchmark per data
  const benchMap = new Map((bench?.series ?? []).map((s) => [s.date, s.value]));
  const combined = portfolioNorm.map((p) => ({
    date: p.date,
    portfolio: p.portfolio,
    benchmark: benchMap.get(p.date) ?? null,
  }));

  const benchYearTicks = combined
    .filter((p, i) =>
      i === 0 ||
      new Date(p.date).getFullYear() !== new Date(combined[i - 1].date).getFullYear()
    )
    .map((p) => p.date);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">{t("performance.benchmark")}</h3>
          <p className="text-xs text-gray-400 mt-0.5">{t("performance.benchmarkNote")}</p>
        </div>
        <select
          value={benchIndex}
          onChange={(e) => setBenchIndex(e.target.value)}
          className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {BENCHMARK_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
      {isLoading ? (
        <div className="h-48 flex items-center justify-center text-xs text-gray-400">{t("common.loading")}</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={combined} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              ticks={benchYearTicks}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(d) => new Date(d).getFullYear().toString()}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}`}
              width={44}
            />
            <Tooltip
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
              formatter={(v: number, name: string) => [
                `${v.toFixed(2)}`,
                name === "portfolio" ? t("performance.portfolio") : BENCHMARK_OPTIONS.find((o) => o.value === benchIndex)?.label ?? "Benchmark",
              ]}
              labelFormatter={(d) => format(parseISO(d), "d MMM yyyy", { locale: dfLocale })}
            />
            <Line type="monotone" dataKey="portfolio" stroke="#10b981" strokeWidth={2} dot={false} name="portfolio" />
            <Line type="monotone" dataKey="benchmark" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="benchmark" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ── Sezione Correlazione ──────────────────────────────────────────────────────

function CorrelationSection() {
  const [corrPeriod, setCorrPeriod] = useState("1y");
  const { t } = useTranslation();

  const { data, isLoading } = useQuery({
    queryKey: ["correlation", corrPeriod],
    queryFn: () => portfolioService.getCorrelation(corrPeriod),
    staleTime: 10 * 60 * 1000,
  });

  const CORR_PERIODS = [
    { value: "3m", label: "3M" },
    { value: "6m", label: "6M" },
    { value: "1y", label: "1A" },
    { value: "3y", label: "3A" },
    { value: "max", label: "Max" },
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
        <GitFork className="w-4 h-4 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">{t("performance.correlation")}</h3>
        <div className="ml-auto flex gap-1">
          {CORR_PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setCorrPeriod(p.value)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                corrPeriod === p.value ? "bg-brand-600 text-white" : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="p-6 text-center text-sm text-gray-400">{t("performance.calculating")}</div>
      ) : !data || data.labels.length < 2 ? (
        <div className="p-6 text-center text-sm text-gray-400">
          {t("performance.insufficientData")}
        </div>
      ) : (
        <div className="p-4 overflow-x-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="w-20 p-1" />
                {data.labels.map((l) => (
                  <th key={l} className="p-1 text-center font-medium text-gray-500 w-16">{l}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.matrix.map((row, i) => (
                <tr key={data.labels[i]}>
                  <td className="p-1 pr-2 font-medium text-gray-600 text-right">{data.labels[i]}</td>
                  {row.map((v, j) => (
                    <td
                      key={j}
                      className="p-1 text-center tabular-nums font-semibold rounded"
                      style={{
                        backgroundColor: corrColor(v) + "33",
                        color: corrColor(v),
                      }}
                      title={`${data.labels[i]} vs ${data.labels[j]}: ${v.toFixed(4)}`}
                    >
                      {v.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            {[
              { label: t("performance.correlationHigh"), color: "#1d4ed8" },
              { label: t("performance.correlationMed"), color: "#60a5fa" },
              { label: t("performance.correlationNone"), color: "#9ca3af" },
              { label: t("performance.correlationMedNeg"), color: "#fca5a5" },
              { label: t("performance.correlationHighNeg"), color: "#dc2626" },
            ].map((c) => (
              <div key={c.label} className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: c.color + "55" }} />
                <span className="text-xs text-gray-500">{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Performance() {
  const [period, setPeriod] = useState("1y");
  const zenMode = useZenMode();
  const zen = (v: string) => zenMode ? "•••••" : v;
  const { t, i18n } = useTranslation();
  const dfLocale = getDateFnsLocale(i18n.language);

  const { data: dashboardData, isLoading: loadingDashboard } = useQuery({
    queryKey: ["portfolio-dashboard"],
    queryFn: portfolioService.getDashboard,
    staleTime: 5 * 60 * 1000,
  });
  const summary: PortfolioSummaryOut | undefined = dashboardData?.summary;
  const positions: PositionOut[] = dashboardData?.positions ?? [];
  const allocation: AllocationOut | undefined = dashboardData?.allocation;
  const loadingPos = loadingDashboard;

  const { data: perf, isLoading: loadingPerf } = useQuery({
    queryKey: ["portfolio-performance", period],
    queryFn: () => portfolioService.getPerformance(period),
  });

  const { data: dividends = [] } = useQuery({
    queryKey: ["portfolio-dividends"],
    queryFn: portfolioService.getDividends,
  });

  const { data: xirrData } = useQuery({
    queryKey: ["portfolio-xirr"],
    queryFn: portfolioService.getXirr,
    staleTime: 10 * 60 * 1000,
  });

  const hasSummary = !!summary;
  const series = perf?.series ?? [];
  const chartPositive = series.length < 2
    ? true
    : series[series.length - 1].pnl_eur >= 0;

  const chartData = series.map((p) => ({ ...p }));

  const yearTicks = chartData
    .filter((p, i) =>
      i === 0 ||
      parseISO(p.date).getFullYear() !== parseISO(chartData[i - 1].date).getFullYear()
    )
    .map((p) => p.date);

  return (
    <>
      <TopBar title={t("performance.title")} />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-6">

        {/* KPI sommario */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          <KpiCard
            label={t("dashboard.portfolioValue")}
            value={hasSummary ? zen(`€ ${fmt(summary.total_value_eur)}`) : "—"}
            sub={hasSummary ? `${t("performance.invested")}: ${zen("€ " + fmt(summary.total_invested_eur))}` : undefined}
          />
          <KpiCard
            label={t("performance.kpiTotalPnl")}
            value={hasSummary ? zen(`€ ${fmtSign(summary.total_pnl_eur)}`) : "—"}
            sub={hasSummary ? `${fmtSign(summary.total_pnl_pct, 2)}%` : undefined}
            positive={hasSummary ? summary.total_pnl_eur >= 0 : undefined}
          />
          <KpiCard
            label={t("performance.unrealizedPnl")}
            value={hasSummary ? zen(`€ ${fmtSign(summary.unrealized_pnl_eur)}`) : "—"}
            sub={hasSummary ? t("performance.openPositionsNote") : undefined}
            positive={hasSummary ? summary.unrealized_pnl_eur >= 0 : undefined}
          />
          <KpiCard
            label={t("performance.realizedPnl")}
            value={hasSummary ? zen(`€ ${fmtSign(summary.realized_pnl_eur)}`) : "—"}
            sub={hasSummary ? t("performance.closedSalesNote") : undefined}
            positive={hasSummary ? summary.realized_pnl_eur >= 0 : undefined}
          />
          <KpiCard
            label={t("performance.irrXirr")}
            value={xirrData?.xirr_pct != null ? `${fmtSign(xirrData.xirr_pct, 2)}%` : "—"}
            sub={t("performance.internalRate")}
            positive={xirrData?.xirr_pct != null ? xirrData.xirr_pct >= 0 : undefined}
          />
        </div>

        {positions.length === 0 && !loadingPos ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <BarChart2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">{t("performance.addTransactions")}</p>
          </div>
        ) : (
          <>
            {/* Grafico performance + bar mensile sulla stessa riga */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">{t("performance.portfolioTrend")}</h3>
                  {perf && (
                    <span className={`text-xs font-medium ${perf.twrr_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                      TWRR {fmtSign(perf.twrr_pct, 2)}%
                    </span>
                  )}
                </div>
                <div className="flex gap-1">
                  {PERIODS.map((p) => (
                    <button
                      key={p.value}
                      onClick={() => setPeriod(p.value)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                        period === p.value
                          ? "bg-brand-600 text-white"
                          : "text-gray-500 hover:bg-gray-100"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {loadingPerf ? (
                <div className="h-48 flex items-center justify-center text-gray-400 text-sm">{t("common.loading")}</div>
              ) : chartData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                  {t("performance.noHistoricalData")}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gradValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={chartPositive ? "#10b981" : "#ef4444"} stopOpacity={0.15} />
                        <stop offset="95%" stopColor={chartPositive ? "#10b981" : "#ef4444"} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradInvested" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.1} />
                        <stop offset="95%" stopColor="#94a3b8" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis
                      dataKey="date"
                      ticks={yearTicks}
                      tickFormatter={(d) => new Date(d).getFullYear().toString()}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => zenMode ? "•••" : `€${(v / 1000).toFixed(0)}k`}
                      width={52}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                      formatter={(v: number, name: string) => [
                        zenMode ? "•••••" : `€ ${fmt(v)}`,
                        name === "value_eur" ? t("common.value") : t("performance.invested"),
                      ]}
                      labelFormatter={(d) => format(parseISO(d), "d MMM yyyy", { locale: dfLocale })}
                    />
                    <Area
                      type="monotone"
                      dataKey="invested_eur"
                      stroke="#94a3b8"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      fill="url(#gradInvested)"
                      dot={false}
                    />
                    <Area
                      type="monotone"
                      dataKey="value_eur"
                      stroke={chartPositive ? "#10b981" : "#ef4444"}
                      strokeWidth={2}
                      fill="url(#gradValue)"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Bar chart mensile */}
            {series.length > 1 && <MonthlyBarChart series={series} />}
            </div>{/* end grid row */}

            {/* Benchmark + Correlazione sulla stessa riga */}
            {series.length > 1 && (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <BenchmarkSection perfSeries={series} period={period} />
                <CorrelationSection />
              </div>
            )}

            {/* Metriche di rischio */}
            <RiskMetricsSection />

            {/* Allocazione */}
            {allocation && allocation.total_value_eur > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                <AllocationPie title={t("performance.allocationPie")} items={allocation.by_type} />
                <AllocationPie title={t("performance.allocationCurrency")} items={allocation.by_currency} />
                {allocation.by_account.length > 1 && (
                  <AllocationPie title={t("performance.allocationAccount")} items={allocation.by_account} />
                )}
              </div>
            )}

            {/* Tabella posizioni */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">{t("performance.openPositions")}</h3>
                <span className="ml-auto text-xs text-gray-400">{positions.length} asset</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-50 text-left">
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.asset")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.qty")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.avgCost")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.currentPrice")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.currentValue")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.unrealizedPnl")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.realizedPnl")}</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("performance.dailyChange")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {positions.map((pos) => (
                      <PositionRow key={pos.asset_id} pos={pos} totalValue={summary?.total_value_eur ?? 0} />
                    ))}
                  </tbody>
                  {positions.length > 0 && summary && (
                    <tfoot>
                      <tr className="border-t border-gray-200 bg-gray-50">
                        <td colSpan={4} className="px-5 py-2 text-xs text-gray-400">{t("performance.totalPortfolio")}</td>
                        <td className="px-5 py-2 text-right text-sm font-semibold text-gray-900">
                          {zen(`€ ${fmt(summary.total_value_eur)}`)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.unrealized_pnl_eur)}`}>
                          {zen(`€ ${fmtSign(summary.unrealized_pnl_eur)}`)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.realized_pnl_eur)}`}>
                          {zen(`€ ${fmtSign(summary.realized_pnl_eur)}`)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.daily_change_eur)}`}>
                          {zen(`€ ${fmtSign(summary.daily_change_eur)}`)}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>

            {/* Dividendi / cedole */}
            {dividends.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                  <Coins className="w-4 h-4 text-gray-400" />
                  <h3 className="text-sm font-semibold text-gray-700">{t("performance.dividendsAndCoupons")}</h3>
                  <span className="ml-auto text-xs text-gray-400">
                    {t("performance.total")} {zen(`€ ${fmt(dividends.reduce((s, d) => s + d.amount_eur, 0))}`)}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50 text-left">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.date")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.type")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.asset")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.account")}</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dividends.amountEur")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {dividends.map((d) => (
                        <tr key={d.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-5 py-3 text-gray-600">
                            {format(parseISO(d.date), "dd MMM yyyy", { locale: dfLocale })}
                          </td>
                          <td className="px-5 py-3">
                            <span className="text-xs font-medium text-blue-600">
                              {t(`performance.dividendTypes.${d.type}`) || d.type}
                            </span>
                          </td>
                          <td className="px-5 py-3">
                            <div className="font-medium text-gray-900">{d.symbol}</div>
                            <div className="text-xs text-gray-400 truncate max-w-[180px]">{d.name}</div>
                          </td>
                          <td className="px-5 py-3 text-xs text-gray-500">{d.account_name}</td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            {zenMode ? "•••••" : `+ € ${fmt(d.amount_eur)}`}
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

// ── Riga posizione ─────────────────────────────────────────────────────────────

function PositionRow({ pos, totalValue }: { pos: PositionOut; totalValue: number }) {
  const { t } = useTranslation();
  const hasPrices = pos.current_value_eur !== null;
  const weightPct = totalValue > 0 && pos.current_value_eur ? (pos.current_value_eur / totalValue) * 100 : 0;
  const isConcentrated = weightPct > 10;
  const zenMode = useZenMode();
  const zen = (v: string) => zenMode ? "•••••" : v;
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-5 py-3">
        <div className="flex items-center gap-1.5">
          <span className="font-medium text-gray-900">{pos.symbol}</span>
          {isConcentrated && (
            <span title={`${t("performance.highConcentration")}: ${weightPct.toFixed(1)}%`}>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400 truncate max-w-[200px]">{pos.name}</div>
        <div className="text-xs text-gray-300">{t(`performance.assetTypes.${pos.asset_type}`) || pos.asset_type} · {pos.exchange}</div>
      </td>
      <td className="px-5 py-3 text-right text-gray-600">
        {pos.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 6 })}
      </td>
      <td className="px-5 py-3 text-right text-gray-600 font-mono text-xs">
        {zen(`€ ${fmt(pos.pmc_eur, 2)}`)}
      </td>
      <td className="px-5 py-3 text-right">
        {hasPrices ? (
          <div>
            <div className="text-gray-700 font-mono text-xs">
              {pos.current_price !== null
                ? `${pos.current_price.toFixed(2)} ${pos.currency}`
                : "—"}
            </div>
            {pos.change_pct !== null && (
              <div className={`text-xs ${colorClass(pos.change_pct)}`}>
                {pos.change_pct >= 0 ? "+" : ""}{pos.change_pct.toFixed(2)}%
              </div>
            )}
          </div>
        ) : <Minus className="w-3 h-3 text-gray-300 ml-auto" />}
      </td>
      <td className="px-5 py-3 text-right font-medium text-gray-900">
        {hasPrices ? zen(`€ ${fmt(pos.current_value_eur!)}`) : "—"}
      </td>
      <td className="px-5 py-3 text-right">
        {pos.unrealized_pnl_eur !== null ? (
          <div>
            <div className={`text-xs font-semibold ${colorClass(pos.unrealized_pnl_eur)}`}>
              {zen(`€ ${fmtSign(pos.unrealized_pnl_eur)}`)}
            </div>
            {pos.unrealized_pnl_pct !== null && (
              <div className={`text-xs ${colorClass(pos.unrealized_pnl_pct)}`}>
                {fmtSign(pos.unrealized_pnl_pct, 2)}%
              </div>
            )}
          </div>
        ) : <Minus className="w-3 h-3 text-gray-300 ml-auto" />}
      </td>
      <td className={`px-5 py-3 text-right text-xs font-semibold ${colorClass(pos.realized_pnl_eur)}`}>
        {pos.realized_pnl_eur !== 0
          ? zen(`€ ${fmtSign(pos.realized_pnl_eur)}`)
          : <span className="text-gray-300">—</span>}
      </td>
      <td className="px-5 py-3 text-right">
        {pos.change_pct !== null && pos.current_value_eur !== null ? (
          <span className={`flex items-center justify-end gap-1 text-xs font-semibold ${colorClass(pos.change_pct)}`}>
            {pos.change_pct >= 0
              ? <TrendingUp className="w-3 h-3" />
              : <TrendingDown className="w-3 h-3" />}
            {pos.change_pct >= 0 ? "+" : ""}{pos.change_pct.toFixed(2)}%
          </span>
        ) : <Minus className="w-3 h-3 text-gray-300 ml-auto" />}
      </td>
    </tr>
  );
}
