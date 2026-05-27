import { api } from "./api";

export interface TokenResponse {
  access_token: string | null;
  refresh_token: string | null;
  token_type: string;
  requires_2fa: boolean;
  session_token: string | null;
}

export interface RegisterResponse {
  requires_verification: boolean;
  email: string | null;
  access_token: string | null;
  refresh_token: string | null;
  token_type: string;
}

export interface RegistrationStatus {
  allow_public_registration: boolean;
}

export interface UserOut {
  id: number;
  email: string;
  name: string;
  currency: string;
  role: "SUPERADMIN" | "USER";
  two_factor_enabled: boolean;
}

export interface TwoFactorSetupOut {
  secret: string;
  uri: string;
}

export interface UserSettingsOut {
  theme: string;
  display_currency: string;
  zen_mode: boolean;
  language: string;
}

export const authService = {
  async register(email: string, password: string, name: string): Promise<RegisterResponse> {
    const { data } = await api.post<RegisterResponse>("/auth/register", { email, password, name });
    return data;
  },

  async verifyEmail(email: string, code: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/verify-email", { email, code });
    return data;
  },

  async resendVerification(email: string): Promise<void> {
    await api.post("/auth/resend-verification", { email });
  },

  async getRegistrationStatus(): Promise<RegistrationStatus> {
    const { data } = await api.get<RegistrationStatus>("/auth/registration-status");
    return data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/login", { email, password });
    return data;
  },

  async verify2fa(sessionToken: string, code: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/2fa/verify", {
      session_token: sessionToken,
      code,
    });
    return data;
  },

  async setup2fa(): Promise<TwoFactorSetupOut> {
    const { data } = await api.post<TwoFactorSetupOut>("/auth/2fa/setup");
    return data;
  },

  async enable2fa(sessionToken: string, code: string): Promise<UserOut> {
    const { data } = await api.post<UserOut>("/auth/2fa/enable", {
      session_token: sessionToken,
      code,
    });
    return data;
  },

  async disable2fa(sessionToken: string, code: string): Promise<UserOut> {
    const { data } = await api.post<UserOut>("/auth/2fa/disable", {
      session_token: sessionToken,
      code,
    });
    return data;
  },

  async me(): Promise<UserOut> {
    const { data } = await api.get<UserOut>("/auth/me");
    return data;
  },

  async getSettings(): Promise<UserSettingsOut> {
    const { data } = await api.get<UserSettingsOut>("/me/settings");
    return data;
  },

  async updateSettings(fields: Partial<UserSettingsOut>): Promise<UserSettingsOut> {
    const { data } = await api.patch<UserSettingsOut>("/me/settings", fields);
    return data;
  },

  saveTokens(tokens: TokenResponse) {
    if (tokens.access_token) localStorage.setItem("access_token", tokens.access_token);
    if (tokens.refresh_token) localStorage.setItem("refresh_token", tokens.refresh_token);
  },

  clearTokens() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem("access_token");
  },

  async forgotPassword(email: string): Promise<void> {
    await api.post("/auth/forgot-password", { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await api.post("/auth/reset-password", { token, new_password: newPassword });
  },
};
