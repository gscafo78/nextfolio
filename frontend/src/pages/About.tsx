import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Info, Server } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "@/services/api";
import { useAuth } from "@/hooks/useAuth";
import { TopBar } from "@/components/layout/TopBar";
import logo from "@/assets/logo.svg";

interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

const CHANGELOG: Array<{
  version: string;
  date: string;
  sections: Array<{ type: "added" | "fixed" | "changed"; items: string[] }>;
}> = [
  {
    version: "1.5.2",
    date: "2026-06-02",
    sections: [
      {
        type: "fixed",
        items: [
          'Mutex per il refresh token: eliminato logout inatteso a ~24h con "Ricordami"',
          "Refresh proattivo al reload: nessun burst di 401 dopo inattività prolungata",
        ],
      },
    ],
  },
  {
    version: "1.5.1",
    date: "2026-05-30",
    sections: [
      { type: "added", items: ["URL privacy: barra indirizzi mostra sempre solo il dominio"] },
      {
        type: "fixed",
        items: [
          'Sessione persistente "Ricordami": flag rem propagato correttamente fino a 30 giorni',
          "Percentuale variazione giornaliera visibile nella KPI card Dashboard",
        ],
      },
    ],
  },
  {
    version: "1.5.0",
    date: "2026-05-28",
    sections: [
      {
        type: "added",
        items: [
          "Registrazione pubblica con verifica OTP email (abilitabile dal superadmin)",
          "Pagina /register con form a 2 step e countdown 15 min",
          "Toggle registrazione pubblica nel pannello Admin",
          "Task Celery cleanup utenti non verificati (ogni giorno alle 03:00)",
        ],
      },
    ],
  },
  {
    version: "1.4.0",
    date: "2026-05-27",
    sections: [
      {
        type: "added",
        items: [
          "Internazionalizzazione completa: IT · EN · FR · DE",
          "Selettore lingua in Impostazioni con cambio istantaneo",
          "Formato date e numeri adattato alla lingua selezionata",
        ],
      },
    ],
  },
  {
    version: "1.3.0",
    date: "2026-05-20",
    sections: [
      {
        type: "added",
        items: [
          "Zen Mode: toggle privacy che maschera i valori monetari in tutta l'app",
          "Login page redesign: split layout dark/light con grafico SVG",
          "Tema dark / light / sistema con cambio istantaneo",
          "TopBar consistente, paginazione Transazioni, stacked allocation bar",
        ],
      },
    ],
  },
  {
    version: "1.2.0",
    date: "2026-05-15",
    sections: [
      {
        type: "added",
        items: [
          "Messa in produzione: nextfolio.myhomecloud.it via Cloudflare Tunnel",
          "Sentry error tracking (backend + frontend)",
          "Backup PostgreSQL automatico ogni notte",
          "PWA icon aggiornata",
        ],
      },
    ],
  },
];

const TYPE_COLOR: Record<string, string> = {
  added: "bg-emerald-50 text-emerald-700 border-emerald-200",
  fixed: "bg-blue-50 text-blue-700 border-blue-200",
  changed: "bg-amber-50 text-amber-700 border-amber-200",
};

export function About() {
  const { t } = useTranslation();
  const { isSuperAdmin } = useAuth();
  const [showOlder, setShowOlder] = useState(false);

  const { data: health } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await api.get<HealthResponse>("/health", { baseURL: "" });
      return data;
    },
    staleTime: 1000 * 60 * 5,
    enabled: isSuperAdmin,
  });

  const recent = CHANGELOG.slice(0, 3);
  const older = CHANGELOG.slice(3);

  return (
    <>
      <TopBar title={t("about.title")} />
      <main className="flex-1">
        <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">

          {/* Header card */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 shadow-sm px-6 py-6 flex items-center gap-5">
            <img src={logo} alt="Nextfolio" className="h-12 w-auto flex-shrink-0" />
            <div>
              <p className="text-sm text-gray-500 dark:text-slate-400 mt-1 leading-relaxed">
                {t("about.description")}
              </p>
              <div className="flex items-center gap-2 mt-3">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 border border-brand-200 dark:border-brand-700 rounded-full px-2.5 py-0.5">
                  <Info className="w-3 h-3" />
                  {t("about.version")} {__APP_VERSION__}
                </span>
              </div>
            </div>
          </div>

          {/* System info — superadmin only */}
          {isSuperAdmin && (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 shadow-sm px-6 py-5">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 flex items-center gap-2 mb-4">
                <Server className="w-4 h-4 text-gray-400" />
                {t("about.systemInfo")}
              </h2>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-0.5">{t("about.frontend")}</p>
                  <p className="font-mono text-gray-700 dark:text-slate-300">{__APP_VERSION__}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-0.5">{t("about.backend")}</p>
                  <p className="font-mono text-gray-700 dark:text-slate-300">{health?.version ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-0.5">{t("about.environment")}</p>
                  <p className="font-mono text-gray-700 dark:text-slate-300">{health?.environment ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-0.5">Status</p>
                  <p className="font-mono text-emerald-600 dark:text-emerald-400">{health?.status ?? "—"}</p>
                </div>
              </div>
            </div>
          )}

          {/* Changelog */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 shadow-sm px-6 py-5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-5">
              {t("about.changelog")}
            </h2>

            <div className="space-y-6">
              {recent.map((entry) => (
                <ChangelogEntry key={entry.version} entry={entry} t={t} />
              ))}
            </div>

            {older.length > 0 && (
              <div className="mt-4">
                <button
                  onClick={() => setShowOlder((v) => !v)}
                  className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-slate-300 transition-colors"
                >
                  {showOlder ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  {t("about.changelog_older")}
                </button>

                {showOlder && (
                  <div className="mt-4 space-y-6 border-t border-gray-100 dark:border-slate-700 pt-4">
                    {older.map((entry) => (
                      <ChangelogEntry key={entry.version} entry={entry} t={t} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Copyright */}
          <p className="text-center text-xs text-gray-300 dark:text-slate-600 pb-4">
            {t("about.copyright", { year: new Date().getFullYear() })}
          </p>

        </div>
      </main>
    </>
  );
}

function ChangelogEntry({
  entry,
  t,
}: {
  entry: (typeof CHANGELOG)[0];
  t: ReturnType<typeof useTranslation>["t"];
}) {
  return (
    <div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-sm font-bold text-gray-900 dark:text-slate-100">v{entry.version}</span>
        <span className="text-xs text-gray-400 dark:text-slate-500">{entry.date}</span>
      </div>
      <div className="space-y-2 pl-1">
        {entry.sections.map((section) => (
          <div key={section.type}>
            <span
              className={`inline-block text-[10px] font-semibold uppercase tracking-wide border rounded px-1.5 py-0.5 mb-1 ${TYPE_COLOR[section.type]}`}
            >
              {t(`about.changelog_${section.type}`)}
            </span>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item} className="text-sm text-gray-600 dark:text-slate-400 flex gap-2">
                  <span className="text-gray-300 dark:text-slate-600 mt-0.5 flex-shrink-0">·</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
