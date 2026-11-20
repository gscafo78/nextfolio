import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, AlertTriangle, MailWarning } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useZenMode } from "@/context/ThemeContext";
import { bondService } from "@/services/bonds";
import { getIntlLocale } from "@/utils/format";

/** Interruttore «Monitora convenienza vendita» con il confronto vendi ora / tieni a scadenza (netto). */
export function BondMonitorCard({ assetId }: { assetId: number }) {
  const { t, i18n } = useTranslation();
  const zen = useZenMode();
  const qc = useQueryClient();
  const key = ["bond-monitor", assetId];
  const { data: m, isLoading } = useQuery({ queryKey: key, queryFn: () => bondService.getMonitor(assetId), staleTime: 60 * 1000 });
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => bondService.setMonitor(assetId, enabled),
    onSuccess: (data) => qc.setQueryData(key, data),
  });
  const err = (toggle.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  const eur = (v: number) => (zen ? "•••••" : v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR" }));
  const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString(i18n.language) : t("bondMonitor.never"));
  const ev = m?.evaluation;
  const ok = ev?.status === "ok";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
      <div className="flex items-start gap-3">
        <BellRing className={`w-5 h-5 mt-0.5 ${m?.enabled ? "text-brand-600" : "text-gray-300"}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900">{t("bondMonitor.title")}</p>
          <p className="text-xs text-gray-500">{t("bondMonitor.desc")}</p>
        </div>
        <label className="inline-flex items-center cursor-pointer select-none" title={t("bondMonitor.toggle")}>
          <input
            type="checkbox"
            className="sr-only peer"
            checked={!!m?.enabled}
            disabled={isLoading || toggle.isPending}
            onChange={(e) => toggle.mutate(e.target.checked)}
          />
          <span className="relative w-10 h-6 rounded-full bg-gray-200 peer-checked:bg-brand-600 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:w-5 after:h-5 after:bg-white after:rounded-full after:transition-transform peer-checked:after:translate-x-4 peer-disabled:opacity-50" />
        </label>
      </div>

      {err && <p className="text-xs text-red-600 flex items-start gap-1.5"><AlertTriangle className="w-3.5 h-3.5 mt-0.5" />{err}</p>}
      {m?.enabled && !m.email_configured && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-1.5">
          <MailWarning className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />{t("bondMonitor.noEmail")}
        </p>
      )}

      {ev && !ok && <p className="text-xs text-gray-500">{t("bondMonitor.missing")}: {ev.reason}</p>}

      {ev && ok && (
        <>
          <div className={`rounded-lg px-3 py-2 text-sm font-medium ${ev.should_sell ? "bg-green-50 text-green-800 border border-green-200" : "bg-gray-50 text-gray-700"}`}>
            {ev.should_sell
              ? t("bondMonitor.sellBetter", { amount: eur(ev.advantage_eur) })
              : t("bondMonitor.holdBetter", { amount: eur(-ev.advantage_eur) })}
            {ev.break_even_price != null && (
              <span className="block text-xs font-normal mt-0.5">
                {t("bondMonitor.breakEven", { price: ev.break_even_price.toFixed(3), current: ev.price.toFixed(3) })}
              </span>
            )}
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 text-left">
                <th className="py-1 font-medium" />
                <th className="py-1 font-medium text-right">{t("bondMonitor.sellNow")}</th>
                <th className="py-1 font-medium text-right">{t("bondMonitor.holdToMaturity")}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              <tr className="border-t border-gray-50"><td className="py-1 text-gray-500">{t("bondMonitor.grossProceeds")}</td>
                <td className="py-1 text-right">{eur(ev.sell_gross_eur)}</td>
                <td className="py-1 text-right">{eur(ev.hold_redemption_eur + ev.hold_future_coupons_gross_eur)}</td></tr>
              <tr className="border-t border-gray-50"><td className="py-1 text-gray-500">{t("bondMonitor.taxes", { pct: (ev.tax_rate * 100).toFixed(1).replace(".0", "") })}</td>
                <td className="py-1 text-right">−{eur(ev.sell_tax_eur)}</td><td className="py-1 text-right">−{eur(ev.hold_tax_eur)}</td></tr>
              <tr className="border-t border-gray-100 font-semibold"><td className="py-1">{t("bondMonitor.netProceeds")}</td>
                <td className="py-1 text-right">{eur(ev.sell_net_eur)}</td><td className="py-1 text-right">{eur(ev.hold_net_eur)}</td></tr>
              <tr className="border-t border-gray-50"><td className="py-1 text-gray-500">{t("bondMonitor.collected")}</td>
                <td className="py-1 text-right" colSpan={2}>{eur(ev.collected_coupons_net_eur)}</td></tr>
              <tr className="border-t border-gray-50"><td className="py-1 text-gray-500">{t("bondMonitor.totalGain")}</td>
                <td className="py-1 text-right">{eur(ev.total_gain_sell_eur)}</td><td className="py-1 text-right">{eur(ev.total_gain_hold_eur)}</td></tr>
            </tbody>
          </table>
          <p className="text-[11px] text-gray-400">
            {t("bondMonitor.note", { coupons: ev.future_coupons, date: ev.maturity_date ?? "—" })}
          </p>
        </>
      )}

      {m?.enabled && (
        <p className="text-[11px] text-gray-400">
          {t("bondMonitor.lastChecked", { date: fmtDate(m.last_checked_at) })} · {t("bondMonitor.lastEmail", { date: fmtDate(m.last_notified_at) })}
          {m.active && ` · ${t("bondMonitor.alreadyNotified")}`}
        </p>
      )}
    </div>
  );
}
