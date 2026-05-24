import { api } from "./api";
import type { UserOut } from "./auth";

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
};
