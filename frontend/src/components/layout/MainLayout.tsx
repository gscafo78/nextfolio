import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { BottomNav } from "./BottomNav";
import { InstallBanner } from "@/components/InstallBanner";

export function MainLayout() {
  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-slate-950">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        <Outlet />
      </div>
      <BottomNav />
      <InstallBanner />
    </div>
  );
}
