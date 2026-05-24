import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authService } from "@/services/auth";

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
    authService.clearTokens();
    queryClient.clear();
    navigate("/login");
  };

  return { user, isLoading, isAuthenticated: !!user, logout };
}
