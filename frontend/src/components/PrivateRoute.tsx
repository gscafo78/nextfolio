import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { authService } from "@/services/auth";

export function PrivateRoute() {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      setAuthenticated(false);
      setReady(true);
      return;
    }
    // Proactively refresh if the access token expires within 60 seconds.
    // This prevents a burst of concurrent 401s on page reload after long inactivity.
    authService.refreshIfExpired().finally(() => {
      setAuthenticated(authService.isAuthenticated());
      setReady(true);
    });
  }, []);

  if (!ready) return null;
  if (!authenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}
