import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Settings, LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Chiude il menu se si clicca fuori
  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function handleLogout() {
    setOpen(false);
    logout();
  }

  return (
    <header className="h-14 md:h-16 bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between px-4 md:px-6">
      <h1 className="text-base md:text-lg font-semibold text-gray-900 dark:text-slate-100">
        {title}
      </h1>

      {/* Menu utente */}
      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 md:gap-2.5 rounded-lg px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors"
          aria-haspopup="true"
          aria-expanded={open}
        >
          <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white text-sm font-medium select-none">
            {user?.name?.[0]?.toUpperCase() ?? "U"}
          </div>
          <span className="hidden md:block text-sm text-gray-700 dark:text-slate-300">
            {user?.name}
          </span>
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1.5 w-48 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl shadow-lg py-1 z-50">
            <Link
              to="/impostazioni"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
            >
              <Settings className="w-4 h-4 flex-shrink-0" />
              {t("nav.settings")}
            </Link>
            <div className="my-1 border-t border-gray-100 dark:border-slate-700" />
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 dark:text-red-400 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
            >
              <LogOut className="w-4 h-4 flex-shrink-0" />
              {t("nav.logout")}
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
