import { api } from "./api";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  name: string;
  currency: string;
}

export const authService = {
  async register(email: string, password: string, name: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/register", { email, password, name });
    return data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/login", { email, password });
    return data;
  },

  async me(): Promise<UserOut> {
    const { data } = await api.get<UserOut>("/auth/me");
    return data;
  },

  saveTokens(tokens: TokenResponse) {
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
  },

  clearTokens() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem("access_token");
  },
};
