import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authService } from "@/services/auth";
import { applyTheme } from "@/context/ThemeContext";

export function useAuth() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: user, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: authService.me,
    enabled: authService.isAuthenticated(),
    retry: false,
  });

  const logout = () => {
    // Resetta il tema PRIMA di svuotare la cache — impedisce che il tema del
    // precedente utente rimanga attivo durante il caricamento del prossimo.
    localStorage.removeItem("nf-theme");
    applyTheme("system");
    authService.clearTokens();
    queryClient.clear();
    navigate("/login");
  };

  const isSuperAdmin = user?.role === "SUPERADMIN";

  return { user, isLoading, isAuthenticated: !!user, logout, isSuperAdmin };
}
