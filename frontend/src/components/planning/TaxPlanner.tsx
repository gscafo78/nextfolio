import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Calculator, Info, Plus, Receipt, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { useZenMode } from "@/context/ThemeContext";
import { planningService } from "@/services/planning";
import { portfolioService } from "@/services/portfolio";
import { getIntlLocale } from "@/utils/format";

const card = "bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5";
const input = "border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-1 text-sm bg-white dark:bg-slate-800";

function useEur() {
  const zen = useZenMode();
  const { i18n } = useTranslation();
  return (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR" }));
}

function Overview() {
  const { t } = useTranslation();
  const eur = useEur();
  const { data: o, isLoading } = useQuery({ queryKey: ["planning-tax-overview"], queryFn: planningService.taxOverview });
  if (isLoading || !o) return <div className="h-40 bg-gray-50 rounded-xl animate-pulse" />;
  const pools = [...o.pool_standard.map((p) => ({ ...p, kind: t("planning.tax.poolStandard") })),
                 ...o.pool_crypto.map((p) => ({ ...p, kind: t("planning.tax.poolCrypto") }))];

  return (
    <div className="space-y-4">
      <div className={card}>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Receipt className="w-4 h-4 text-brand-500" />
          {t("planning.tax.yearTitle", { year: o.year })}</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {([["capitalGains", o.year_tax.capital_gains_tax_eur], ["income", o.year_tax.income_tax_eur],
             ["wealth", o.year_tax.wealth_tax_eur], ["total", o.year_tax.total_eur]] as const).map(([k, v]) => (
            <div key={k} className={`rounded-lg px-3 py-2 ${k === "total" ? "bg-brand-50 dark:bg-slate-800" : "bg-gray-50 dark:bg-slate-800"}`}>
              <p className="text-[11px] text-gray-500">{t(`planning.tax.${k}`)}</p>
              <p className="text-sm font-semibold tabular-nums">{eur(v)}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-2">{t("planning.tax.yearNote")}</p>
      </div>

      <div className={card}>
        <h3 className="text-sm font-semibold mb-2">{t("planning.tax.poolTitle")}</h3>
        {pools.length === 0 ? <p className="text-sm text-gray-400">{t("planning.tax.noPool")}</p> : (
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 text-left">
              <th className="py-1 font-medium">{t("planning.tax.pool")}</th><th className="py-1 font-medium">{t("planning.tax.realized")}</th>
              <th className="py-1 font-medium text-right">{t("planning.tax.residual")}</th><th className="py-1 font-medium text-right">{t("planning.tax.expires")}</th>
            </tr></thead>
            <tbody>{pools.map((p) => (
              <tr key={`${p.kind}-${p.year}`} className={`border-t border-gray-50 dark:border-slate-800 ${p.expiring ? "text-amber-700 font-medium" : ""}`}>
                <td className="py-1">{p.kind}</td><td className="py-1">{p.year}</td>
                <td className="py-1 text-right tabular-nums">{eur(p.amount)}</td>
                <td className="py-1 text-right">{p.expires_year}{p.expiring && " ⚠"}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>

      {(o.use_losses.length > 0 || o.expiring_standard + o.expiring_crypto > 0) && (
        <div className={card}>
          <h3 className="text-sm font-semibold">{t("planning.tax.useTitle", { amount: eur(o.expiring_standard + o.expiring_crypto) })}</h3>
          <p className="text-xs text-gray-400 mb-2">{t("planning.tax.useDesc")}</p>
          {o.use_losses.length === 0 ? <p className="text-sm text-gray-400">{t("planning.tax.noCandidates")}</p> : (
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-gray-400 text-left">
                <th className="py-1 font-medium">{t("common.asset")}</th><th className="py-1 font-medium">{t("planning.exec.account")}</th>
                <th className="py-1 font-medium text-right">{t("common.quantity")}</th><th className="py-1 font-medium text-right">{t("planning.tax.gain")}</th>
                <th className="py-1 font-medium text-right">{t("planning.tax.taxSaved")}</th>
              </tr></thead>
              <tbody>{o.use_losses.map((s) => (
                <tr key={`${s.asset_id}-${s.account}`} className="border-t border-gray-50 dark:border-slate-800">
                  <td className="py-1">{s.name}</td><td className="py-1 text-xs text-gray-500">{s.account}</td>
                  <td className="py-1 text-right tabular-nums">{s.quantity}</td>
                  <td className="py-1 text-right tabular-nums text-green-600">{eur(s.gain_eur)}</td>
                  <td className="py-1 text-right tabular-nums font-semibold">{eur(s.tax_saved_eur)}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}

      {o.harvest_losses.length > 0 && (
        <div className={card}>
          <h3 className="text-sm font-semibold">{t("planning.tax.harvestTitle")}</h3>
          <p className="text-xs text-gray-400 mb-2">{t("planning.tax.harvestDesc")}</p>
          <table className="w-full text-sm">
            <tbody>{o.harvest_losses.map((s) => (
              <tr key={`${s.asset_id}-${s.account}`} className="border-t border-gray-50 dark:border-slate-800 first:border-0">
                <td className="py-1">{s.name}</td><td className="py-1 text-xs text-gray-500">{s.account}</td>
                <td className="py-1 text-right tabular-nums">{s.quantity}</td>
                <td className="py-1 text-right tabular-nums text-red-600">{eur(s.loss_eur)}</td>
                <td className="py-1 text-right tabular-nums font-semibold">{eur(s.tax_saved_eur)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      <div className="flex items-start gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-xs text-blue-700">
        <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div className="space-y-0.5">{o.notes.map((n) => <p key={n}>{n}</p>)}</div>
      </div>
    </div>
  );
}

function SalesSimulator() {
  const { t } = useTranslation();
  const eur = useEur();
  const { data: positions = [] } = useQuery({ queryKey: ["positions"], queryFn: portfolioService.getPositions });
  const [rows, setRows] = useState<{ asset_id: number; quantity: string }[]>([]);
  const [pick, setPick] = useState("");
  const run = useMutation({
    mutationFn: () => planningService.simulateSales(rows.map((r) => ({ asset_id: r.asset_id, quantity: Number(r.quantity.replace(",", ".")) }))),
  });
  const err = (run.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;
  const r = run.data;
  const name = (id: number) => positions.find((p) => p.asset_id === id)?.name ?? String(id);

  return (
    <div className={card}>
      <h3 className="text-sm font-semibold">{t("planning.tax.salesTitle")}</h3>
      <p className="text-xs text-gray-400 mb-3">{t("planning.tax.salesDesc")}</p>
      <div className="space-y-1.5">
        {rows.map((row, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <span className="flex-1 truncate">{name(row.asset_id)}</span>
            <input value={row.quantity} inputMode="decimal" className={`${input} w-28`}
              onChange={(e) => setRows((rs) => rs.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} />
            <span className="text-xs text-gray-400">/ {positions.find((p) => p.asset_id === row.asset_id)?.quantity.toFixed(4)}</span>
            <button onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} className="text-gray-300 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        <select value={pick} onChange={(e) => setPick(e.target.value)} className={input}>
          <option value="">{t("planning.tax.choosePosition")}</option>
          {positions.filter((p) => !rows.some((r) => r.asset_id === p.asset_id)).map((p) => (
            <option key={p.asset_id} value={p.asset_id}>{p.name}</option>
          ))}
        </select>
        <Button size="sm" variant="secondary" disabled={!pick} onClick={() => {
          const p = positions.find((x) => x.asset_id === Number(pick));
          if (p) setRows((rs) => [...rs, { asset_id: p.asset_id, quantity: String(p.quantity) }]);
          setPick("");
        }}><Plus className="w-4 h-4 mr-1" /> {t("planning.tax.addSale")}</Button>
        <Button size="sm" onClick={() => run.mutate()} loading={run.isPending} disabled={!rows.length}>
          <Calculator className="w-4 h-4 mr-1" /> {t("planning.tax.simulate")}
        </Button>
      </div>
      {err && <p className="text-sm text-red-600 mt-2 flex gap-1"><AlertTriangle className="w-4 h-4" />{err}</p>}
      {r && (
        <div className="mt-4 space-y-3">
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 text-left">
              <th className="py-1 font-medium">{t("common.asset")}</th><th className="py-1 font-medium text-right">{t("planning.tax.proceeds")}</th>
              <th className="py-1 font-medium text-right">{t("planning.tax.cost")}</th><th className="py-1 font-medium text-right">{t("planning.tax.result")}</th>
              <th className="py-1 font-medium">{t("planning.tax.category")}</th>
            </tr></thead>
            <tbody>{r.sales.map((x, i) => (
              <tr key={i} className="border-t border-gray-50 dark:border-slate-800">
                <td className="py-1">{x.name}</td>
                <td className="py-1 text-right tabular-nums">{eur(x.proceeds_eur)}</td>
                <td className="py-1 text-right tabular-nums">{eur(x.cost_eur)}</td>
                <td className={`py-1 text-right tabular-nums ${x.gain_loss_eur >= 0 ? "text-green-600" : "text-red-600"}`}>{eur(x.gain_loss_eur)}</td>
                <td className="py-1 text-xs text-gray-500">{t(`planning.tax.categories.${x.category}`)} · {(x.tax_rate * 100).toFixed(1)}%</td>
              </tr>
            ))}</tbody>
          </table>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            {(["total_tax_eur", "carryforward_used_eur", "new_carryforward_eur"] as const).map((k) => (
              <div key={k} className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2">
                <p className="text-[11px] text-gray-500">{t(`planning.tax.summary.${k}`)}</p>
                <p className="text-sm font-semibold tabular-nums">{eur(r.before[k])} → {eur(r.after[k])}</p>
              </div>
            ))}
            <div className={`rounded-lg px-3 py-2 ${r.delta_tax_eur > 0 ? "bg-red-50" : "bg-green-50"}`}>
              <p className="text-[11px] text-gray-500">{t("planning.tax.deltaTax")}</p>
              <p className="text-sm font-bold tabular-nums">{r.delta_tax_eur > 0 ? "+" : ""}{eur(r.delta_tax_eur)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function TaxPlanner() {
  return (
    <div className="space-y-4">
      <Overview />
      <SalesSimulator />
    </div>
  );
}
