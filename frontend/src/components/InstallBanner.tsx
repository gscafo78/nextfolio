import { Download, X } from "lucide-react";
import { useInstallPrompt } from "@/hooks/useInstallPrompt";
import { useTranslation } from "react-i18next";

export function InstallBanner() {
  const { show, install, dismiss } = useInstallPrompt();
  const { t } = useTranslation();

  if (!show) return null;

  return (
    <div className="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-40
                    bg-slate-900 text-white rounded-2xl shadow-2xl px-4 py-3 flex items-center gap-3
                    animate-in slide-in-from-bottom-4 duration-300">
      <div className="w-9 h-9 bg-brand-500/20 rounded-xl flex items-center justify-center flex-shrink-0">
        <Download className="w-4 h-4 text-brand-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{t("pwa.installTitle")}</p>
        <p className="text-xs text-slate-400 mt-0.5">{t("pwa.installDesc")}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={install}
          className="px-3 py-1.5 bg-brand-500 hover:bg-brand-600 rounded-lg text-xs font-semibold transition-colors"
        >
          {t("pwa.install")}
        </button>
        <button
          onClick={dismiss}
          className="p-1 text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
