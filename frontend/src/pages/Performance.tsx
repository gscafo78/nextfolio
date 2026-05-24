import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { TrendingUp, TrendingDown, Minus, BarChart2, Coins, ArrowDownLeft } from "lucide-react";
import { format, parseISO } from "date-fns";
import { it } from "date-fns/locale";
import { TopBar } from "@/components/layout/TopBar";
import { portfolioService, type PositionOut, type AllocationItem } from "@/services/portfolio";

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

const TYPE_LABELS: Record<string, string> = {
  STOCK: "Azioni", ETF: "ETF", BOND: "Obbligazioni",
  CRYPTO: "Crypto", COMMODITY: "Commodity", REIT: "REIT",
};

const DIV_LABELS: Record<string, string> = {
  DIVIDEND: "Dividendo", COUPON: "Cedola", INTEREST: "Interesse",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, digits = 2) {
  return v.toLocaleString("it-IT", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtSign(v: number, digits = 2) {
  return v.toLocaleString("it-IT", { minimumFractionDigits: digits, maximumFractionDigits: digits, signDisplay: "always" });
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
              formatter={(v: number) => [`€ ${fmt(v)}`, ""]}
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

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Performance() {
  const [period, setPeriod] = useState("1y");

  const { data: summary, isLoading: loadingSum } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: portfolioService.getSummary,
  });

  const { data: positions = [], isLoading: loadingPos } = useQuery({
    queryKey: ["portfolio-positions"],
    queryFn: portfolioService.getPositions,
  });

  const { data: perf, isLoading: loadingPerf } = useQuery({
    queryKey: ["portfolio-performance", period],
    queryFn: () => portfolioService.getPerformance(period),
  });

  const { data: allocation } = useQuery({
    queryKey: ["portfolio-allocation"],
    queryFn: portfolioService.getAllocation,
  });

  const { data: dividends = [] } = useQuery({
    queryKey: ["portfolio-dividends"],
    queryFn: portfolioService.getDividends,
  });

  const hasSummary = !!summary;
  const series = perf?.series ?? [];
  const chartPositive = series.length < 2
    ? true
    : series[series.length - 1].pnl_eur >= 0;

  // Formatta le date per il tooltip del grafico
  const chartData = series.map((p) => ({
    ...p,
    dateLabel: format(parseISO(p.date), "d MMM yy", { locale: it }),
  }));

  return (
    <>
      <TopBar title="Performance" />
      <main className="flex-1 p-6 space-y-6">

        {/* KPI sommario */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <KpiCard
            label="Valore portafoglio"
            value={hasSummary ? `€ ${fmt(summary.total_value_eur)}` : "—"}
            sub={hasSummary ? `Investito: € ${fmt(summary.total_invested_eur)}` : undefined}
          />
          <KpiCard
            label="P&L totale"
            value={hasSummary ? `€ ${fmtSign(summary.total_pnl_eur)}` : "—"}
            sub={hasSummary ? `${fmtSign(summary.total_pnl_pct, 2)}%` : undefined}
            positive={hasSummary ? summary.total_pnl_eur >= 0 : undefined}
          />
          <KpiCard
            label="P&L non realizzato"
            value={hasSummary ? `€ ${fmtSign(summary.unrealized_pnl_eur)}` : "—"}
            sub={hasSummary ? "Su posizioni aperte" : undefined}
            positive={hasSummary ? summary.unrealized_pnl_eur >= 0 : undefined}
          />
          <KpiCard
            label="P&L realizzato"
            value={hasSummary ? `€ ${fmtSign(summary.realized_pnl_eur)}` : "—"}
            sub={hasSummary ? "Da vendite chiuse" : undefined}
            positive={hasSummary ? summary.realized_pnl_eur >= 0 : undefined}
          />
        </div>

        {positions.length === 0 && !loadingPos ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <BarChart2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Aggiungi transazioni per vedere la performance.</p>
          </div>
        ) : (
          <>
            {/* Grafico performance */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">Andamento portafoglio</h3>
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
                <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Caricamento...</div>
              ) : chartData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                  Nessun dato storico disponibile. Avvia un backfill dalla pagina Asset.
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
                      dataKey="dateLabel"
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`}
                      width={52}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                      formatter={(v: number, name: string) => [
                        `€ ${fmt(v)}`,
                        name === "value_eur" ? "Valore" : "Investito",
                      ]}
                      labelFormatter={(l) => l}
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

            {/* Allocazione */}
            {allocation && allocation.total_value_eur > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                <AllocationPie title="Per tipo asset" items={allocation.by_type} />
                <AllocationPie title="Per valuta" items={allocation.by_currency} />
                {allocation.by_account.length > 1 && (
                  <AllocationPie title="Per conto" items={allocation.by_account} />
                )}
              </div>
            )}

            {/* Tabella posizioni */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">Posizioni aperte</h3>
                <span className="ml-auto text-xs text-gray-400">{positions.length} asset</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-50 text-left">
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Asset</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Qtà</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">PMC</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Prezzo att.</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Valore</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">P&L non real.</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">P&L real.</th>
                      <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Var. oggi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {positions.map((pos) => (
                      <PositionRow key={pos.asset_id} pos={pos} />
                    ))}
                  </tbody>
                  {positions.length > 0 && summary && (
                    <tfoot>
                      <tr className="border-t border-gray-200 bg-gray-50">
                        <td colSpan={4} className="px-5 py-2 text-xs text-gray-400">Totale portafoglio</td>
                        <td className="px-5 py-2 text-right text-sm font-semibold text-gray-900">
                          € {fmt(summary.total_value_eur)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.unrealized_pnl_eur)}`}>
                          € {fmtSign(summary.unrealized_pnl_eur)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.realized_pnl_eur)}`}>
                          € {fmtSign(summary.realized_pnl_eur)}
                        </td>
                        <td className={`px-5 py-2 text-right text-sm font-semibold ${colorClass(summary.daily_change_eur)}`}>
                          € {fmtSign(summary.daily_change_eur)}
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
                  <h3 className="text-sm font-semibold text-gray-700">Dividendi e cedole</h3>
                  <span className="ml-auto text-xs text-gray-400">
                    Totale: € {fmt(dividends.reduce((s, d) => s + d.amount_eur, 0))}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50 text-left">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Data</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Tipo</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Asset</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Conto</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Importo EUR</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {dividends.map((d) => (
                        <tr key={d.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-5 py-3 text-gray-600">
                            {format(parseISO(d.date), "dd MMM yyyy", { locale: it })}
                          </td>
                          <td className="px-5 py-3">
                            <span className="text-xs font-medium text-blue-600">
                              {DIV_LABELS[d.type] ?? d.type}
                            </span>
                          </td>
                          <td className="px-5 py-3">
                            <div className="font-medium text-gray-900">{d.symbol}</div>
                            <div className="text-xs text-gray-400 truncate max-w-[180px]">{d.name}</div>
                          </td>
                          <td className="px-5 py-3 text-xs text-gray-500">{d.account_name}</td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            + € {fmt(d.amount_eur)}
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

function PositionRow({ pos }: { pos: PositionOut }) {
  const hasPrices = pos.current_value_eur !== null;
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-5 py-3">
        <div className="font-medium text-gray-900">{pos.symbol}</div>
        <div className="text-xs text-gray-400 truncate max-w-[200px]">{pos.name}</div>
        <div className="text-xs text-gray-300">{TYPE_LABELS[pos.asset_type] ?? pos.asset_type} · {pos.exchange}</div>
      </td>
      <td className="px-5 py-3 text-right text-gray-600">
        {pos.quantity.toLocaleString("it-IT", { maximumFractionDigits: 6 })}
      </td>
      <td className="px-5 py-3 text-right text-gray-600 font-mono text-xs">
        € {fmt(pos.pmc_eur, 4)}
      </td>
      <td className="px-5 py-3 text-right">
        {hasPrices ? (
          <div>
            <div className="text-gray-700 font-mono text-xs">
              {pos.current_price !== null
                ? `${pos.current_price.toFixed(4)} ${pos.currency}`
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
        {hasPrices ? `€ ${fmt(pos.current_value_eur!)}` : "—"}
      </td>
      <td className="px-5 py-3 text-right">
        {pos.unrealized_pnl_eur !== null ? (
          <div>
            <div className={`text-xs font-semibold ${colorClass(pos.unrealized_pnl_eur)}`}>
              € {fmtSign(pos.unrealized_pnl_eur)}
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
          ? `€ ${fmtSign(pos.realized_pnl_eur)}`
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
