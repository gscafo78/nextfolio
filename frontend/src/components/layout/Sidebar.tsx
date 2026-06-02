import { NavLink } from "react-router-dom";
import {
  BarChart2,
  ArrowLeftRight,
  TrendingUp,
  PieChart,
  Calculator,
  Wrench,
  Bell,
  Upload,
  ShieldCheck,
  Coins,
  ScanSearch,
  Eye,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import logo from "@/assets/logo.svg";

export function Sidebar() {
  const { t } = useTranslation();
  const { isSuperAdmin } = useAuth();

  const navItems = [
    { to: "/", label: t("nav.dashboard"), icon: BarChart2 },
    { to: "/transazioni", label: t("nav.transactions"), icon: ArrowLeftRight },
    { to: "/performance", label: t("nav.performance"), icon: TrendingUp },
    { to: "/allocazione", label: t("nav.allocation"), icon: PieChart },
    { to: "/fiscale", label: t("nav.tax"), icon: Calculator },
    { to: "/dividendi", label: t("nav.dividends"), icon: Coins },
    { to: "/xray",      label: t("nav.xray"),      icon: ScanSearch },
    { to: "/watchlist", label: t("nav.watchlist"), icon: Eye },
    { to: "/strumenti", label: t("nav.tools"), icon: Wrench },
    { to: "/alert", label: t("nav.alerts"), icon: Bell },
    { to: "/import", label: t("nav.import"), icon: Upload },
  ];

  return (
    <aside className="hidden md:flex w-64 min-h-screen bg-white dark:bg-slate-900 border-r border-gray-200 dark:border-slate-700 flex-col">
      <div className="px-6 py-5 border-b border-gray-200 dark:border-slate-700">
        <img src={logo} alt="Nextfolio" className="h-9 w-auto" fetchPriority="high" decoding="sync" />
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400"
                  : "text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
        {isSuperAdmin && (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400"
                  : "text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
              }`
            }
          >
            <ShieldCheck className="w-4 h-4 flex-shrink-0" />
            {t("nav.admin")}
          </NavLink>
        )}
      </nav>
    </aside>
  );
}
