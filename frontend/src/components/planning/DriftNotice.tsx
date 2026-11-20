import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { useTranslation } from "react-i18next";
import { planningService } from "@/services/planning";

/** Avviso in dashboard quando una asset class esce dalla banda di tolleranza dell'allocazione obiettivo. */
export function DriftNotice() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["planning-drift"], queryFn: planningService.drift, staleTime: 5 * 60 * 1000 });
  if (!data?.configured || !data.out_of_band) return null;
  const off = data.classes.filter((c) => c.out_of_band);
  return (
    <Link to="/pianifica?tab=versamento"
      className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 hover:bg-amber-100">
      <Compass className="w-4 h-4 mt-0.5 flex-shrink-0" />
      <span>
        {t("planning.drift.notice", { tol: data.tolerance_pct })}{" "}
        {off.map((c) => `${c.label} ${c.current_pct.toFixed(0)}% (${t("planning.contrib.target")} ${c.target_pct.toFixed(0)}%)`).join(", ")}
        {" · "}<span className="underline">{t("planning.drift.action")}</span>
      </span>
    </Link>
  );
}
