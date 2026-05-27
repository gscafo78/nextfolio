import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { Coins, TrendingUp, TrendingDown } from "lucide-react";
import { TopBar } from "@/components/layout/TopBar";
import { api } from "@/services/api";

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
  return v.toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d });
}

// ── Componente principale ──────────────────────────────────────────────────────

export function Dividendi() {
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
        <TopBar title="Dividendi & Cedole" />
        <main className="flex-1 p-4 md:p-6 flex items-center justify-center">
          <p className="text-sm text-gray-400">Caricamento...</p>
        </main>
      </>
    );
  }

  const isEmpty = !data || data.total_income_eur === 0;

  // Prendi gli ultimi 24 mesi per il grafico mensile
  const monthlyData = (data?.by_month ?? []).slice(-24);

  return (
    <>
      <TopBar title="Dividendi & Cedole" />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-6">

        {isEmpty ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <Coins className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Nessun dividendo o cedola registrati.</p>
          </div>
        ) : (
          <>
            {/* KPI */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Totale incassato</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">€ {fmt(data!.total_income_eur)}</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Anno corrente</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  € {fmt((data!.by_year.find((y) => y.year === new Date().getFullYear())?.amount_eur ?? 0))}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Media annua</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  € {fmt(data!.by_year.length > 0 ? data!.total_income_eur / data!.by_year.length : 0)}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Asset pagatori</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{data!.yield_on_cost.length}</p>
              </div>
            </div>

            {/* Grafico mensile */}
            {monthlyData.length > 1 && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Reddito mensile (ultimi 24 mesi)</h3>
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
                      tickFormatter={(v) => `€${v}`}
                      width={50}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                      formatter={(v: number) => [`€ ${fmt(v)}`, "Incassato"]}
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
                  <h3 className="text-sm font-semibold text-gray-700">Reddito per anno</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-left">Anno</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Importo EUR</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Crescita YoY</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {[...data!.by_year].reverse().map((y) => (
                        <tr key={y.year} className="hover:bg-gray-50">
                          <td className="px-5 py-3 font-semibold text-gray-900">{y.year}</td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            + € {fmt(y.amount_eur)}
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
                  <h3 className="text-sm font-semibold text-gray-700">Yield on Cost per asset</h3>
                  <p className="text-xs text-gray-400 mt-0.5">Reddito totale / costo d&apos;acquisto storico</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50">
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-left">Asset</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Costo d&apos;acquisto</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Reddito totale</th>
                        <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">YoC %</th>
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
                            € {fmt(entry.cost_basis_eur)}
                          </td>
                          <td className="px-5 py-3 text-right font-medium text-green-600">
                            + € {fmt(entry.total_income_eur)}
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
