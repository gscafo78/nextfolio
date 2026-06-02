import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { useTranslation } from "react-i18next";
import { getDateFnsLocale, getIntlLocale } from "@/utils/format";
import type { PerformancePoint } from "@/services/portfolio";

interface ChartPoint {
  date: string;
  value: number;
  pct: number; // TWRR % from backend
  pnlEur: number; // net P&L EUR from period start
}

interface PortfolioChartProps {
  series: PerformancePoint[];
  isLoading: boolean;
  header?: ReactNode;
  height?: number;
}

export function PortfolioChart({ series, isLoading, header, height = 220 }: PortfolioChartProps) {
  const { t, i18n } = useTranslation();
  const dfLocale = getDateFnsLocale(i18n.language);
  const intlLocale = getIntlLocale(i18n.language);

  const pnlAtStart = series[0]?.pnl_eur ?? 0;

  const chartData: ChartPoint[] = series.map((pt) => ({
    date: pt.date,
    value: pt.value_eur,
    pct: pt.twrr_pct,
    pnlEur: pt.pnl_eur - pnlAtStart,
  }));

  const yearTicks = chartData
    .filter((pt, i) =>
      i === 0 ||
      new Date(pt.date).getFullYear() !== new Date(chartData[i - 1].date).getFullYear()
    )
    .map((pt) => pt.date);

  const lastPct = chartData[chartData.length - 1]?.pct ?? 0;
  const isPositive = lastPct >= 0;
  const color      = isPositive ? "#16a34a" : "#dc2626";

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const pt = payload[0].payload as ChartPoint;
    const pos = pt.pct >= 0;
    const pnlEur = pt.pnlEur;
    return (
      <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs shadow-lg">
        <p className="text-gray-400 mb-1">
          {format(new Date(label), "d MMM yyyy", { locale: dfLocale })}
        </p>
        <p className={`font-bold text-sm ${pos ? "text-green-600" : "text-red-600"}`}>
          {pos ? "+" : ""}{pt.pct.toFixed(2)} %
        </p>
        <p className={`font-medium ${pos ? "text-green-600" : "text-red-600"}`}>
          {pos ? "+" : "−"} € {Math.abs(pnlEur).toLocaleString(intlLocale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className="text-gray-400 mt-0.5">
          {t("common.value")}: € {pt.value.toLocaleString(intlLocale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 h-56 flex items-center justify-center text-gray-400 text-sm">
        {t("common.loading")}
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 h-56 flex flex-col items-center justify-center text-gray-400 text-sm gap-1">
        <span>{t("performance.noHistoricalData")}</span>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 overflow-hidden py-4">
      {header}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="pf-pos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#16a34a" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#16a34a" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="pf-neg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#dc2626" stopOpacity={0} />
              <stop offset="100%" stopColor="#dc2626" stopOpacity={0.12} />
            </linearGradient>
          </defs>

          <XAxis
            dataKey="date"
            ticks={yearTicks}
            tickFormatter={(d) => new Date(d).getFullYear().toString()}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={false}
          />

          <YAxis
            tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)} %`}
            tick={{ fontSize: 10, fill: "#d1d5db" }}
            tickLine={false}
            axisLine={false}
            width={52}
            orientation="right"
          />

          <ReferenceLine y={0} stroke="#e5e7eb" strokeWidth={1} />

          <Tooltip content={<CustomTooltip />} />

          <Area
            type="monotone"
            dataKey="pct"
            stroke={color}
            strokeWidth={2}
            fill={isPositive ? "url(#pf-pos)" : "url(#pf-neg)"}
            dot={false}
            activeDot={{ r: 4, fill: color, stroke: "#fff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
