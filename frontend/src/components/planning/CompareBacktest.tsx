import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, GitCompare, History, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { CHART_COLORS } from "@/components/charts/SmallDonutCard";
import { useZenMode } from "@/context/ThemeContext";
import { planningService, type SearchResult, type SecurityRef } from "@/services/planning";
import { getIntlLocale } from "@/utils/format";
import { SecuritySearch } from "./SecuritySearch";

const card = "bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5";
const input = "border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-1 text-sm bg-white dark:bg-slate-800";
const YEARS = [1, 3, 5, 10] as const;
const pct = (v: number | null | undefined) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

const toRef = (r: SearchResult): SecurityRef & { label: string } =>
  ({ asset_id: r.asset_id, symbol: r.asset_id ? null : r.symbol, name: r.name, type: r.type, label: r.name });

function Compare() {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<(SecurityRef & { label: string })[]>([]);
  const [years, setYears] = useState<number>(3);
  const run = useMutation({ mutationFn: () => planningService.compareSecurities(items.map(({ label: _l, ...r }) => r), years) });
  const r = run.data;
  const keys = r ? Object.keys(r.normalized) : [];
  const data = r ? r.dates.map((d, i) => Object.fromEntries([["date", d], ...keys.map((k) => [r.names[k], r.normalized[k][i]])])) : [];
  const err = (run.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  return (
    <div className={card}>
      <h3 className="text-sm font-semibold flex items-center gap-2"><GitCompare className="w-4 h-4 text-brand-500" />{t("planning.compare.title")}</h3>
      <p className="text-xs text-gray-400 mb-3">{t("planning.compare.desc")}</p>
      {items.length < 4 && <SecuritySearch onSelect={(s) => setItems((xs) => [...xs, toRef(s)])} />}
      <div className="flex flex-wrap gap-1.5 mt-3">
        {items.map((it, i) => (
          <span key={i} className="inline-flex items-center gap-1 rounded-full border border-gray-200 px-2.5 py-1 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_COLORS[i] }} />{it.label}
            <button onClick={() => setItems((xs) => xs.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500"><Trash2 className="w-3 h-3" /></button>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-3">
        {YEARS.map((y) => (
          <button key={y} onClick={() => setYears(y)} className={`px-2.5 py-1 rounded text-xs ${years === y ? "bg-brand-600 text-white" : "text-gray-500 hover:bg-gray-100"}`}>
            {y}{t("planning.goals.yearShort").toUpperCase()}
          </button>
        ))}
        <Button size="sm" className="ml-auto" onClick={() => run.mutate()} loading={run.isPending} disabled={items.length < 2}>{t("planning.compare.run")}</Button>
      </div>
      {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
      {r && (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-gray-400">{t("planning.compare.window", { start: r.start, end: r.end })}</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(0, 7)} fontSize={11} minTickGap={40} />
                <YAxis domain={["auto", "auto"]} fontSize={11} width={40} />
                <Tooltip labelFormatter={(d: string) => new Date(d).toLocaleDateString(i18n.language)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {keys.map((k, i) => <Line key={k} dataKey={r.names[k]} stroke={CHART_COLORS[i]} dot={false} strokeWidth={1.5} />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 text-left">
              <th className="py-1 font-medium" /><th className="py-1 font-medium text-right">{t("planning.compare.periodReturn")}</th>
              <th className="py-1 font-medium text-right">{t("planning.compare.annual")}</th><th className="py-1 font-medium text-right">{t("planning.card.volatility")}</th>
              <th className="py-1 font-medium text-right">{t("planning.card.maxDrawdown")}</th>
            </tr></thead>
            <tbody>{keys.map((k) => (
              <tr key={k} className="border-t border-gray-50 dark:border-slate-800">
                <td className="py-1 truncate max-w-[200px]">{r.names[k]}</td>
                <td className="py-1 text-right tabular-nums">{pct(r.metrics[k].window_return_pct)}</td>
                <td className="py-1 text-right tabular-nums">{pct(r.metrics[k].window_ann_return_pct)}</td>
                <td className="py-1 text-right tabular-nums">{r.metrics[k].volatility_1y_pct?.toFixed(1) ?? "—"}%</td>
                <td className="py-1 text-right tabular-nums">{pct(r.metrics[k].max_drawdown_1y_pct)}</td>
              </tr>
            ))}</tbody>
          </table>
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">{t("planning.compare.correlation")}</p>
            <table className="text-xs">
              <tbody>{keys.map((a) => (
                <tr key={a}><td className="pr-3 py-0.5 truncate max-w-[160px]">{r.names[a]}</td>
                  {keys.map((b) => {
                    const v = r.correlation[a][b];
                    return <td key={b} className="px-2 py-0.5 text-center tabular-nums rounded"
                      style={{ backgroundColor: `rgba(59,130,246,${Math.max(v, 0) * 0.35})` }}>{v.toFixed(2)}</td>;
                  })}</tr>
              ))}</tbody>
            </table>
          </div>
          {r.overlaps.map((o) => (
            <p key={`${o.a}-${o.b}`} className="text-xs text-gray-600">
              {t("planning.compare.overlap", { a: o.a, b: o.b, pct: o.overlap_pct.toFixed(1) })}
              {o.common.length > 0 && ` (${o.common.slice(0, 5).map((c) => c.name).join(", ")})`}
            </p>
          ))}
          {r.overlaps.length > 0 && <p className="text-[11px] text-gray-400">{r.notes.join(" ")}</p>}
        </div>
      )}
    </div>
  );
}

function Backtest() {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const [items, setItems] = useState<(SecurityRef & { label: string; weight: number })[]>([]);
  const [bench, setBench] = useState<(SecurityRef & { label: string }) | null>(null);
  const [pickBench, setPickBench] = useState(false);
  const [years, setYears] = useState<number>(5);
  const [initial, setInitial] = useState(10000);
  const [monthly, setMonthly] = useState(0);
  const [rebalance, setRebalance] = useState<"none" | "annual" | "threshold">("annual");
  const eur = (v?: number) => (v == null ? "—" : zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }));
  const total = items.reduce((s, x) => s + x.weight, 0);
  const run = useMutation({
    mutationFn: () => planningService.backtest({
      components: items.map(({ label: _l, ...r }) => r), years, initial_amount: initial, monthly_contribution: monthly, rebalance,
      benchmark: bench ? (({ label: _l, ...r }) => r)(bench) : null,
    }),
  });
  const r = run.data;
  const err = (run.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;
  const chart = r ? r.model.series.map((p, i) => ({ date: p.date, model: p.value, invested: p.invested, bench: r.benchmark?.series[i]?.value })) : [];

  return (
    <div className={card}>
      <h3 className="text-sm font-semibold flex items-center gap-2"><History className="w-4 h-4 text-brand-500" />{t("planning.backtest.title")}</h3>
      <p className="text-xs text-gray-400 mb-3">{t("planning.backtest.desc")}</p>
      {items.length < 10 && <SecuritySearch onSelect={(s) => setItems((xs) => [...xs, { ...toRef(s), weight: xs.length ? 0 : 100 }])} />}
      <div className="space-y-1.5 mt-3">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <span className="flex-1 truncate">{it.label}</span>
            <input type="number" min={0} max={100} value={it.weight} className={`${input} w-20`}
              onChange={(e) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)))} /> %
            <button onClick={() => setItems((xs) => xs.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        {items.length > 0 && <p className={`text-xs ${Math.abs(total - 100) > 0.5 ? "text-red-600" : "text-green-600"}`}>{t("planning.contrib.total", { total })}</p>}
      </div>
      <div className="flex flex-wrap items-end gap-3 mt-3 text-xs text-gray-500">
        <label className="flex flex-col gap-0.5">{t("planning.goals.initial")}<input type="number" min={0} value={initial} onChange={(e) => setInitial(Number(e.target.value))} className={`${input} w-28`} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.monthly")}<input type="number" min={0} value={monthly} onChange={(e) => setMonthly(Number(e.target.value))} className={`${input} w-24`} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.backtest.rebalance")}
          <select value={rebalance} onChange={(e) => setRebalance(e.target.value as typeof rebalance)} className={input}>
            {(["none", "annual", "threshold"] as const).map((x) => <option key={x} value={x}>{t(`planning.backtest.rebalanceModes.${x}`)}</option>)}
          </select></label>
        <div className="flex gap-1">{YEARS.map((y) => (
          <button key={y} onClick={() => setYears(y)} className={`px-2.5 py-1 rounded ${years === y ? "bg-brand-600 text-white" : "hover:bg-gray-100"}`}>{y}{t("planning.goals.yearShort").toUpperCase()}</button>
        ))}</div>
      </div>
      <div className="mt-3 text-xs">
        {bench ? (
          <span className="inline-flex items-center gap-1">{t("planning.backtest.benchmark")}: <strong>{bench.label}</strong>
            <button onClick={() => setBench(null)} className="text-gray-300 hover:text-red-500"><Trash2 className="w-3 h-3" /></button></span>
        ) : pickBench ? (
          <SecuritySearch autoFocus onSelect={(s) => { setBench(toRef(s)); setPickBench(false); }} />
        ) : (
          <button className="text-brand-600 hover:underline" onClick={() => setPickBench(true)}>+ {t("planning.backtest.addBenchmark")}</button>
        )}
      </div>
      <Button size="sm" className="mt-3" onClick={() => run.mutate()} loading={run.isPending} disabled={!items.length || Math.abs(total - 100) > 0.5}>
        {t("planning.backtest.run")}
      </Button>
      {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
      {r && (
        <div className="mt-4 space-y-3">
          {r.model.warnings.map((w) => <p key={w} className="text-xs text-amber-700 flex gap-1"><AlertTriangle className="w-3.5 h-3.5" />{w}</p>)}
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(0, 7)} fontSize={11} minTickGap={40} />
                <YAxis fontSize={11} width={55} tickFormatter={(v: number) => (zen ? "•••" : v.toLocaleString(getIntlLocale(i18n.language), { notation: "compact" }))} />
                <Tooltip formatter={(v: number) => eur(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line dataKey="model" name={t("planning.backtest.model")} stroke={CHART_COLORS[0]} dot={false} strokeWidth={2} />
                {r.benchmark && <Line dataKey="bench" name={r.benchmark.name} stroke={CHART_COLORS[1]} dot={false} />}
                <Line dataKey="invested" name={t("planning.goals.contributed")} stroke="#9ca3af" strokeDasharray="4 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 text-left"><th />
              <th className="py-1 font-medium text-right">{t("planning.backtest.final")}</th><th className="py-1 font-medium text-right">TWRR</th>
              <th className="py-1 font-medium text-right">{t("planning.compare.annual")}</th><th className="py-1 font-medium text-right">{t("planning.backtest.vol")}</th>
              <th className="py-1 font-medium text-right">Max DD</th></tr></thead>
            <tbody>{[{ name: t("planning.backtest.model"), m: r.model.metrics }, ...(r.benchmark ? [{ name: r.benchmark.name, m: r.benchmark.metrics }] : [])].map(({ name, m }) => (
              <tr key={name} className="border-t border-gray-50 dark:border-slate-800">
                <td className="py-1">{name}</td><td className="py-1 text-right tabular-nums">{eur(m.final_value)}</td>
                <td className="py-1 text-right tabular-nums">{pct(m.twrr_pct)}</td><td className="py-1 text-right tabular-nums">{pct(m.twrr_ann_pct)}</td>
                <td className="py-1 text-right tabular-nums">{m.volatility_pct?.toFixed(1) ?? "—"}%</td><td className="py-1 text-right tabular-nums">{pct(m.max_drawdown_pct)}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="text-xs text-gray-400">{t("planning.backtest.note", { start: r.model.metrics.start, rebalances: r.model.metrics.rebalances ?? 0 })}</p>
        </div>
      )}
    </div>
  );
}

export function CompareBacktest() {
  return (
    <div className="space-y-4">
      <Compare />
      <Backtest />
    </div>
  );
}
