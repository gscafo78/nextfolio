import { api } from "./api";

export type PromptMode = "analysis" | "portfolio";
export type PromptLanguage = "it" | "en" | "fr" | "de";

export interface PromptParams {
  mode: PromptMode;
  lang: PromptLanguage;
  include_values: boolean;
  account_id?: number;
  asset_type?: string;
}

export interface McpToken {
  id: number;
  name: string;
  token_prefix: string;
  can_read_values: boolean;
  can_write: boolean;
  can_delete: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface McpTokenCreated extends McpToken {
  token: string;
}

export interface McpInfo {
  enabled: boolean;
  path: string;
  tokens: McpToken[];
}

export const aiService = {
  async getPrompt(params: PromptParams): Promise<string> {
    const { data } = await api.get<{ prompt: string }>("/ai/prompt", { params });
    return data.prompt;
  },

  async getMcpInfo(): Promise<McpInfo> {
    const { data } = await api.get<McpInfo>("/ai/mcp-tokens");
    return data;
  },

  async createMcpToken(body: { name: string; can_read_values: boolean; can_write: boolean; can_delete: boolean }): Promise<McpTokenCreated> {
    const { data } = await api.post<McpTokenCreated>("/ai/mcp-tokens", body);
    return data;
  },

  async revokeMcpToken(id: number): Promise<void> {
    await api.delete(`/ai/mcp-tokens/${id}`);
  },
};
