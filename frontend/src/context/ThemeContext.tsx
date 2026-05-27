import { createContext, useContext, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { authService } from "@/services/auth";

export type ThemeMode = "light" | "dark" | "system";

const LS_KEY = "nf-theme";

export function applyTheme(mode: ThemeMode) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = mode === "dark" || (mode === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", isDark);
  try { localStorage.setItem(LS_KEY, mode); } catch { /* incognito */ }
}

const ThemeContext = createContext<ThemeMode>("system");
export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { data: settings, isLoading } = useQuery({
    queryKey: ["my-settings"],
    queryFn: authService.getSettings,
    enabled: authService.isAuthenticated(),
    staleTime: Infinity,
  });

  const mode: ThemeMode = (settings?.theme as ThemeMode | undefined) ?? "system";

  useEffect(() => {
    // While fetching, let the FOUC script's class stand — no flash.
    if (isLoading) return;

    applyTheme(mode);

    if (mode !== "system") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode, isLoading]);

  return (
    <ThemeContext.Provider value={mode}>
      {children}
    </ThemeContext.Provider>
  );
}
