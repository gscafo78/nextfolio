import { NavLink } from "react-router-dom";
import { BarChart2, TrendingUp, PieChart, ArrowLeftRight, Settings } from "lucide-react";

const items = [
  { to: "/",             label: "Home",         icon: BarChart2 },
  { to: "/performance",  label: "Performance",  icon: TrendingUp },
  { to: "/allocazione",  label: "Allocazioni",  icon: PieChart },
  { to: "/transazioni",  label: "Transazioni",  icon: ArrowLeftRight },
  { to: "/impostazioni", label: "Impostazioni", icon: Settings },
];

export function BottomNav() {
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
            `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-[10px] font-medium transition-colors ${
              isActive ? "text-brand-600 dark:text-brand-400" : "text-gray-400 dark:text-slate-500"
            }`
          }
        >
          <Icon className="w-5 h-5" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
