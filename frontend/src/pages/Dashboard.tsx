import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { PriceChart } from "@/components/prices/PriceChart";
import { PriceTicker } from "@/components/prices/PriceTicker";
import { useLivePrices } from "@/hooks/useLivePrices";
import { useAuth } from "@/hooks/useAuth";
import { priceService } from "@/services/prices";
import { accountService, transactionService, type Account, type Transaction } from "@/services/transactions";
import type { PriceOut } from "@/services/prices";

export function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data: transactions = [] } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => transactionService.list({ limit: 500 }),
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const portfolioAssets = Array.from(
    new Map(transactions.map((tx) => [tx.asset_id, tx.asset])).values()
  );
  const assetIds = portfolioAssets.map((a) => a.id);

  const livePrices = useLivePrices(assetIds);

  const { data: initialPrices = [] } = useQuery({
    queryKey: ["prices-initial", assetIds.join(",")],
    queryFn: async () => {
      const results = await Promise.allSettled(assetIds.map((id) => priceService.getPrice(id)));
      return results
        .filter((r): r is PromiseFulfilledResult<PriceOut> => r.status === "fulfilled")
        .map((r) => r.value);
    },
    enabled: assetIds.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const allPrices: Record<number, PriceOut> = Object.fromEntries([
    ...initialPrices.map((p) => [p.asset_id, p]),
    ...Object.entries(livePrices),
  ]);

  // ── Calcoli aggregati ───────────────────────────────────────────────────

  function calcPortfolioValue(txList: Transaction[]): number {
    const byAsset: Record<number, number> = {};
    for (const tx of txList) {
      if (tx.type === "BUY")  byAsset[tx.asset_id] = (byAsset[tx.asset_id] ?? 0) + tx.quantity;
      if (tx.type === "SELL") byAsset[tx.asset_id] = (byAsset[tx.asset_id] ?? 0) - tx.quantity;
    }
    return Object.entries(byAsset).reduce((sum, [assetId, qty]) => {
      const price = allPrices[Number(assetId)];
      if (!price || qty <= 0) return sum;
      return sum + qty * price.price * (price as any).exchange_rate ?? 1;
    }, 0);
  }

  function calcCostBasis(txList: Transaction[]): number {
    return txList.filter((tx) => tx.type === "BUY").reduce((s, tx) => s + tx.total_eur, 0);
  }

  function calcDailyChange(txList: Transaction[]): number {
    const byAsset: Record<number, number> = {};
    for (const tx of txList) {
      if (tx.type === "BUY")  byAsset[tx.asset_id] = (byAsset[tx.asset_id] ?? 0) + tx.quantity;
      if (tx.type === "SELL") byAsset[tx.asset_id] = (byAsset[tx.asset_id] ?? 0) - tx.quantity;
    }
    return Object.entries(byAsset).reduce((sum, [assetId, qty]) => {
      const p = allPrices[Number(assetId)];
      if (!p || qty <= 0) return sum;
      const prev = p.prev_close ?? p.price;
      return sum + qty * (p.price - prev);
    }, 0);
  }

  const hasPrices = Object.keys(allPrices).length > 0;
  const totalValue = calcPortfolioValue(transactions);
  const totalCost = calcCostBasis(transactions);
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const dailyChange = calcDailyChange(transactions);

  // ── Breakdown per conto ─────────────────────────────────────────────────

  const accountBreakdown = accounts.map((acc) => {
    const accTxs = transactions.filter((tx) => tx.account_id === acc.id);
    const value = calcPortfolioValue(accTxs);
    const cost = calcCostBasis(accTxs);
    const pnl = value - cost;
    const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
    const daily = calcDailyChange(accTxs);
    return { acc, value, cost, pnl, pnlPct, daily, txCount: accTxs.length };
  }).filter((b) => b.txCount > 0);

  return (
    <>
      <TopBar title="Dashboard" />
      <main className="flex-1 p-6 space-y-6">
        {/* Saluto */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Ciao, {user?.name} 👋</h2>
          <p className="text-gray-500 mt-0.5 text-sm">
            {new Date().toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        </div>

        {/* KPI Cards — portafoglio totale */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard
            label="Valore portafoglio"
            value={hasPrices ? `€ ${totalValue.toLocaleString("it-IT", { minimumFractionDigits: 2 })}` : "—"}
            sub={hasPrices ? `Costo: € ${totalCost.toLocaleString("it-IT", { minimumFractionDigits: 2 })}` : undefined}
          />
          <KpiCard
            label="P&L totale"
            value={hasPrices ? `€ ${totalPnl.toLocaleString("it-IT", { minimumFractionDigits: 2, signDisplay: "always" })}` : "—"}
            sub={hasPrices ? `${totalPnlPct.toFixed(2)}%` : undefined}
            positive={hasPrices ? totalPnl >= 0 : undefined}
          />
          <KpiCard
            label="Variazione oggi"
            value={hasPrices ? `€ ${dailyChange.toLocaleString("it-IT", { minimumFractionDigits: 2, signDisplay: "always" })}` : "—"}
            positive={hasPrices ? dailyChange >= 0 : undefined}
          />
        </div>

        {portfolioAssets.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <p className="text-sm">Aggiungi le prime transazioni per vedere prezzi e performance.</p>
          </div>
        ) : (
          <>
            {/* Breakdown per conto — visibile solo se hai più di un conto attivo */}
            {accountBreakdown.length > 1 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-700">Per conto</h3>
                  <button
                    onClick={() => navigate("/impostazioni")}
                    className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                  >
                    Gestisci conti <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {accountBreakdown.map(({ acc, value, cost, pnl, pnlPct, daily }) => (
                    <button
                      key={acc.id}
                      onClick={() => navigate(`/transazioni?account=${acc.id}`)}
                      className="bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-brand-300 hover:shadow-sm transition-all group"
                    >
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <p className="text-xs text-gray-400 truncate">{acc.broker ?? "—"}</p>
                          <p className="text-sm font-semibold text-gray-900 truncate">{acc.name}</p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-brand-500 transition-colors flex-shrink-0 mt-0.5" />
                      </div>
                      <div className="mt-3 space-y-1">
                        <div className="flex justify-between items-baseline">
                          <span className="text-xs text-gray-400">Valore</span>
                          <span className="text-sm font-bold text-gray-900">
                            {hasPrices ? `€ ${value.toLocaleString("it-IT", { maximumFractionDigits: 0 })}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-xs text-gray-400">P&L</span>
                          <span className={`text-xs font-semibold ${hasPrices ? (pnl >= 0 ? "text-green-600" : "text-red-600") : "text-gray-400"}`}>
                            {hasPrices
                              ? `${pnl >= 0 ? "+" : ""}€ ${pnl.toLocaleString("it-IT", { maximumFractionDigits: 0 })} (${pnlPct.toFixed(1)}%)`
                              : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-xs text-gray-400">Oggi</span>
                          <span className={`text-xs font-semibold ${hasPrices ? (daily >= 0 ? "text-green-600" : "text-red-600") : "text-gray-400"}`}>
                            {hasPrices
                              ? `${daily >= 0 ? "+" : ""}€ ${daily.toLocaleString("it-IT", { maximumFractionDigits: 0 })}`
                              : "—"}
                          </span>
                        </div>
                      </div>
                      {/* Barra proporzionale al valore */}
                      {hasPrices && totalValue > 0 && (
                        <div className="mt-3 h-1 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-brand-400 rounded-full"
                            style={{ width: `${Math.min((value / totalValue) * 100, 100)}%` }}
                          />
                        </div>
                      )}
                      {hasPrices && totalValue > 0 && (
                        <p className="text-xs text-gray-300 mt-1 text-right">
                          {((value / totalValue) * 100).toFixed(1)}% del totale
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Prezzi live */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Prezzi live
                <span className="ml-2 inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              </h3>
              <div className="flex flex-wrap gap-2">
                {portfolioAssets.map((asset) => {
                  const p = allPrices[asset.id];
                  if (!p) return (
                    <span key={asset.id} className="px-3 py-1.5 rounded-lg bg-gray-100 text-xs text-gray-400">
                      {asset.symbol} — caricamento...
                    </span>
                  );
                  return <PriceTicker key={asset.id} price={p} />;
                })}
              </div>
            </div>

            {/* Grafico del primo asset */}
            {portfolioAssets[0] && (
              <PriceChart
                assetId={portfolioAssets[0].id}
                symbol={portfolioAssets[0].symbol}
                currency={portfolioAssets[0].currency}
              />
            )}

            {/* Tabella posizioni */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700">Posizioni aperte</h3>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-50 text-left">
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">Asset</th>
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Qtà</th>
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Prezzo</th>
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Valore</th>
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase text-right">Var. %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {portfolioAssets.map((asset) => {
                    const qty = transactions
                      .filter((tx) => tx.asset_id === asset.id && tx.type === "BUY")
                      .reduce((s, tx) => s + tx.quantity, 0);
                    const p = allPrices[asset.id];
                    const value = p ? qty * p.price : null;
                    const positive = p ? p.change_pct >= 0 : null;
                    return (
                      <tr key={asset.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-3">
                          <div className="font-medium text-gray-900">{asset.symbol}</div>
                          <div className="text-xs text-gray-400 truncate max-w-[200px]">{asset.name}</div>
                        </td>
                        <td className="px-5 py-3 text-right text-gray-600">
                          {qty.toLocaleString("it-IT", { maximumFractionDigits: 6 })}
                        </td>
                        <td className="px-5 py-3 text-right text-gray-700">
                          {p ? `${p.price.toFixed(4)} ${p.currency}` : "—"}
                        </td>
                        <td className="px-5 py-3 text-right font-medium text-gray-900">
                          {value !== null ? `€ ${value.toLocaleString("it-IT", { minimumFractionDigits: 2 })}` : "—"}
                        </td>
                        <td className="px-5 py-3 text-right">
                          {p ? (
                            <span className={`flex items-center justify-end gap-1 text-xs font-semibold ${positive ? "text-green-600" : "text-red-600"}`}>
                              {positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                              {positive ? "+" : ""}{p.change_pct.toFixed(2)}%
                            </span>
                          ) : <Minus className="w-3 h-3 text-gray-300 ml-auto" />}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </>
  );
}

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
