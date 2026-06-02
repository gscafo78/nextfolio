import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { BottomNav, NAV_ROUTES } from "./BottomNav";
import { InstallBanner } from "@/components/InstallBanner";
import { useSwipeNavigation } from "@/hooks/useSwipeNavigation";

export function MainLayout() {
  const swipe = useSwipeNavigation(NAV_ROUTES);

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-slate-950">
      <Sidebar />
      {/* onTouchStart/End attivi solo su mobile — md+ non hanno BottomNav */}
      <div
        className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0"
        onTouchStart={swipe.onTouchStart}
        onTouchEnd={swipe.onTouchEnd}
      >
        <Outlet />
      </div>
      <BottomNav />
      <InstallBanner />
    </div>
  );
}
