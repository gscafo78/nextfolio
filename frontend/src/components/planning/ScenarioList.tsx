import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, GitCompare, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { useZenMode } from "@/context/ThemeContext";
import { planningService, type Scenario } from "@/services/planning";
import { getIntlLocale } from "@/utils/format";

/** Scenari salvati: apri, confronta (fino a 4), elimina. */
export function ScenarioList({ onOpen }: { onOpen: (s: Scenario) => void }) {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const qc = useQueryClient();
  const [checked, setChecked] = useState<number[]>([]);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const { data: scenarios = [], isLoading } = useQuery({ queryKey: ["planning-scenarios"], queryFn: planningService.scenarios });
  const cmp = useQuery({
    queryKey: ["planning-compare", compareIds],
    queryFn: () => planningService.compare(compareIds),
    enabled: compareIds.length >= 2,
  });
  const del = useMutation({
    mutationFn: planningService.deleteScenario,
    onSuccess: () => { setConfirmDelete(null); qc.invalidateQueries({ queryKey: ["planning-scenarios"] }); },
  });

  const eur = (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }));
  const toggle = (id: number) =>
    setChecked((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length < 4 ? [...c, id] : c));

  if (isLoading) return <div className="h-24 bg-gray-50 rounded-xl animate-pulse" />;
  if (!scenarios.length) return <p className="text-sm text-gray-400">{t("planning.scenarios.none")}</p>;

  const classes = Array.from(new Set((cmp.data ?? []).flatMap((x) => x.simulation?.allocation_after.by_asset_class.map((i) => i.label) ?? [])));

  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-50 dark:divide-slate-800">
        {scenarios.map((s) => (
          <div key={s.id} className="flex items-center gap-3 px-4 py-3">
            <input type="checkbox" checked={checked.includes(s.id)} onChange={() => toggle(s.id)}
              className="rounded border-gray-300 text-brand-500" title={t("planning.scenarios.selectCompare")} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{s.name}
                <span className={`ml-2 text-[10px] rounded-full px-2 py-0.5 ${s.status === "executed" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {t(s.status === "executed" ? "planning.scenarios.executed" : "planning.scenarios.draft")}
                </span>
              </p>
              <p className="text-xs text-gray-400 truncate">
                {s.items.map((i) => i.name).join(", ")} · {new Date(s.updated_at).toLocaleDateString(i18n.language)}
              </p>
            </div>
            <Button size="sm" variant="secondary" onClick={() => onOpen(s)}><FolderOpen className="w-4 h-4 mr-1" />{t("planning.scenarios.open")}</Button>
            {confirmDelete === s.id ? (
              <Button size="sm" className="!bg-red-600" onClick={() => del.mutate(s.id)} loading={del.isPending}>{t("common.delete")}</Button>
            ) : (
              <button onClick={() => setConfirmDelete(s.id)} className="p-1.5 text-gray-300 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
            )}
          </div>
        ))}
      </div>

      <Button size="sm" onClick={() => setCompareIds(checked)} disabled={checked.length < 2}>
        <GitCompare className="w-4 h-4 mr-1" /> {t("planning.scenarios.compare", { n: checked.length })}
      </Button>

      {compareIds.length >= 2 && (
        cmp.isLoading ? <div className="h-32 bg-gray-50 rounded-xl animate-pulse" /> : cmp.data && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-gray-400 text-left">
                <th className="py-1 font-medium" />
                {cmp.data.map((x) => <th key={x.scenario.id} className="py-1 font-medium text-right">{x.scenario.name}</th>)}
              </tr></thead>
              <tbody>
                <tr className="border-t border-gray-50"><td className="py-1 text-xs text-gray-500">{t("planning.sim.invested")}</td>
                  {cmp.data.map((x) => <td key={x.scenario.id} className="py-1 text-right tabular-nums">{x.simulation ? eur(x.simulation.invested_eur + x.simulation.fees_eur) : "—"}</td>)}</tr>
                <tr className="border-t border-gray-50"><td className="py-1 text-xs text-gray-500">{t("planning.sim.cash")}</td>
                  {cmp.data.map((x) => <td key={x.scenario.id} className="py-1 text-right tabular-nums">{x.simulation ? eur(x.simulation.cash_after_eur) : "—"}</td>)}</tr>
                <tr className="border-t border-gray-50"><td className="py-1 text-xs text-gray-500">{t("planning.sim.xrayScore")}</td>
                  {cmp.data.map((x) => <td key={x.scenario.id} className="py-1 text-right tabular-nums">{x.simulation ? `${x.simulation.xray_before.score} → ${x.simulation.xray_after.score}` : "—"}</td>)}</tr>
                {classes.map((c) => (
                  <tr key={c} className="border-t border-gray-50"><td className="py-1 text-xs text-gray-500">{c}</td>
                    {cmp.data.map((x) => {
                      const v = x.simulation?.allocation_after.by_asset_class.find((i) => i.label === c)?.pct;
                      return <td key={x.scenario.id} className="py-1 text-right tabular-nums">{v != null ? `${v.toFixed(1)}%` : "—"}</td>;
                    })}</tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
