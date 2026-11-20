import { Navigate } from "react-router-dom";

/** Gli strumenti di calcolo sono nella pagina Pianifica (scheda Obiettivi). */
export function Strumenti() {
  return <Navigate to="/pianifica?tab=obiettivi" replace />;
}
