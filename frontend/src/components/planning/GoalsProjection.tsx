import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Flame, Plus, Save, Target, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { useZenMode } from "@/context/ThemeContext";
import { ASSET_CLASS_KEYS, planningService, type AssetClassKey, type Assumptions, type Goal, type Projection } from "@/services/planning";
import { getIntlLocale } from "@/utils/format";
import { PacCalculator } from "./PacCalculator";

const DEFAULTS: Record<AssetClassKey, [number, number]> = {
  EQUITY: [7, 16], BOND: [3, 6], MONEY_MARKET: [2, 0.5], CRYPTO: [15, 60], OTHER: [4, 15],
};
const input = "border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-1 text-sm bg-white dark:bg-slate-800";
const inTenYears = () => { const d = new Date(); d.setFullYear(d.getFullYear() + 10); return d.toISOString().slice(0, 10); };

function AssumptionsEditor({ value, onChange }: { value: Assumptions; onChange: (a: Assumptions) => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const set = (kind: "returns_pct" | "volatility_pct", k: AssetClassKey, v: number) =>
    onChange({ ...value, [kind]: { ...(value[kind] ?? {}), [k]: v } });
  return (
    <div className="text-xs">
      <button className="text-brand-600 hover:underline" onClick={() => setOpen((o) => !o)}>
        {open ? t("planning.goals.hideAssumptions") : t("planning.goals.editAssumptions")}
      </button>
      {open && (
        <table className="mt-2 text-xs">
          <thead><tr className="text-gray-400"><th /><th className="px-2 font-medium">{t("planning.goals.returnPct")}</th><th className="px-2 font-medium">{t("planning.goals.volPct")}</th></tr></thead>
          <tbody>
            {ASSET_CLASS_KEYS.map((k) => (
              <tr key={k}>
                <td className="pr-2 py-0.5">{t(`planning.classes.${k}`)}</td>
                <td className="px-2"><input type="number" step={0.5} className={`${input} w-16`}
                  value={value.returns_pct?.[k] ?? DEFAULTS[k][0]} onChange={(e) => set("returns_pct", k, Number(e.target.value))} /></td>
                <td className="px-2"><input type="number" step={0.5} className={`${input} w-16`}
                  value={value.volatility_pct?.[k] ?? DEFAULTS[k][1]} onChange={(e) => set("volatility_pct", k, Number(e.target.value))} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-gray-400 mt-1">{t("planning.goals.assumptionsNote")}</p>
    </div>
  );
}

function ProjectionChart({ p, target }: { p: Projection; target: number }) {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const fmt = (v: number) => (zen ? "•••" : v.toLocaleString(getIntlLocale(i18n.language), { notation: "compact", maximumFractionDigits: 1 }));
  const data = p.yearly.map((y) => ({ ...y, band: [y.p10, y.p90], mid: [y.p25, y.p75] }));
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data}>
          <XAxis dataKey="year" tickFormatter={(y) => `${y}${t("planning.goals.yearShort")}`} fontSize={11} />
          <YAxis tickFormatter={fmt} fontSize={11} width={50} />
          <Tooltip
            formatter={(v: number | number[], name: string) => [Array.isArray(v) ? v.map(fmt).join(" – ") : fmt(v), t(`planning.goals.series.${name}`)]}
            labelFormatter={(y) => `${t("planning.goals.year")} ${y}`} contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Area dataKey="band" stroke="none" fill="#3b82f6" fillOpacity={0.12} />
          <Area dataKey="mid" stroke="none" fill="#3b82f6" fillOpacity={0.22} />
          <Line dataKey="p50" stroke="#2563eb" strokeWidth={2} dot={false} />
          <Line dataKey="contributed" stroke="#9ca3af" strokeDasharray="4 3" dot={false} />
          <ReferenceLine y={target} stroke="#16a34a" strokeDasharray="6 3" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function GoalCard() {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const qc = useQueryClient();
  const { data: goals = [] } = useQuery({ queryKey: ["planning-goals"], queryFn: planningService.goals });
  const empty: Goal = { name: "", target_amount: 100000, target_date: inTenYears(), monthly_contribution: 300, initial_amount: null, inflation_pct: 2 };
  const [goal, setGoal] = useState<Goal>(empty);
  const [assumptions, setAssumptions] = useState<Assumptions>({});
  const [result, setResult] = useState<Projection | null>(null);
  const eur = (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }));

  const run = useMutation({
    mutationFn: () => planningService.projection({ ...assumptions, target_amount: goal.target_amount, target_date: goal.target_date,
      monthly_contribution: goal.monthly_contribution, initial_amount: goal.initial_amount, inflation_pct: goal.inflation_pct }),
    onSuccess: setResult,
  });
  const save = useMutation({
    mutationFn: () => planningService.saveGoal({ ...goal, name: goal.name.trim() || t("planning.goals.untitled") }),
    onSuccess: (g) => { setGoal(g); qc.invalidateQueries({ queryKey: ["planning-goals"] }); },
  });
  const del = useMutation({
    mutationFn: (id: number) => planningService.deleteGoal(id),
    onSuccess: () => { setGoal(empty); setResult(null); qc.invalidateQueries({ queryKey: ["planning-goals"] }); },
  });
  useEffect(() => { if (goal.id) run.mutate(); }, [goal.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = <K extends keyof Goal>(k: K, v: Goal[K]) => setGoal((g) => ({ ...g, [k]: v }));
  const err = (run.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5 space-y-4">
      <div className="flex items-start gap-3">
        <Target className="w-5 h-5 text-brand-500 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold">{t("planning.goals.title")}</h3>
          <p className="text-xs text-gray-400">{t("planning.goals.desc")}</p>
        </div>
      </div>
      {goals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {goals.map((g) => (
            <button key={g.id} onClick={() => setGoal(g)}
              className={`px-2.5 py-1 rounded-full text-xs border ${goal.id === g.id ? "bg-brand-600 border-brand-600 text-white" : "border-gray-200 text-gray-600"}`}>
              {g.name}
            </button>
          ))}
          <button onClick={() => { setGoal(empty); setResult(null); }} className="px-2.5 py-1 rounded-full text-xs border border-dashed border-gray-300 text-gray-500">
            <Plus className="w-3 h-3 inline" /> {t("planning.goals.new")}
          </button>
        </div>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs text-gray-500">
        <label className="flex flex-col gap-0.5">{t("planning.goals.name")}
          <input value={goal.name} onChange={(e) => set("name", e.target.value)} className={input} placeholder={t("planning.goals.namePlaceholder")} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.targetAmount")}
          <input type="number" min={1} value={goal.target_amount} onChange={(e) => set("target_amount", Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.targetDate")}
          <input type="date" value={goal.target_date} onChange={(e) => set("target_date", e.target.value)} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.monthly")}
          <input type="number" min={0} value={goal.monthly_contribution} onChange={(e) => set("monthly_contribution", Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.initial")}
          <input type="number" min={0} value={goal.initial_amount ?? ""} placeholder={t("planning.goals.currentNetWorth")}
            onChange={(e) => set("initial_amount", e.target.value === "" ? null : Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.inflation")}
          <input type="number" step={0.5} value={goal.inflation_pct} onChange={(e) => set("inflation_pct", Number(e.target.value))} className={input} /></label>
      </div>
      <AssumptionsEditor value={assumptions} onChange={setAssumptions} />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => run.mutate()} loading={run.isPending}>{t("planning.goals.project")}</Button>
        <Button size="sm" variant="secondary" onClick={() => save.mutate()} loading={save.isPending}>
          <Save className="w-4 h-4 mr-1" /> {goal.id ? t("planning.goals.update") : t("planning.goals.save")}
        </Button>
        {goal.id && (
          <button onClick={() => del.mutate(goal.id!)} className="p-1.5 text-gray-300 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
        )}
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <div className={`rounded-lg px-3 py-2 ${result.probability >= 0.8 ? "bg-green-50" : result.probability >= 0.5 ? "bg-amber-50" : "bg-red-50"}`}>
              <p className="text-[11px] text-gray-500">{t("planning.goals.probability")}</p>
              <p className="text-xl font-bold">{(result.probability * 100).toFixed(0)}%</p>
            </div>
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2">
              <p className="text-[11px] text-gray-500">{t("planning.goals.median")}</p>
              <p className="text-sm font-semibold">{eur(result.median_final)}</p>
              <p className="text-[11px] text-gray-400">{eur(result.p10_final)} – {eur(result.p90_final)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2">
              <p className="text-[11px] text-gray-500">{t("planning.goals.contributed")}</p>
              <p className="text-sm font-semibold">{eur(result.total_contributed)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2">
              <p className="text-[11px] text-gray-500">{t("planning.goals.required80")}</p>
              <p className="text-sm font-semibold">{result.required_monthly_80 == null ? "—" : `${eur(result.required_monthly_80)}/${t("planning.goals.monthShort")}`}</p>
            </div>
          </div>
          <ProjectionChart p={result} target={goal.target_amount} />
          <p className="text-xs text-gray-400">
            {t("planning.goals.chartNote", { ret: result.expected_return_pct, vol: result.volatility_pct })}
          </p>
        </div>
      )}
    </div>
  );
}

function FireCard() {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const [expenses, setExpenses] = useState(24000);
  const [rate, setRate] = useState(3.5);
  const [monthly, setMonthly] = useState(500);
  const [horizon, setHorizon] = useState(40);
  const [inflation, setInflation] = useState(2);
  const eur = (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }));
  const run = useMutation({
    mutationFn: () => planningService.fire({ annual_expenses: expenses, withdrawal_rate_pct: rate, monthly_contribution: monthly,
      inflation_pct: inflation, horizon_years: horizon }),
  });
  const r = run.data;
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5 space-y-3">
      <div className="flex items-start gap-3">
        <Flame className="w-5 h-5 text-orange-500 mt-0.5" />
        <div><h3 className="text-sm font-semibold">{t("planning.fire.title")}</h3><p className="text-xs text-gray-400">{t("planning.fire.desc")}</p></div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-xs text-gray-500">
        <label className="flex flex-col gap-0.5">{t("planning.fire.expenses")}<input type="number" value={expenses} onChange={(e) => setExpenses(Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.fire.rate")}<input type="number" step={0.25} value={rate} onChange={(e) => setRate(Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.monthly")}<input type="number" value={monthly} onChange={(e) => setMonthly(Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.fire.horizon")}<input type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className={input} /></label>
        <label className="flex flex-col gap-0.5">{t("planning.goals.inflation")}<input type="number" step={0.5} value={inflation} onChange={(e) => setInflation(Number(e.target.value))} className={input} /></label>
      </div>
      <Button size="sm" onClick={() => run.mutate()} loading={run.isPending} disabled={expenses <= 0 || rate <= 0}>{t("planning.fire.calculate")}</Button>
      {r && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2"><p className="text-[11px] text-gray-500">{t("planning.fire.target")}</p><p className="text-sm font-semibold">{eur(r.target_capital)}</p></div>
          <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2"><p className="text-[11px] text-gray-500">{t("planning.fire.years")}</p>
            <p className="text-sm font-semibold">{r.years_to_fire_median == null ? t("planning.fire.over50") : `${r.years_to_fire_median} ${t("planning.goals.yearsLong")}`}</p>
            <p className="text-[11px] text-gray-400">{t("planning.fire.pessimistic")}: {r.years_to_fire_p10 == null ? t("planning.fire.over50") : r.years_to_fire_p10}</p></div>
          <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2"><p className="text-[11px] text-gray-500">{t("planning.fire.success", { years: horizon })}</p><p className="text-sm font-semibold">{(r.success_probability * 100).toFixed(0)}%</p></div>
          <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2"><p className="text-[11px] text-gray-500">{t("planning.fire.sustainable")}</p><p className="text-sm font-semibold">{eur(r.sustainable_withdrawal_90)}/{t("planning.goals.yearShortLong")}</p></div>
        </div>
      )}
      <p className="text-xs text-gray-400">{t("planning.fire.note")}</p>
    </div>
  );
}

export function GoalsProjection() {
  return (
    <div className="space-y-4">
      <GoalCard />
      <FireCard />
      <PacCalculator />
    </div>
  );
}
