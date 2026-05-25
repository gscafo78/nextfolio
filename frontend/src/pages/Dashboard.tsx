import { useEffect, useRef, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { ArrowRight, RefreshCw, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { PortfolioChart } from "@/components/portfolio/PortfolioChart";
import { useLivePrices } from "@/hooks/useLivePrices";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/services/api";
import { accountService, transactionService } from "@/services/transactions";
import { portfolioService, type PositionOut } from "@/services/portfolio";
import { HoldingDetailModal } from "@/components/portfolio/HoldingDetailModal";

type SortField = "allocation" | "value" | "change" | "performance" | "name";
type SortDir   = "asc" | "desc";
type Period    = string;

interface PeriodOption { label: string; value: Period }

function buildPeriodOptions(firstYear: number | null): PeriodOption[] {
  const currentYear = new Date().getFullYear();
  const base: PeriodOption[] = [
    { label: "Oggi",   value: "today" },
    { label: "WTD",    value: "wtd"   },
    { label: "MTD",    value: "mtd"   },
    { label: "YTD",    value: "ytd"   },
    { label: "1 anno", value: "1y"    },
    { label: "Max",    value: "max"   },
  ];
  if (firstYear) {
    for (let y = currentYear; y >= firstYear; y--)
      base.push({ label: String(y), value: String(y) });
  }
  return base;
}

// ── Period selector (dropdown) ────────────────────────────────────────────────
function PeriodSelector({
  period, options, onChange,
}: { period: Period; options: PeriodOption[]; onChange: (p: Period) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === period);

  useEffect(() => {
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-sm font-medium text-gray-700 border border-gray-200 rounded-lg px-3 py-1.5 hover:border-gray-400 bg-white transition-colors shadow-sm"
      >
        {selected?.label ?? period}
        {open ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-52 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
          <div className="max-h-72 overflow-y-auto py-1">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={`w-full text-left px-4 py-2 text-sm transition-colors
                  ${period === opt.value
                    ? "bg-brand-50 text-brand-700 font-semibold"
                    : "text-gray-700 hover:bg-gray-50"}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export function Dashboard() {
  const { user } = useAuth();
  const navigate  = useNavigate();

  const [period,    setPeriod]    = useState<Period>(
    () => localStorage.getItem("dashboard_period") ?? "max"
  );
  const [showClosed, setShowClosed] = useState(false);
  const [sortField, setSortField] = useState<SortField>("allocation");
  const [sortDir,   setSortDir]   = useState<SortDir>("desc");
  const [backfillDone, setBackfillDone] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);

  const { mutate: runBackfill, isPending: backfillPending } = useMutation({
    mutationFn: () => api.post("/portfolio/backfill-history"),
    onSuccess: () => setBackfillDone("Backfill avviato"),
    onError:   () => setBackfillDone("Errore avvio backfill"),
  });

  // ── Data queries ───────────────────────────────────────────────────────────
  const { data: transactions = [] } = useQuery({
    queryKey: ["transactions"],
    queryFn:  () => transactionService.list({ limit: 500 }),
  });
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn:  accountService.list,
  });
  const { data: dashboard, isLoading: positionsLoading } = useQuery({
    queryKey: ["portfolio-dashboard"],
    queryFn:  portfolioService.getDashboard,
    staleTime: 5 * 60 * 1000,
  });
  const positions: PositionOut[] = dashboard?.positions ?? [];
  const { data: perfData, isLoading: perfLoading } = useQuery({
    queryKey: ["portfolio-performance", period],
    queryFn:  () => portfolioService.getPerformance(period),
    staleTime: 5 * 60 * 1000,
  });

  const accountPerfQueries = useQueries({
    queries: accounts.map((acc) => ({
      queryKey: ["portfolio-performance", period, acc.id],
      queryFn:  () => portfolioService.getPerformance(period, acc.id),
      staleTime: 5 * 60 * 1000,
      enabled:  period !== "today",
    })),
  });
  const accPerfMap = Object.fromEntries(
    accounts.map((acc, i) => [acc.id, accountPerfQueries[i]?.data])
  );

  // ── Live prices (WebSocket) ────────────────────────────────────────────────
  const assetIds = positions.map((p) => p.asset_id);
  const livePrices = useLivePrices(assetIds);

  const enrichedPositions: PositionOut[] = positions.map((pos) => {
    const live = livePrices[pos.asset_id];
    if (!live || !pos.current_price || !pos.current_price_eur) return pos;
    const fx = pos.current_price > 0 ? pos.current_price_eur / pos.current_price : 1.0;
    const liveValueEur = pos.quantity * live.price * fx;
    const livePnl      = liveValueEur - pos.total_invested_eur;
    const livePnlPct   = pos.total_invested_eur > 0 ? (livePnl / pos.total_invested_eur) * 100 : 0;
    return { ...pos, current_price: live.price, current_price_eur: live.price * fx,
      current_value_eur: liveValueEur, unrealized_pnl_eur: livePnl,
      unrealized_pnl_pct: livePnlPct, change_pct: live.change_pct };
  });

  // ── Aggregates ─────────────────────────────────────────────────────────────
  const totalValue    = enrichedPositions.reduce((s, p) => s + (p.current_value_eur ?? 0), 0);
  const totalInvested = enrichedPositions.reduce((s, p) => s + p.total_invested_eur, 0);
  const hasPrices     = enrichedPositions.some((p) => p.current_value_eur != null);

  const dailyChange = enrichedPositions.reduce((s, p) => {
    if (p.change_pct == null || !p.current_value_eur) return s;
    return s + p.current_value_eur * (p.change_pct / 100) / (1 + p.change_pct / 100);
  }, 0);

  const dailyChangePct = hasPrices && (totalValue - dailyChange) !== 0
    ? (dailyChange / (totalValue - dailyChange)) * 100
    : null;

  // Period performance — TWRR; for "oggi" fall back to daily change (TWRR needs ≥2 points)
  const perfSeries = perfData?.series ?? [];
  const pnlAtStart = perfSeries[0]?.pnl_eur ?? 0;
  const lastPerfPt = perfSeries[perfSeries.length - 1];

  const periodPnl = period === "today"
    ? (hasPrices ? dailyChange : null)
    : (lastPerfPt ? lastPerfPt.pnl_eur - pnlAtStart : null);

  const periodPnlPct = period === "today"
    ? dailyChangePct
    : (lastPerfPt ? lastPerfPt.twrr_pct : null);

  // For "oggi": synthesise a 2-point series from live prices.
  // price_history has no intraday data so perfSeries is always empty for today's date.
  const chartSeries = (() => {
    if (period !== "today" || !hasPrices) return perfSeries;
    const prevValue = totalValue - dailyChange;
    const todayStr  = new Date().toISOString().slice(0, 10);
    const prevStr   = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    return [
      { date: prevStr,  value_eur: prevValue, invested_eur: totalInvested, pnl_eur: prevValue - totalInvested, twrr_pct: 0 },
      { date: todayStr, value_eur: totalValue, invested_eur: totalInvested, pnl_eur: totalValue - totalInvested, twrr_pct: dailyChangePct ?? 0 },
    ];
  })();

  // ── Transactions helpers ────────────────────────────────────────────────────
  const firstBuyDate: Record<number, string> = {};
  for (const tx of transactions) {
    if (tx.type === "BUY" && (!firstBuyDate[tx.asset_id] || tx.date < firstBuyDate[tx.asset_id]))
      firstBuyDate[tx.asset_id] = tx.date;
  }

  const allBuyDates = transactions.filter((tx) => tx.type === "BUY").map((tx) => tx.date);
  const firstYear   = allBuyDates.length > 0
    ? new Date(allBuyDates.reduce((a, b) => (a < b ? a : b))).getFullYear()
    : null;

  const periodOptions = buildPeriodOptions(firstYear);

  const netQtyByAsset: Record<number, number> = {};
  for (const tx of transactions) {
    if (tx.type === "BUY")  netQtyByAsset[tx.asset_id] = (netQtyByAsset[tx.asset_id] ?? 0) + tx.quantity;
    if (tx.type === "SELL") netQtyByAsset[tx.asset_id] = (netQtyByAsset[tx.asset_id] ?? 0) - tx.quantity;
  }

  // Closed positions
  const assetById = new Map(transactions.map((tx) => [tx.asset_id, tx.asset]));
  const closedRows = Array.from(assetById.values())
    .filter((a) => (netQtyByAsset[a.id] ?? 0) <= 0.000001 &&
      transactions.some((tx) => tx.asset_id === a.id && tx.type === "BUY"))
    .map((asset) => {
      const buyTxs    = transactions.filter((tx) => tx.asset_id === asset.id && tx.type === "BUY");
      const sellTxs   = transactions.filter((tx) => tx.asset_id === asset.id && tx.type === "SELL");
      const totalBought = buyTxs.reduce((s, tx) => s + tx.total_eur, 0);
      const totalSold   = sellTxs.reduce((s, tx) => s + tx.quantity * tx.price * tx.exchange_rate - tx.fee, 0);
      const pnl    = totalSold - totalBought;
      const pnlPct = totalBought > 0 ? (pnl / totalBought) * 100 : 0;
      const dates  = [...buyTxs, ...sellTxs].map((tx) => tx.date).sort();
      return { asset, firstDate: dates[0] ?? null, lastDate: dates[dates.length - 1] ?? null,
        totalBought, totalSold, pnl, pnlPct };
    });

  // Per-account breakdown
  const priceEurByAsset: Record<number, number> = Object.fromEntries(
    enrichedPositions.filter((p) => p.current_price_eur != null).map((p) => [p.asset_id, p.current_price_eur!])
  );
  const accountBreakdown = accounts.map((acc) => {
    const accTxs = transactions.filter((tx) => tx.account_id === acc.id);
    const accNetQty: Record<number, number> = {};
    for (const tx of accTxs) {
      if (tx.type === "BUY")  accNetQty[tx.asset_id] = (accNetQty[tx.asset_id] ?? 0) + tx.quantity;
      if (tx.type === "SELL") accNetQty[tx.asset_id] = (accNetQty[tx.asset_id] ?? 0) - tx.quantity;
    }
    const value = Object.entries(accNetQty).reduce((s, [aid, qty]) => {
      const p = priceEurByAsset[Number(aid)];
      return p && qty > 0 ? s + qty * p : s;
    }, 0);

    let pnl: number;
    let pnlPct: number;

    if (period === "today") {
      // Daily change per account from live change_pct
      const accDailyChange = Object.entries(accNetQty).reduce((s, [aid, qty]) => {
        const pos = enrichedPositions.find((p) => p.asset_id === Number(aid));
        if (!pos || pos.change_pct == null || !pos.current_price_eur || qty <= 0) return s;
        const cv = qty * pos.current_price_eur;
        return s + cv * (pos.change_pct / 100) / (1 + pos.change_pct / 100);
      }, 0);
      pnl    = accDailyChange;
      pnlPct = (value - accDailyChange) > 0 ? (accDailyChange / (value - accDailyChange)) * 100 : 0;
    } else {
      const series  = accPerfMap[acc.id]?.series ?? [];
      const firstPt = series[0];
      const lastPt  = series[series.length - 1];
      if (firstPt && lastPt) {
        pnl    = lastPt.pnl_eur - firstPt.pnl_eur;
        pnlPct = lastPt.twrr_pct;
      } else {
        // Fallback while loading: net invested all-time
        const buyCost      = accTxs.filter((tx) => tx.type === "BUY").reduce((s, tx) => s + tx.total_eur, 0);
        const sellProceeds = accTxs.filter((tx) => tx.type === "SELL")
          .reduce((s, tx) => s + tx.quantity * tx.price * tx.exchange_rate - tx.fee, 0);
        const netInvested = buyCost - sellProceeds;
        pnl    = value - netInvested;
        pnlPct = netInvested > 0 ? (pnl / netInvested) * 100 : 0;
      }
    }

    const txCount = accTxs.filter((tx) => tx.type === "BUY" || tx.type === "SELL").length;
    return { acc, value, pnl, pnlPct, txCount };
  }).filter((b) => b.txCount > 0);

  // Per-position period-aware P&L: daily change for "oggi", all-time for everything else
  const positionsWithPeriod = enrichedPositions.map((pos) => {
    if (period !== "today") return { ...pos, periodPnlEur: pos.unrealized_pnl_eur, periodPnlPct: pos.unrealized_pnl_pct };
    const dailyEur = pos.change_pct != null && pos.current_value_eur != null
      ? pos.current_value_eur * (pos.change_pct / 100) / (1 + pos.change_pct / 100)
      : null;
    return { ...pos, periodPnlEur: dailyEur, periodPnlPct: pos.change_pct };
  });

  // ── Sort positions ──────────────────────────────────────────────────────────
  function handleSort(field: SortField) {
    if (sortField === field) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortField(field); setSortDir("desc"); }
  }
  const sortedPositions = [...positionsWithPeriod].sort((a, b) => {
    if (sortField === "name")
      return sortDir === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    const vals: Record<SortField, [number, number]> = {
      allocation:  [a.current_value_eur ?? 0, b.current_value_eur ?? 0],
      value:       [a.current_value_eur ?? 0, b.current_value_eur ?? 0],
      change:      [a.periodPnlEur ?? 0,      b.periodPnlEur ?? 0],
      performance: [a.periodPnlPct ?? 0,      b.periodPnlPct ?? 0],
      name:        [0, 0],
    };
    const [va, vb] = vals[sortField];
    return sortDir === "asc" ? va - vb : vb - va;
  });

  // Period label for KPI card
  const periodLabel = periodOptions.find((o) => o.value === period)?.label ?? period;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <>
      <TopBar title="Dashboard" />
      <main className="flex-1 p-6 space-y-6">

        {/* Greeting + period selector */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Ciao, {user?.name} 👋</h2>
            <p className="text-gray-500 mt-0.5 text-sm">
              {new Date().toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long" })}
            </p>
          </div>
          <PeriodSelector period={period} options={periodOptions} onChange={(p) => { setPeriod(p); localStorage.setItem("dashboard_period", p); }} />
        </div>

        {positions.length === 0 && !positionsLoading ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <p className="text-sm">Aggiungi le prime transazioni per vedere prezzi e performance.</p>
          </div>
        ) : (
          <>
            {/* Performance chart */}
            <PortfolioChart series={chartSeries} isLoading={perfLoading && chartSeries.length === 0} />

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <KpiCard
                label="Valore portafoglio"
                value={hasPrices ? `€ ${totalValue.toLocaleString("it-IT", { minimumFractionDigits: 2 })}` : "—"}
                sub={hasPrices ? `Investito: € ${totalInvested.toLocaleString("it-IT", { minimumFractionDigits: 2 })}` : undefined}
              />
              <KpiCard
                label={`Performance ${periodLabel}`}
                value={periodPnl != null
                  ? `€ ${periodPnl.toLocaleString("it-IT", { minimumFractionDigits: 2, signDisplay: "always" })}`
                  : "—"}
                sub={periodPnlPct != null ? `${periodPnlPct >= 0 ? "+" : ""}${periodPnlPct.toFixed(2)}%` : undefined}
                positive={periodPnl != null ? periodPnl >= 0 : undefined}
              />
              <KpiCard
                label="Variazione oggi"
                value={hasPrices ? `€ ${dailyChange.toLocaleString("it-IT", { minimumFractionDigits: 2, signDisplay: "always" })}` : "—"}
                positive={hasPrices ? dailyChange >= 0 : undefined}
              />
            </div>

            {/* Per-account breakdown */}
            {accountBreakdown.length > 1 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-700">Per conto</h3>
                  <button onClick={() => navigate("/impostazioni")}
                    className="text-xs text-brand-600 hover:underline flex items-center gap-1">
                    Gestisci conti <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {accountBreakdown.map(({ acc, value, pnl, pnlPct }) => (
                    <button key={acc.id} onClick={() => navigate(`/transazioni?account=${acc.id}`)}
                      className="bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-brand-300 hover:shadow-sm transition-all group">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <p className="text-xs text-gray-400 truncate">{acc.broker ?? "—"}</p>
                          <p className="text-sm font-semibold text-gray-900 truncate">{acc.name}</p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-brand-500 flex-shrink-0 mt-0.5" />
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
                            {hasPrices ? `${pnl >= 0 ? "+" : ""}€ ${pnl.toLocaleString("it-IT", { maximumFractionDigits: 0 })} (${pnlPct.toFixed(1)}%)` : "—"}
                          </span>
                        </div>
                      </div>
                      {hasPrices && totalValue > 0 && (
                        <>
                          <div className="mt-3 h-1 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full bg-brand-400 rounded-full"
                              style={{ width: `${Math.min((value / totalValue) * 100, 100)}%` }} />
                          </div>
                          <p className="text-xs text-gray-300 mt-1 text-right">
                            {((value / totalValue) * 100).toFixed(1)}% del totale
                          </p>
                        </>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Holdings table */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-gray-900">Holdings</h3>
                  <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                </div>
                <div className="flex items-center gap-3">
                  {backfillDone && <span className="text-xs text-green-600">{backfillDone}</span>}
                  <button onClick={() => { setBackfillDone(null); runBackfill(); }} disabled={backfillPending}
                    className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-brand-600 disabled:opacity-50 transition-colors"
                    title="Scarica storico prezzi dalla data del primo acquisto">
                    <RefreshCw className={`w-3.5 h-3.5 ${backfillPending ? "animate-spin" : ""}`} />
                    Aggiorna storico
                  </button>
                  <div className="flex rounded-full border border-gray-200 overflow-hidden text-xs font-medium">
                    <button onClick={() => setShowClosed(false)}
                      className={`px-3 py-1 transition-colors ${!showClosed ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-50"}`}>
                      Attivi
                    </button>
                    <button onClick={() => setShowClosed(true)}
                      className={`px-3 py-1 transition-colors ${showClosed ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-50"}`}>
                      Chiusi
                    </button>
                  </div>
                </div>
              </div>

              {!showClosed && (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-50 bg-gray-50/50 text-left">
                      <SortTh field="name" current={sortField} dir={sortDir} onSort={handleSort} className="pl-5">Nome</SortTh>
                      <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Prima attività</th>
                      <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Quantità</th>
                      <SortTh field="value" current={sortField} dir={sortDir} onSort={handleSort} className="text-right">Valore</SortTh>
                      <SortTh field="allocation" current={sortField} dir={sortDir} onSort={handleSort} className="text-right">Allocaz.</SortTh>
                      <SortTh field="change" current={sortField} dir={sortDir} onSort={handleSort} className="text-right">Variazione</SortTh>
                      <SortTh field="performance" current={sortField} dir={sortDir} onSort={handleSort} className="pr-5 text-right">Performance</SortTh>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {positionsLoading
                      ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={7} />)
                      : sortedPositions.map((pos) => {
                          const alloc = totalValue > 0 && pos.current_value_eur != null
                            ? (pos.current_value_eur / totalValue) * 100 : null;
                          const dateStr = firstBuyDate[pos.asset_id];
                          return (
                            <tr
                              key={pos.asset_id}
                              className="hover:bg-gray-50/70 transition-colors cursor-pointer"
                              onDoubleClick={() => setSelectedAssetId(pos.asset_id)}
                              title="Doppio click per i dettagli"
                            >
                              <td className="pl-5 pr-4 py-3.5">
                                <div className="font-medium text-gray-900 truncate max-w-[220px]">{pos.name}</div>
                                <div className="text-xs text-gray-400 mt-0.5">{pos.symbol}</div>
                              </td>
                              <td className="px-4 py-3.5 text-right text-xs text-gray-400">
                                {dateStr ? new Date(dateStr).toLocaleDateString("it-IT") : "—"}
                              </td>
                              <td className="px-4 py-3.5 text-right text-gray-600 tabular-nums">
                                {pos.quantity.toLocaleString("it-IT", { maximumFractionDigits: 4 })}
                              </td>
                              <td className="px-4 py-3.5 text-right font-semibold text-gray-900 tabular-nums">
                                {pos.current_value_eur != null
                                  ? `€ ${pos.current_value_eur.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                  : <span className="text-gray-300 font-normal">N/D</span>}
                              </td>
                              <td className="px-4 py-3.5 text-right">
                                {alloc != null ? (
                                  <div className="flex items-center justify-end gap-2">
                                    <div className="w-14 h-1.5 bg-gray-100 rounded-full overflow-hidden hidden sm:block">
                                      <div className="h-full bg-brand-400 rounded-full" style={{ width: `${Math.min(alloc, 100)}%` }} />
                                    </div>
                                    <span className="text-xs text-gray-600 tabular-nums w-10 text-right">{alloc.toFixed(2)}%</span>
                                  </div>
                                ) : <span className="text-gray-300 text-xs">—</span>}
                              </td>
                              <td className="px-4 py-3.5 text-right tabular-nums">
                                {pos.periodPnlEur != null ? (
                                  <span className={`text-sm font-medium ${pos.periodPnlEur >= 0 ? "text-green-600" : "text-red-500"}`}>
                                    {pos.periodPnlEur >= 0 ? "+ " : "− "}
                                    {Math.abs(pos.periodPnlEur).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </span>
                                ) : <span className="text-gray-300 text-xs">—</span>}
                              </td>
                              <td className="pr-5 pl-4 py-3.5 text-right tabular-nums">
                                {pos.periodPnlPct != null ? (
                                  <span className={`text-sm font-semibold ${pos.periodPnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                                    {pos.periodPnlPct >= 0 ? "+" : ""}{pos.periodPnlPct.toFixed(2)} %
                                  </span>
                                ) : <span className="text-gray-300 text-xs">—</span>}
                              </td>
                            </tr>
                          );
                        })}
                  </tbody>
                </table>
              )}

              {showClosed && (
                closedRows.length === 0 ? (
                  <div className="p-10 text-center text-sm text-gray-400">Nessuna posizione chiusa.</div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-50 bg-gray-50/50 text-left">
                        <th className="pl-5 pr-4 py-3 text-xs font-medium text-gray-400 uppercase">Nome</th>
                        <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Prima attività</th>
                        <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Ultima attività</th>
                        <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Investito</th>
                        <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Incassato</th>
                        <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">P&L</th>
                        <th className="pr-5 pl-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">Performance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {closedRows.map(({ asset, firstDate, lastDate, totalBought, totalSold, pnl, pnlPct }) => (
                        <tr key={asset.id} className="hover:bg-gray-50/70 transition-colors">
                          <td className="pl-5 pr-4 py-3.5">
                            <div className="font-medium text-gray-900 truncate max-w-[220px]">{asset.name}</div>
                            <div className="text-xs text-gray-400 mt-0.5">{asset.symbol}</div>
                          </td>
                          <td className="px-4 py-3.5 text-right text-xs text-gray-400">
                            {firstDate ? new Date(firstDate).toLocaleDateString("it-IT") : "—"}
                          </td>
                          <td className="px-4 py-3.5 text-right text-xs text-gray-400">
                            {lastDate ? new Date(lastDate).toLocaleDateString("it-IT") : "—"}
                          </td>
                          <td className="px-4 py-3.5 text-right text-gray-700 tabular-nums">
                            € {totalBought.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3.5 text-right text-gray-700 tabular-nums">
                            € {totalSold.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3.5 text-right tabular-nums">
                            <span className={`font-medium text-sm ${pnl >= 0 ? "text-green-600" : "text-red-500"}`}>
                              {pnl >= 0 ? "+ " : "− "}€ {Math.abs(pnl).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </td>
                          <td className="pr-5 pl-4 py-3.5 text-right tabular-nums">
                            <span className={`font-semibold text-sm ${pnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)} %
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}
            </div>
          </>
        )}
      </main>

      {selectedAssetId != null && (
        <HoldingDetailModal
          assetId={selectedAssetId}
          onClose={() => setSelectedAssetId(null)}
        />
      )}
    </>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SortTh({ field, current, dir, onSort, children, className = "" }: {
  field: SortField; current: SortField; dir: SortDir;
  onSort: (f: SortField) => void; children: React.ReactNode; className?: string;
}) {
  const active = current === field;
  return (
    <th onClick={() => onSort(field)}
      className={`px-4 py-3 text-xs font-medium uppercase cursor-pointer select-none
        ${active ? "text-gray-700" : "text-gray-400 hover:text-gray-600"} ${className}`}>
      <span className="inline-flex items-center gap-1">
        {children}
        {active
          ? dir === "desc" ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />
          : null}
      </span>
    </th>
  );
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-4">
          <div className={`h-3.5 bg-gray-100 rounded ${i === 0 ? "w-36" : "w-16 ml-auto"}`} />
        </td>
      ))}
    </tr>
  );
}

function KpiCard({ label, value, sub, positive }: {
  label: string; value: string; sub?: string; positive?: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${
        positive === undefined ? "text-gray-900" : positive ? "text-green-600" : "text-red-600"
      }`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}
