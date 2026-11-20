import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Check, Play, Save, Trash2, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { SmallDonutCard } from "@/components/charts/SmallDonutCard";
import { useZenMode } from "@/context/ThemeContext";
import { accountService } from "@/services/transactions";
import { planningService, type PlanItem, type Scenario, type SearchResult, type SimulationResult } from "@/services/planning";
import { getIntlLocale } from "@/utils/format";
import { SecuritySearch } from "./SecuritySearch";
import { SecurityCard } from "./SecurityCard";

const STATUS_COLOR: Record<string, string> = {
  ok: "text-green-600", warn: "text-amber-600", error: "text-red-600", info: "text-gray-400",
};

function Kpi({ label, before, after, money = true }: { label: string; before: number; after: number; money?: boolean }) {
  const zen = useZenMode();
  const { i18n } = useTranslation();
  const f = (v: number) => (money
    ? (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }))
    : String(v));
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 px-4 py-3">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-semibold tabular-nums flex items-center gap-1.5 mt-0.5">
        <span className="text-gray-500">{f(before)}</span>
        <ArrowRight className="w-3.5 h-3.5 text-gray-300" />
        <span className="text-gray-900 dark:text-slate-100">{f(after)}</span>
      </p>
    </div>
  );
}

function Results({ sim }: { sim: SimulationResult }) {
  const { t } = useTranslation();
  const changed = sim.rule_changes.filter((r) => r.changed);
  return (
    <div className="space-y-4">
      {sim.warnings.length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 space-y-0.5">
          {sim.warnings.map((w) => <p key={w} className="flex gap-1.5"><AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />{w}</p>)}
        </div>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi label={t("planning.sim.netWorth")} before={sim.total_before_eur} after={sim.total_after_eur} />
        <Kpi label={t("planning.sim.cash")} before={sim.cash_before_eur} after={sim.cash_after_eur} />
        <Kpi label={t("planning.sim.invested")} before={0} after={sim.invested_eur + sim.fees_eur} />
        <Kpi label={t("planning.sim.xrayScore")} before={sim.xray_before.score} after={sim.xray_after.score} money={false} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SmallDonutCard title={`${t("allocation.byAssetClass")} — ${t("planning.sim.before")}`} items={sim.allocation_before.by_asset_class} />
        <SmallDonutCard title={`${t("allocation.byAssetClass")} — ${t("planning.sim.after")}`} items={sim.allocation_after.by_asset_class} />
        <SmallDonutCard title={`${t("allocation.byCurrencyExposure")} — ${t("planning.sim.before")}`} items={sim.allocation_before.by_currency_exposure} />
        <SmallDonutCard title={`${t("allocation.byCurrencyExposure")} — ${t("planning.sim.after")}`} items={sim.allocation_after.by_currency_exposure} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">{t("planning.sim.weights")}</h4>
          <table className="w-full text-xs">
            <thead><tr className="text-gray-400 text-left">
              <th className="py-1 font-medium">{t("common.asset")}</th>
              <th className="py-1 font-medium text-right">{t("planning.sim.before")}</th>
              <th className="py-1 font-medium text-right">{t("planning.sim.after")}</th>
              <th className="py-1 font-medium text-right">Δ</th>
            </tr></thead>
            <tbody>
              {sim.weights.map((w) => (
                <tr key={w.name} className="border-t border-gray-50 dark:border-slate-800">
                  <td className="py-1 pr-2 truncate max-w-[180px]">
                    {w.name}{w.new && <span className="ml-1 text-[10px] text-brand-600">{t("planning.search.new")}</span>}
                  </td>
                  <td className="py-1 text-right tabular-nums text-gray-500">{w.before_pct.toFixed(1)}%</td>
                  <td className="py-1 text-right tabular-nums">{w.after_pct.toFixed(1)}%</td>
                  <td className={`py-1 text-right tabular-nums ${w.delta_pct > 0 ? "text-green-600" : w.delta_pct < 0 ? "text-red-600" : "text-gray-300"}`}>
                    {w.delta_pct > 0 ? "+" : ""}{w.delta_pct.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-1">{t("planning.sim.xrayRules")}</h4>
          <p className="text-xs text-gray-400 mb-2">
            {changed.length ? t("planning.sim.rulesChanged", { n: changed.length }) : t("planning.sim.noRuleChange")}
          </p>
          <table className="w-full text-xs">
            <tbody>
              {sim.rule_changes.map((r) => (
                <tr key={r.key} className={`border-t border-gray-50 dark:border-slate-800 ${r.changed ? "bg-brand-50/50 dark:bg-slate-800" : ""}`}>
                  <td className="py-1 pr-2">{r.name}</td>
                  <td className={`py-1 text-right ${STATUS_COLOR[r.before_status ?? "info"]}`}>
                    {r.before_actual != null ? `${r.before_actual}%` : "—"}
                  </td>
                  <td className="py-1 px-1 text-gray-300"><ArrowRight className="w-3 h-3" /></td>
                  <td className={`py-1 text-right font-medium ${STATUS_COLOR[r.after_status]}`}>
                    {r.after_actual != null ? `${r.after_actual}%` : "—"} {r.after_status.toUpperCase()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ExecuteDialog({ scenario, sim, onClose }: { scenario: Scenario; sim: SimulationResult; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [accountId, setAccountId] = useState<string>("");
  const [rows, setRows] = useState(() =>
    scenario.items.map((it, i) => ({
      item_id: it.id!, name: it.name,
      quantity: String(+(sim.items[i]?.quantity ?? it.quantity ?? 0).toFixed(4)),
      price: String(+(sim.items[i]?.price_eur ?? it.price_eur ?? 0).toFixed(4)),
      fee: String(it.fee_eur ?? 0), account_id: it.account_id,
    })),
  );
  useEffect(() => { if (!accountId && accounts[0]) setAccountId(String(accounts[0].id)); }, [accounts, accountId]);

  const exec = useMutation({
    mutationFn: () => planningService.execute(scenario.id, {
      account_id: Number(accountId), date,
      items: rows.map((r) => ({ item_id: r.item_id, quantity: Number(r.quantity.replace(",", ".")),
        price: Number(r.price.replace(",", ".")), fee: Number(r.fee.replace(",", ".")) || 0, account_id: r.account_id })),
    }),
    onSuccess: () => {
      for (const k of ["planning-scenarios", "portfolio-dashboard", "transactions", "xray", "accounts"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const set = (i: number, k: "quantity" | "price" | "fee", v: string) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const err = (exec.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-5 max-h-[90vh] overflow-y-auto">
        <h3 className="text-base font-bold">{t("planning.exec.title", { name: scenario.name })}</h3>
        <p className="text-xs text-gray-500 mt-1">{t("planning.exec.desc")}</p>
        {exec.isSuccess ? (
          <div className="mt-4 text-sm text-green-700 flex items-center gap-2">
            <Check className="w-4 h-4" /> {t("planning.exec.done", { n: exec.data.created.length, skipped: exec.data.skipped_rows.length })}
            <Button size="sm" className="ml-auto" onClick={onClose}>{t("common.close")}</Button>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-3 mt-4">
              <label className="text-xs text-gray-500 flex flex-col gap-0.5">{t("planning.exec.account")}
                <select value={accountId} onChange={(e) => setAccountId(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm">
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label className="text-xs text-gray-500 flex flex-col gap-0.5">{t("planning.exec.date")}
                <input type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
              </label>
            </div>
            <table className="w-full text-sm mt-4">
              <thead><tr className="text-xs text-gray-400 text-left">
                <th className="py-1 font-medium">{t("common.asset")}</th>
                <th className="py-1 font-medium">{t("common.quantity")}</th>
                <th className="py-1 font-medium">{t("planning.exec.priceEur")}</th>
                <th className="py-1 font-medium">{t("planning.card.fee")}</th>
              </tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.item_id}>
                    <td className="py-1 pr-2 text-xs truncate max-w-[180px]">{r.name}</td>
                    {(["quantity", "price", "fee"] as const).map((k) => (
                      <td key={k} className="py-1 pr-2">
                        <input value={r[k]} onChange={(e) => set(i, k, e.target.value)} inputMode="decimal"
                          className="w-24 border border-gray-300 rounded-lg px-2 py-1 text-sm" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
              <Button onClick={() => exec.mutate()} loading={exec.isPending} disabled={!accountId}>
                <Play className="w-4 h-4 mr-1" /> {t("planning.exec.confirm")}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/** Carrello di acquisti ipotetici + risultati della simulazione + salvataggio/esecuzione dello scenario. */
export function PurchaseSimulator({ scenario, onScenarioSaved, preset }: {
  scenario: Scenario | null;
  onScenarioSaved: (s: Scenario | null) => void;
  /** Acquisti precompilati (es. dal versamento intelligente); ``nonce`` cambia a ogni invio. */
  preset?: { items: PlanItem[]; useCash: boolean; nonce: number } | null;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [items, setItems] = useState<PlanItem[]>(scenario?.items ?? []);
  const [useCash, setUseCash] = useState(scenario?.use_cash ?? false);
  const [name, setName] = useState(scenario?.name ?? "");
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    setItems(scenario?.items ?? []);
    setUseCash(scenario?.use_cash ?? false);
    setName(scenario?.name ?? "");
  }, [scenario]);

  useEffect(() => {
    if (!preset) return;
    setItems(preset.items);
    setUseCash(preset.useCash);
  }, [preset?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  const key = useMemo(() => JSON.stringify({ items, useCash }), [items, useCash]);
  const sim = useQuery({
    queryKey: ["planning-simulate", key],
    queryFn: () => planningService.simulate(items, useCash),
    enabled: items.length > 0,
    staleTime: 60 * 1000,
  });

  const save = useMutation({
    mutationFn: () => planningService.saveScenario({ id: scenario?.status === "draft" ? scenario.id : undefined,
      name: name.trim() || t("planning.sim.untitled"), use_cash: useCash, items }),
    onSuccess: (s) => { qc.invalidateQueries({ queryKey: ["planning-scenarios"] }); onScenarioSaved(s); },
  });

  const update = (i: number, patch: Partial<PlanItem>) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const executed = scenario?.status === "executed";
  const dirty = !scenario || JSON.stringify(scenario.items.map(({ id: _id, ...r }) => r)) !== JSON.stringify(items.map(({ id: _id, ...r }) => r)) || scenario.use_cash !== useCash || scenario.name !== name;

  return (
    <div className="space-y-4">
      <SecuritySearch onSelect={setSelected} />
      {selected && (
        <SecurityCard result={selected} onClose={() => setSelected(null)}
          onAdd={(it) => { setItems((xs) => [...xs, it]); setSelected(null); }} />
      )}

      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-100 flex-1">
            {scenario ? t("planning.sim.scenarioTitle", { name: scenario.name }) : t("planning.sim.cartTitle")}
            {executed && <span className="ml-2 text-xs rounded-full bg-green-100 text-green-700 px-2 py-0.5">{t("planning.scenarios.executed")}</span>}
          </h3>
          <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
            <input type="checkbox" checked={useCash} onChange={(e) => setUseCash(e.target.checked)} disabled={executed}
              className="rounded border-gray-300 text-brand-500" />
            <Wallet className="w-3.5 h-3.5" /> {t("planning.sim.useCash")}
          </label>
        </div>

        {items.length === 0 ? (
          <p className="text-sm text-gray-400">{t("planning.sim.empty")}</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-t border-gray-50 dark:border-slate-800 first:border-0">
                  <td className="py-1.5 pr-2 truncate max-w-[220px]">{it.name}</td>
                  <td className="py-1.5 pr-2">
                    <input
                      value={it.amount_eur ?? it.quantity ?? ""} inputMode="decimal" disabled={executed}
                      onChange={(e) => {
                        const v = Number(e.target.value.replace(",", ".")) || null;
                        update(i, it.amount_eur != null ? { amount_eur: v } : { quantity: v });
                      }}
                      className="w-24 border border-gray-300 rounded-lg px-2 py-1 text-sm"
                    />
                    <span className="ml-1 text-xs text-gray-400">{it.amount_eur != null ? "€" : t("planning.card.units")}</span>
                  </td>
                  <td className="py-1.5 text-xs text-gray-400">
                    {sim.data?.items[i] && `${sim.data.items[i].asset_class} · ${sim.data.items[i].quantity.toFixed(3)} × ${sim.data.items[i].price_eur.toFixed(2)} €`}
                  </td>
                  <td className="py-1.5 text-right">
                    {!executed && (
                      <button onClick={() => setItems((xs) => xs.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {items.length > 0 && !executed && (
          <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-gray-100 dark:border-slate-800">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("planning.sim.scenarioName")}
              className="flex-1 min-w-[180px] border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
            <Button size="sm" variant="secondary" onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty}>
              <Save className="w-4 h-4 mr-1" /> {scenario?.status === "draft" ? t("planning.sim.update") : t("planning.sim.save")}
            </Button>
            {scenario?.status === "draft" && !dirty && sim.data && (
              <Button size="sm" onClick={() => setExecuting(true)}>
                <Play className="w-4 h-4 mr-1" /> {t("planning.sim.execute")}
              </Button>
            )}
            {scenario && (
              <Button size="sm" variant="secondary" onClick={() => onScenarioSaved(null)}>{t("planning.sim.newSimulation")}</Button>
            )}
          </div>
        )}
      </div>

      {sim.isLoading && items.length > 0 && <div className="h-48 bg-gray-50 dark:bg-slate-800 rounded-xl animate-pulse" />}
      {sim.isError && <p className="text-sm text-red-600">{t("planning.sim.error")}</p>}
      {sim.data && items.length > 0 && <Results sim={sim.data} />}

      {executing && scenario && sim.data && (
        <ExecuteDialog scenario={scenario} sim={sim.data} onClose={() => { setExecuting(false); onScenarioSaved(null); }} />
      )}
    </div>
  );
}
