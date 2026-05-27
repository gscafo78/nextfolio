import { createContext, useContext } from "react";

interface SettingsModalContextType {
  openSettings: () => void;
}

export const SettingsModalContext = createContext<SettingsModalContextType>({
  openSettings: () => {},
});

export function useSettingsModal() {
  return useContext(SettingsModalContext);
}
