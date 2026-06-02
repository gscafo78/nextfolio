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

  async login(email: string, password: string, rememberMe = false): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/login", { email, password, remember_me: rememberMe });
    return data;
  },

  async verify2fa(sessionToken: string, code: string, rememberMe = false): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/2fa/verify", {
      session_token: sessionToken,
      code,
      remember_me: rememberMe,
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

  saveTokens(tokens: TokenResponse, remember = true) {
    // refresh_token always in localStorage so silent refresh survives browser restarts
    if (tokens.access_token) {
      (remember ? localStorage : sessionStorage).setItem("access_token", tokens.access_token);
    }
    if (tokens.refresh_token) {
      localStorage.setItem("refresh_token", tokens.refresh_token);
    }
    localStorage.setItem("nf-remember", remember ? "1" : "0");
  },

  getToken(key: string): string | null {
    return localStorage.getItem(key) ?? sessionStorage.getItem(key);
  },

  clearTokens() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    sessionStorage.removeItem("access_token");
    localStorage.removeItem("nf-remember");
  },

  isAuthenticated(): boolean {
    return !!(localStorage.getItem("access_token") ?? sessionStorage.getItem("access_token"));
  },

  // Decode JWT expiry without a library (no signature verification needed here —
  // the server will reject tampered tokens; we just want the exp claim).
  tokenExpiresInSeconds(token: string): number {
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.exp - Math.floor(Date.now() / 1000);
    } catch {
      return 0;
    }
  },

  // If the access token expires within 60 seconds (or is already expired),
  // refresh it proactively before the first API call fires.
  // This avoids the burst of concurrent 401s on page reload after 24h of inactivity.
  async refreshIfExpired(): Promise<void> {
    const access = localStorage.getItem("access_token") ?? sessionStorage.getItem("access_token");
    const refresh = localStorage.getItem("refresh_token");
    if (!access || !refresh) return;
    if (this.tokenExpiresInSeconds(access) > 60) return;
    try {
      const { data } = await import("axios").then((m) =>
        m.default.post("/api/v1/auth/refresh", { refresh_token: refresh })
      );
      const remember = localStorage.getItem("nf-remember") !== "0";
      if (data.access_token)
        (remember ? localStorage : sessionStorage).setItem("access_token", data.access_token);
      if (data.refresh_token)
        localStorage.setItem("refresh_token", data.refresh_token);
    } catch {
      // Refresh failed — let normal request flow handle it via the interceptor mutex.
    }
  },

  async forgotPassword(email: string): Promise<void> {
    await api.post("/auth/forgot-password", { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await api.post("/auth/reset-password", { token, new_password: newPassword });
  },
};
