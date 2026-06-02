import { NavLink } from "react-router-dom";
import { BarChart2, TrendingUp, PieChart, ArrowLeftRight, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Ordine delle route usato anche da useSwipeNavigation */
export const NAV_ROUTES = ["/", "/performance", "/allocazione", "/transazioni", "/impostazioni"];

export function BottomNav() {
  const { t } = useTranslation();

  const items = [
    { to: "/",             label: t("nav.dashboard"),    icon: BarChart2 },
    { to: "/performance",  label: t("nav.performance"),  icon: TrendingUp },
    { to: "/allocazione",  label: t("nav.allocation"),   icon: PieChart },
    { to: "/transazioni",  label: t("nav.transactions"), icon: ArrowLeftRight },
    { to: "/impostazioni", label: t("nav.settings"),     icon: Settings },
  ];

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex md:hidden bg-white dark:bg-slate-900 border-t border-gray-200 dark:border-slate-700"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            /* In portrait: icona + label. In landscape: solo icona (py ridotto, label nascosta) */
            `flex-1 flex flex-col items-center justify-center py-2 landscape:py-1 gap-0.5 text-[10px] font-medium transition-colors ${
              isActive ? "text-brand-600 dark:text-brand-400" : "text-gray-400 dark:text-slate-500"
            }`
          }
        >
          <Icon className="w-5 h-5" />
          <span className="landscape:hidden">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
