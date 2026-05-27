import { useAuth } from "@/hooks/useAuth";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const { user } = useAuth();

  return (
    <header className="h-14 md:h-16 bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between px-4 md:px-6">
      <h1 className="text-base md:text-lg font-semibold text-gray-900 dark:text-slate-100">{title}</h1>
      <div className="flex items-center gap-2 md:gap-3">
        <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white text-sm font-medium">
          {user?.name?.[0]?.toUpperCase() ?? "U"}
        </div>
        <span className="hidden md:block text-sm text-gray-700 dark:text-slate-300">{user?.name}</span>
      </div>
    </header>
  );
}
