import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import { priceService, type Period } from "@/services/prices";

const PERIODS: { label: string; value: Period }[] = [
  { label: "1S", value: "1w" },
  { label: "1M", value: "1mo" },
  { label: "3M", value: "3mo" },
  { label: "6M", value: "6mo" },
  { label: "1A", value: "1y" },
  { label: "3A", value: "3y" },
  { label: "5A", value: "5y" },
  { label: "Max", value: "max" },
];

interface PriceChartProps {
  assetId: number;
  symbol: string;
  currency?: string;
}

export function PriceChart({ assetId, symbol, currency = "EUR" }: PriceChartProps) {
  const [period, setPeriod] = useState<Period>("1y");

  const { data = [], isLoading } = useQuery({
    queryKey: ["price-history", assetId, period],
    queryFn: () => priceService.getHistory(assetId, period, "live"),
    staleTime: 5 * 60 * 1000,
  });

  const isPositive = data.length >= 2
    ? data[data.length - 1].close >= data[0].close
    : true;
  const color = isPositive ? "#16a34a" : "#dc2626";

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    if (period === "1w") return format(d, "EEE", { locale: it });
    if (period === "1mo") return format(d, "d MMM", { locale: it });
    if (period === "3mo" || period === "6mo") return format(d, "MMM", { locale: it });
    return format(d, "MMM yy", { locale: it });
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">Andamento {symbol}</h3>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                period === p.value
                  ? "bg-brand-500 text-white"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
          Caricamento...
        </div>
      ) : data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
          Storico non disponibile — avvia il backfill
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`grad-${assetId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => v.toFixed(2)}
              width={55}
            />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)} ${currency}`, "Prezzo"]}
              labelFormatter={(l) => format(new Date(l), "d MMM yyyy", { locale: it })}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              fill={`url(#grad-${assetId})`}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
