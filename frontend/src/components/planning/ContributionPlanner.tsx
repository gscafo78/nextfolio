import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Calculator, Save, ShoppingCart, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { useZenMode } from "@/context/ThemeContext";
import {
  ASSET_CLASS_KEYS, planningService,
  type AssetClassKey, type ContributionPlan, type PlanItem, type Targets,
} from "@/services/planning";
import { getIntlLocale } from "@/utils/format";
import { SecuritySearch } from "./SecuritySearch";

const DEFAULT_TARGETS: Targets = { weights: { EQUITY: 70, BOND: 25, MONEY_MARKET: 5 }, tolerance_pct: 5, preferred: {} };
const input = "border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-1 text-sm bg-white dark:bg-slate-800";

function TargetsEditor({ initial, onSaved }: { initial: Targets; onSaved: () => void }) {
  const { t } = useTranslation();
  const [targets, setTargets] = useState<Targets>(initial);
  const [adding, setAdding] = useState<AssetClassKey | null>(null);
  useEffect(() => setTargets(initial), [initial]);

  const total = ASSET_CLASS_KEYS.reduce((s, k) => s + (targets.weights[k] ?? 0), 0);
  const save = useMutation({ mutationFn: () => planningService.saveTargets(targets), onSuccess: onSaved });
  const setW = (k: AssetClassKey, v: number) => setTargets((x) => ({ ...x, weights: { ...x.weights, [k]: v } }));
  const prefs = (k: AssetClassKey) => targets.preferred[k] ?? [];
  const setPrefs = (k: AssetClassKey, list: Targets["preferred"][AssetClassKey]) =>
    setTargets((x) => ({ ...x, preferred: { ...x.preferred, [k]: list } }));

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold">{t("planning.contrib.targetsTitle")}</h3>
        <p className="text-xs text-gray-400">{t("planning.contrib.targetsDesc")}</p>
      </div>
      <div className="space-y-3">
        {ASSET_CLASS_KEYS.map((k) => (
          <div key={k} className="border-t border-gray-50 dark:border-slate-800 pt-2 first:border-0 first:pt-0">
            <div className="flex items-center gap-3">
              <span className="w-32 text-sm">{t(`planning.classes.${k}`)}</span>
              <input type="range" min={0} max={100} step={1} value={targets.weights[k] ?? 0}
                onChange={(e) => setW(k, Number(e.target.value))} className="flex-1 accent-brand-600" />
              <input type="number" min={0} max={100} value={targets.weights[k] ?? 0}
                onChange={(e) => setW(k, Math.max(0, Math.min(100, Number(e.target.value))))} className={`${input} w-16`} />
              <span className="text-xs text-gray-400">%</span>
            </div>
            {(targets.weights[k] ?? 0) > 0 && k !== "MONEY_MARKET" && (
              <div className="ml-32 pl-3 mt-1 space-y-1">
                {prefs(k).map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="flex-1 truncate text-gray-600">{p.name}</span>
                    <input type="number" min={1} value={p.weight} title={t("planning.contrib.instrumentWeight")}
                      onChange={(e) => setPrefs(k, prefs(k).map((x, j) => (j === i ? { ...x, weight: Math.max(1, Number(e.target.value)) } : x)))}
                      className={`${input} w-14 text-xs`} />
                    <button onClick={() => setPrefs(k, prefs(k).filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {adding === k ? (
                  <SecuritySearch autoFocus onSelect={(r) => {
                    setPrefs(k, [...prefs(k), { asset_id: r.asset_id, symbol: r.asset_id ? null : r.symbol, name: r.name, type: r.type, weight: 1 }]);
                    setAdding(null);
                  }} />
                ) : (
                  <button className="text-xs text-brand-600 hover:underline" onClick={() => setAdding(k)}>
                    + {prefs(k).length ? t("planning.contrib.addInstrument") : t("planning.contrib.chooseInstrument")}
                  </button>
                )}
                {!prefs(k).length && <p className="text-[11px] text-gray-400">{t("planning.contrib.defaultInstruments")}</p>}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-100 dark:border-slate-800">
        <span className={`text-sm font-medium ${Math.abs(total - 100) > 0.5 ? "text-red-600" : "text-green-600"}`}>
          {t("planning.contrib.total", { total })}
        </span>
        <label className="text-xs text-gray-500 flex items-center gap-1">{t("planning.contrib.tolerance")}
          <input type="number" min={0} max={50} value={targets.tolerance_pct}
            onChange={(e) => setTargets((x) => ({ ...x, tolerance_pct: Number(e.target.value) }))} className={`${input} w-14`} /> %
        </label>
        <Button size="sm" className="ml-auto" onClick={() => save.mutate()} loading={save.isPending} disabled={Math.abs(total - 100) > 0.5}>
          <Save className="w-4 h-4 mr-1" /> {t("planning.contrib.saveTargets")}
        </Button>
      </div>
    </div>
  );
}

function DriftBars() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["planning-drift"], queryFn: planningService.drift });
  if (!data?.configured) return null;
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
      <h3 className="text-sm font-semibold mb-3">{t("planning.contrib.driftTitle", { tol: data.tolerance_pct })}</h3>
      <div className="space-y-2">
        {data.classes.map((r) => (
          <div key={r.class}>
            <div className="flex justify-between text-xs mb-0.5">
              <span>{r.label}</span>
              <span className={r.out_of_band ? "text-amber-600 font-semibold" : "text-gray-500"}>
                {r.current_pct.toFixed(1)}% / {r.target_pct.toFixed(0)}% ({r.delta_pct > 0 ? "+" : ""}{r.delta_pct.toFixed(1)})
              </span>
            </div>
            <div className="relative h-2 bg-gray-100 dark:bg-slate-800 rounded-full">
              <div className={`absolute h-2 rounded-full ${r.out_of_band ? "bg-amber-400" : "bg-brand-500"}`} style={{ width: `${Math.min(r.current_pct, 100)}%` }} />
              <div className="absolute -top-0.5 h-3 w-0.5 bg-gray-700" style={{ left: `${Math.min(r.target_pct, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Allocazione obiettivo, scostamento e versamento "solo acquisti". */
export function ContributionPlanner({ onSimulate }: { onSimulate: (items: PlanItem[], useCash: boolean) => void }) {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const qc = useQueryClient();
  const { data: targets, isLoading } = useQuery({ queryKey: ["planning-targets"], queryFn: planningService.targets });
  const [amount, setAmount] = useState("");
  const [fromCash, setFromCash] = useState(false);
  const [wholeUnits, setWholeUnits] = useState(true);
  const [minOrder, setMinOrder] = useState("0");
  const [fee, setFee] = useState("0");
  const [plan, setPlan] = useState<ContributionPlan | null>(null);
  const eur = (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR" }));

  const calc = useMutation({
    mutationFn: () => planningService.contribution({
      amount_eur: amount.trim() ? Number(amount.replace(",", ".")) : null, from_cash: fromCash, whole_units: wholeUnits,
      min_order_eur: Number(minOrder) || 0, fee_per_order_eur: Number(fee.replace(",", ".")) || 0,
    }),
    onSuccess: setPlan,
  });
  const err = (calc.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;
  const toItems = (p: ContributionPlan): PlanItem[] => p.orders.map((o) => ({
    asset_id: o.asset_id, symbol: o.symbol, name: o.name, type: o.type, amount_eur: null, quantity: o.quantity,
    price_eur: o.price_eur, fee_eur: o.fee_eur, account_id: null,
  }));

  if (isLoading) return <div className="h-40 bg-gray-50 rounded-xl animate-pulse" />;

  return (
    <div className="space-y-4">
      <TargetsEditor initial={targets ?? DEFAULT_TARGETS} onSaved={() => {
        qc.invalidateQueries({ queryKey: ["planning-targets"] });
        qc.invalidateQueries({ queryKey: ["planning-drift"] });
      }} />
      <DriftBars />

      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <h3 className="text-sm font-semibold">{t("planning.contrib.title")}</h3>
        <p className="text-xs text-gray-400 mb-3">{t("planning.contrib.desc")}</p>
        {!targets ? (
          <p className="text-sm text-gray-400">{t("planning.contrib.saveTargetsFirst")}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <label className="text-xs text-gray-500 flex flex-col gap-0.5">{t("planning.contrib.amount")}
                <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal"
                  placeholder={fromCash ? t("planning.contrib.allCash") : "500"} className={`${input} w-32`} />
              </label>
              <label className="text-xs text-gray-500 flex flex-col gap-0.5">{t("planning.contrib.minOrder")}
                <input value={minOrder} onChange={(e) => setMinOrder(e.target.value)} inputMode="decimal" className={`${input} w-24`} />
              </label>
              <label className="text-xs text-gray-500 flex flex-col gap-0.5">{t("planning.contrib.feePerOrder")}
                <input value={fee} onChange={(e) => setFee(e.target.value)} inputMode="decimal" className={`${input} w-24`} />
              </label>
              <label className="text-xs text-gray-600 flex items-center gap-1.5 pb-1.5">
                <input type="checkbox" checked={fromCash} onChange={(e) => setFromCash(e.target.checked)} className="rounded border-gray-300" />
                {t("planning.contrib.fromCash")}
              </label>
              <label className="text-xs text-gray-600 flex items-center gap-1.5 pb-1.5">
                <input type="checkbox" checked={wholeUnits} onChange={(e) => setWholeUnits(e.target.checked)} className="rounded border-gray-300" />
                {t("planning.contrib.wholeUnits")}
              </label>
              <Button size="sm" onClick={() => calc.mutate()} loading={calc.isPending} disabled={!fromCash && !amount.trim()}>
                <Calculator className="w-4 h-4 mr-1" /> {t("planning.contrib.calculate")}
              </Button>
            </div>
            {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
          </>
        )}

        {plan && (
          <div className="mt-4 space-y-3">
            {plan.warnings.length > 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 space-y-0.5">
                {plan.warnings.map((w) => <p key={w} className="flex gap-1.5"><AlertTriangle className="w-3.5 h-3.5 mt-0.5" />{w}</p>)}
              </div>
            )}
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-gray-400 text-left">
                <th className="py-1 font-medium">{t("common.asset")}</th>
                <th className="py-1 font-medium">{t("planning.contrib.class")}</th>
                <th className="py-1 font-medium text-right">{t("common.quantity")}</th>
                <th className="py-1 font-medium text-right">{t("planning.exec.priceEur")}</th>
                <th className="py-1 font-medium text-right">{t("planning.contrib.orderAmount")}</th>
              </tr></thead>
              <tbody>
                {plan.orders.map((o) => (
                  <tr key={o.name} className="border-t border-gray-50 dark:border-slate-800">
                    <td className="py-1">{o.name}</td><td className="py-1 text-xs text-gray-500">{o.asset_class}</td>
                    <td className="py-1 text-right tabular-nums">{o.quantity}</td>
                    <td className="py-1 text-right tabular-nums">{o.price_eur.toFixed(2)}</td>
                    <td className="py-1 text-right tabular-nums">{eur(o.amount_eur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-500">{t("planning.contrib.uninvested", { amount: eur(plan.uninvested_eur) })}</p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {plan.per_class.map((c) => (
                <div key={c.class} className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2 text-xs">
                  <p className="text-gray-500">{c.label}</p>
                  <p className="font-semibold tabular-nums">{c.before_pct.toFixed(1)}% → {c.after_pct.toFixed(1)}%</p>
                  <p className="text-gray-400">{t("planning.contrib.target")} {c.target_pct.toFixed(0)}%</p>
                </div>
              ))}
            </div>
            {plan.orders.length > 0 && (
              <div className="flex gap-2">
                <Button size="sm" onClick={() => onSimulate(toItems(plan), plan.from_cash)}>
                  <ShoppingCart className="w-4 h-4 mr-1" /> {t("planning.contrib.openInSimulator")}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
