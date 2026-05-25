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
import { it } from "date-fns/locale";
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
}

export function PortfolioChart({ series, isLoading }: PortfolioChartProps) {
  const pnlAtStart = series[0]?.pnl_eur ?? 0;

  const chartData: ChartPoint[] = series.map((pt) => ({
    date: pt.date,
    value: pt.value_eur,
    pct: pt.twrr_pct,
    pnlEur: pt.pnl_eur - pnlAtStart,
  }));

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
          {format(new Date(label), "d MMM yyyy", { locale: it })}
        </p>
        <p className={`font-bold text-sm ${pos ? "text-green-600" : "text-red-600"}`}>
          {pos ? "+" : ""}{pt.pct.toFixed(2)} %
        </p>
        <p className={`font-medium ${pos ? "text-green-600" : "text-red-600"}`}>
          {pos ? "+" : "−"} € {Math.abs(pnlEur).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className="text-gray-400 mt-0.5">
          Valore: € {pt.value.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 h-56 flex items-center justify-center text-gray-400 text-sm">
        Caricamento…
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 h-56 flex flex-col items-center justify-center text-gray-400 text-sm gap-1">
        <span>Nessun dato storico per il periodo selezionato.</span>
        <span className="text-xs">Avvia "Aggiorna storico" per scaricare i prezzi.</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden py-4">
      <ResponsiveContainer width="100%" height={220}>
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

          <XAxis dataKey="date" hide />

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
