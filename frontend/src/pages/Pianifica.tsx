import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FolderOpen, ShoppingCart } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { PurchaseSimulator } from "@/components/planning/PurchaseSimulator";
import { ScenarioList } from "@/components/planning/ScenarioList";
import type { Scenario } from "@/services/planning";

const TABS = [
  { key: "simula", icon: ShoppingCart },
  { key: "scenari", icon: FolderOpen },
] as const;
type Tab = (typeof TABS)[number]["key"];

export function Pianifica() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((x) => x.key === params.get("tab"))?.key ?? "simula") as Tab;
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const go = (k: Tab) => setParams({ tab: k }, { replace: true });

  return (
    <>
      <TopBar title={t("nav.planning")} />
      <main className="flex-1 p-4 md:p-6 max-w-5xl mx-auto w-full space-y-4">
        <p className="text-sm text-gray-500">{t("planning.intro")}</p>
        <div className="flex gap-1 border-b border-gray-200 dark:border-slate-700 overflow-x-auto">
          {TABS.map(({ key, icon: Icon }) => (
            <button key={key} onClick={() => go(key)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${
                tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}>
              <Icon className="w-4 h-4" /> {t(`planning.tabs.${key}`)}
            </button>
          ))}
        </div>

        {tab === "simula" && <PurchaseSimulator scenario={scenario} onScenarioSaved={setScenario} />}
        {tab === "scenari" && <ScenarioList onOpen={(s) => { setScenario(s); go("simula"); }} />}
      </main>
    </>
  );
}
