import { useAuth } from "@/hooks/useAuth";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const { user } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white text-sm font-medium">
          {user?.name?.[0]?.toUpperCase() ?? "U"}
        </div>
        <span className="text-sm text-gray-700">{user?.name}</span>
      </div>
    </header>
  );
}
