import { api } from "./api";

export interface UserAdminOut {
  id: number;
  email: string;
  name: string;
  role: "SUPERADMIN" | "USER";
  is_active: boolean;
  two_factor_enabled: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  name: string;
  role: "SUPERADMIN" | "USER";
}

export interface UserAdminUpdate {
  name?: string;
  role?: "SUPERADMIN" | "USER";
  is_active?: boolean;
  reset_2fa?: boolean;
}

export interface AuditLogOut {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface EmailConfigOut {
  configured: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  emails_from: string;
}

export const adminService = {
  async listUsers(): Promise<UserAdminOut[]> {
    const { data } = await api.get<UserAdminOut[]>("/admin/users");
    return data;
  },

  async createUser(body: UserCreate): Promise<UserAdminOut> {
    const { data } = await api.post<UserAdminOut>("/admin/users", body);
    return data;
  },

  async updateUser(id: number, body: UserAdminUpdate): Promise<UserAdminOut> {
    const { data } = await api.patch<UserAdminOut>(`/admin/users/${id}`, body);
    return data;
  },

  async deleteUser(id: number): Promise<void> {
    await api.delete(`/admin/users/${id}`);
  },

  async getAuditLogs(params?: { action?: string; limit?: number; offset?: number }): Promise<AuditLogOut[]> {
    const { data } = await api.get<AuditLogOut[]>("/admin/audit-logs", { params });
    return data;
  },

  // ── Email ──────────────────────────────────────────────────────────────────
  async getEmailConfig(): Promise<EmailConfigOut> {
    const { data } = await api.get<EmailConfigOut>("/admin/email/config");
    return data;
  },

  async sendTestEmail(to: string): Promise<void> {
    await api.post("/admin/email/test", { to });
  },

  async sendWelcomeEmail(userId: number, tempPassword: string): Promise<void> {
    await api.post(`/admin/email/welcome/${userId}`, { temp_password: tempPassword });
  },

  async sendResetLink(userId: number): Promise<void> {
    await api.post(`/admin/email/reset-link/${userId}`);
  },
};
