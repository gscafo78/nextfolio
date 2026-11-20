import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { getIntlLocale } from "@/utils/format";
import i18n from "@/i18n";
import { useZenMode } from "@/context/ThemeContext";
import type { AllocationItem } from "@/services/portfolio";

export const CHART_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
  "#ef4444", "#06b6d4", "#84cc16", "#f97316",
  "#ec4899", "#14b8a6", "#a855f7", "#fb923c",
];
const COLORS = CHART_COLORS;

function fmt(v: number, d = 2) {
  return v.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** Ciambella con legenda e barre percentuali (pagine Allocazione e Pianifica). */
export function SmallDonutCard({ title, items }: { title: string; items: AllocationItem[] }) {
  if (!items.length) return null;
  const maxPct = Math.max(...items.map((it) => it.pct));
  const zenMode = useZenMode();
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="flex flex-col sm:flex-row gap-3 items-center sm:items-start">
        <ResponsiveContainer width={130} height={130}>
          <PieChart>
            <Pie
              data={items}
              dataKey="value_eur"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={60}
              strokeWidth={1}
              stroke="#f8fafc"
            >
              {items.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => [zenMode ? "•••••" : `€ ${fmt(v)}`, ""]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="w-full sm:flex-1 space-y-2 min-w-0">
          {items.map((item, i) => (
            <div key={item.label}>
              <div className="flex items-center gap-2 mb-0.5">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-xs text-gray-600 truncate flex-1">{item.label}</span>
                <span className="text-xs font-semibold text-gray-800 tabular-nums">{item.pct}%</span>
              </div>
              <div className="ml-4 h-1 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${maxPct > 0 ? (item.pct / maxPct) * 100 : 0}%`,
                    backgroundColor: COLORS[i % COLORS.length],
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
