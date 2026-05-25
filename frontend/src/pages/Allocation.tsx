import { useQuery } from "@tanstack/react-query";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieIcon } from "lucide-react";
import { TopBar } from "@/components/layout/TopBar";
import { portfolioService, type AllocationItem, type PositionOut } from "@/services/portfolio";

// ── Costanti ──────────────────────────────────────────────────────────────────

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
  "#ef4444", "#06b6d4", "#84cc16", "#f97316",
  "#ec4899", "#14b8a6", "#a855f7", "#fb923c",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, d = 2) {
  return v.toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function buildHoldingItems(positions: PositionOut[], total: number): AllocationItem[] {
  if (total <= 0) return [];
  return positions
    .filter((p) => p.current_value_eur != null && p.current_value_eur > 0)
    .map((p) => ({
      label: p.symbol,
      value_eur: p.current_value_eur!,
      pct: Math.round((p.current_value_eur! / total) * 1000) / 10,
      count: 1,
    }))
    .sort((a, b) => b.value_eur - a.value_eur);
}

function buildExchangeItems(positions: PositionOut[], total: number): AllocationItem[] {
  if (total <= 0) return [];
  const map = new Map<string, number>();
  for (const p of positions) {
    if (p.current_value_eur) {
      map.set(p.exchange, (map.get(p.exchange) ?? 0) + p.current_value_eur);
    }
  }
  return [...map.entries()]
    .map(([label, value_eur]) => ({
      label,
      value_eur: Math.round(value_eur * 100) / 100,
      pct: Math.round((value_eur / total) * 1000) / 10,
      count: 0,
    }))
    .sort((a, b) => b.value_eur - a.value_eur);
}

// ── Sub-componenti ────────────────────────────────────────────────────────────

function SmallDonutCard({ title, items }: { title: string; items: AllocationItem[] }) {
  if (!items.length) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="flex gap-4 items-center">
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
              formatter={(v: number) => [`€ ${fmt(v)}`, ""]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5 min-w-0">
          {items.map((item, i) => (
            <div key={item.label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="text-xs text-gray-600 truncate flex-1">{item.label}</span>
              <span className="text-xs font-semibold text-gray-800 tabular-nums">{item.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const RADIAN = Math.PI / 180;

function renderOuterLabel({ cx, cy, midAngle, outerRadius, pct, name }: {
  cx: number; cy: number; midAngle: number; outerRadius: number; pct: number; name: string;
}) {
  if (pct < 3) return null;
  const radius = outerRadius + 32;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text
      x={x}
      y={y}
      fill="#6b7280"
      textAnchor={x > cx ? "start" : "end"}
      dominantBaseline="central"
      fontSize={11}
      fontFamily="inherit"
    >
      {name}
    </text>
  );
}

function HoldingDonut({ items }: { items: AllocationItem[] }) {
  if (!items.length) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Per Holding</h3>
      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0" style={{ minHeight: 360 }}>
          <ResponsiveContainer width="100%" height={360}>
            <PieChart>
              <Pie
                data={items}
                dataKey="value_eur"
                nameKey="label"
                cx="50%"
                cy="50%"
                innerRadius={90}
                outerRadius={140}
                strokeWidth={1}
                stroke="#f8fafc"
                labelLine={{ stroke: "#d1d5db", strokeWidth: 1 }}
                label={renderOuterLabel}
              >
                {items.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v: number, _: string, props: { payload?: AllocationItem }) => [
                  `€ ${fmt(v)}  (${props.payload?.pct ?? 0}%)`,
                  "",
                ]}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="w-52 flex-shrink-0 space-y-1.5 pt-2">
          {items.map((item, i) => (
            <div key={item.label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="text-xs text-gray-600 truncate flex-1" title={item.label}>{item.label}</span>
              <span className="text-xs font-semibold text-gray-800 tabular-nums">{item.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Allocation() {
  const { data: dashboard } = useQuery({
    queryKey: ["portfolio-dashboard"],
    queryFn: portfolioService.getDashboard,
    staleTime: 5 * 60 * 1000,
  });
  const allocation = dashboard?.allocation;
  const positions = dashboard?.positions ?? [];

  const total = allocation?.total_value_eur ?? 0;
  const holdingItems = buildHoldingItems(positions, total);
  const exchangeItems = buildExchangeItems(positions, total);

  const isEmpty = !allocation || total === 0;

  return (
    <>
      <TopBar title="Allocazioni" />
      <main className="flex-1 p-6 space-y-6">

        {isEmpty ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <PieIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Aggiungi transazioni per vedere l&apos;allocazione.</p>
          </div>
        ) : (
          <>
            {/* Quota del patrimonio netto */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-sm font-medium text-gray-600">
                  Quota del patrimonio netto
                  <span className="ml-2 text-xs text-amber-500 font-semibold">● Portafoglio</span>
                </span>
                <span className="text-sm font-bold text-gray-900 tabular-nums">100,00 %</span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full bg-emerald-400" style={{ width: "100%" }} />
              </div>
              <div className="mt-2 text-xs text-gray-400 text-right">
                Totale: <span className="font-semibold text-gray-700">€ {fmt(total)}</span>
              </div>
            </div>

            {/* Per Piattaforma / Valuta / Asset Class */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              <SmallDonutCard title="Per Piattaforma" items={allocation.by_account} />
              <SmallDonutCard title="Per Valuta" items={allocation.by_currency} />
              <SmallDonutCard title="Per Classe di Asset" items={allocation.by_type} />
            </div>

            {/* Per Holding */}
            <HoldingDonut items={holdingItems} />

            {/* Per Borsa */}
            {exchangeItems.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                <SmallDonutCard title="Per Borsa" items={exchangeItems} />
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
