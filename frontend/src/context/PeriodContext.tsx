import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

const STORAGE_KEY = "dashboard_period";

interface PeriodContextValue {
  period: string;
  setPeriod: (p: string) => void;
}

const PeriodContext = createContext<PeriodContextValue | null>(null);

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [period, _setPeriod] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) ?? "ytd"
  );

  function setPeriod(p: string) {
    _setPeriod(p);
    localStorage.setItem(STORAGE_KEY, p);
  }

  return (
    <PeriodContext.Provider value={{ period, setPeriod }}>
      {children}
    </PeriodContext.Provider>
  );
}

export function usePeriod(): PeriodContextValue {
  const ctx = useContext(PeriodContext);
  if (!ctx) throw new Error("usePeriod must be used inside PeriodProvider");
  return ctx;
}
