import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Copy, Check, Plug, Trash2, Plus, KeyRound, Eye, EyeOff, AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/Button";
import { useZenMode } from "@/context/ThemeContext";
import { accountService } from "@/services/transactions";
import { aiService, type McpTokenCreated, type PromptLanguage, type PromptMode } from "@/services/ai";

const ASSET_TYPES = ["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"] as const;
const LANGUAGES: PromptLanguage[] = ["it", "en", "fr", "de"];

const card = "bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5";
const selectCls =
  "w-full text-sm border border-gray-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500";
const labelCls = "block text-xs font-medium text-gray-500 dark:text-slate-400 mb-1";

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback per contesti non sicuri (http): selezione + execCommand
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };
  return { copied, copy };
}

function CopyButton({ id, text, copied, copy, label }: {
  id: string; text: string; copied: string | null; copy: (k: string, t: string) => void; label?: string;
}) {
  const { t } = useTranslation();
  const done = copied === id;
  return (
    <Button type="button" variant="secondary" size="sm" onClick={() => copy(id, text)} disabled={!text}>
      {done ? <Check className="w-4 h-4 mr-1.5 text-green-500" /> : <Copy className="w-4 h-4 mr-1.5" />}
      {done ? t("ai.copied") : label ?? t("ai.copy")}
    </Button>
  );
}

// ── Prompt per chatbot ───────────────────────────────────────────────────────

function PromptGenerator() {
  const { t, i18n } = useTranslation();
  const zenMode = useZenMode();
  const { copied, copy } = useCopy();

  const uiLang = (i18n.language?.slice(0, 2) ?? "it") as PromptLanguage;
  const [mode, setMode] = useState<PromptMode>("analysis");
  const [lang, setLang] = useState<PromptLanguage>(LANGUAGES.includes(uiLang) ? uiLang : "it");
  const [includeValues, setIncludeValues] = useState(!zenMode);
  const [accountId, setAccountId] = useState<string>("");
  const [assetType, setAssetType] = useState<string>("");

  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });

  const gen = useMutation({
    mutationFn: () =>
      aiService.getPrompt({
        mode,
        lang,
        include_values: includeValues,
        account_id: accountId ? Number(accountId) : undefined,
        asset_type: assetType || undefined,
      }),
  });

  return (
    <section className={card}>
      <div className="flex items-start gap-3 mb-4">
        <Sparkles className="w-5 h-5 text-brand-500 mt-0.5 flex-shrink-0" />
        <div>
          <h2 className="text-base font-bold text-gray-900 dark:text-slate-100">{t("ai.promptTitle")}</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">{t("ai.promptDesc")}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className={labelCls}>{t("ai.mode")}</label>
          <select className={selectCls} value={mode} onChange={(e) => setMode(e.target.value as PromptMode)}>
            <option value="analysis">{t("ai.modeAnalysis")}</option>
            <option value="portfolio">{t("ai.modePortfolio")}</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>{t("ai.language")}</label>
          <select className={selectCls} value={lang} onChange={(e) => setLang(e.target.value as PromptLanguage)}>
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>{t(`ai.languages.${l}`)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>{t("ai.account")}</label>
          <select className={selectCls} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="">{t("ai.allAccounts")}</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>{t("ai.assetType")}</label>
          <select className={selectCls} value={assetType} onChange={(e) => setAssetType(e.target.value)}>
            <option value="">{t("ai.allAssetTypes")}</option>
            {ASSET_TYPES.map((at) => (
              <option key={at} value={at}>{t(`ai.assetTypes.${at}`)}</option>
            ))}
          </select>
        </div>
      </div>

      <label className="flex items-center gap-2 mt-4 text-sm text-gray-700 dark:text-slate-300 cursor-pointer select-none">
        <input
          type="checkbox"
          className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
          checked={includeValues}
          onChange={(e) => setIncludeValues(e.target.checked)}
        />
        {includeValues ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
        {t("ai.includeValues")}
      </label>
      <p className="text-xs text-gray-400 dark:text-slate-500 mt-1 ml-6">{t("ai.includeValuesHint")}</p>

      <div className="flex flex-wrap gap-2 mt-4">
        <Button type="button" onClick={() => gen.mutate()} loading={gen.isPending}>
          <Sparkles className="w-4 h-4 mr-1.5" />
          {t("ai.generate")}
        </Button>
        {gen.data && <CopyButton id="prompt" text={gen.data} copied={copied} copy={copy} />}
      </div>

      {gen.isError && <p className="text-sm text-red-600 mt-3">{t("ai.generateError")}</p>}

      {gen.data && (
        <>
          <textarea
            readOnly
            value={gen.data}
            className="mt-4 w-full h-80 font-mono text-xs leading-relaxed border border-gray-200 dark:border-slate-700 rounded-lg p-3 bg-gray-50 dark:bg-slate-800 text-gray-800 dark:text-slate-200 focus:outline-none"
            onFocus={(e) => e.currentTarget.select()}
          />
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
            {t("ai.promptStats", { chars: gen.data.length.toLocaleString(), tokens: Math.round(gen.data.length / 4).toLocaleString() })}
          </p>
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 flex items-start gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            {t("ai.privacyWarning")}
          </p>
        </>
      )}
    </section>
  );
}

// ── Server MCP ───────────────────────────────────────────────────────────────

function McpSection() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { copied, copy } = useCopy();
  const [name, setName] = useState("");
  const [canReadValues, setCanReadValues] = useState(false);
  const [created, setCreated] = useState<McpTokenCreated | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<number | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["mcp-tokens"], queryFn: aiService.getMcpInfo });

  const create = useMutation({
    mutationFn: () => aiService.createMcpToken({ name: name.trim(), can_read_values: canReadValues }),
    onSuccess: (tok) => {
      setCreated(tok);
      setName("");
      setCanReadValues(false);
      qc.invalidateQueries({ queryKey: ["mcp-tokens"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => aiService.revokeMcpToken(id),
    onSuccess: () => {
      setConfirmRevoke(null);
      qc.invalidateQueries({ queryKey: ["mcp-tokens"] });
    },
  });

  const url = `${window.location.origin}${data?.path ?? "/api/mcp"}`;
  const token = created?.token ?? "<TOKEN>";
  const claudeCode = `claude mcp add --transport http nextfolio ${url} --header "Authorization: Bearer ${token}"`;
  const jsonConfig = JSON.stringify(
    { mcpServers: { nextfolio: { type: "http", url, headers: { Authorization: `Bearer ${token}` } } } },
    null,
    2,
  );
  const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString(i18n.language) : t("ai.never"));

  return (
    <section className={card}>
      <div className="flex items-start gap-3 mb-4">
        <Plug className="w-5 h-5 text-brand-500 mt-0.5 flex-shrink-0" />
        <div>
          <h2 className="text-base font-bold text-gray-900 dark:text-slate-100">{t("ai.mcpTitle")}</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">{t("ai.mcpDesc")}</p>
        </div>
      </div>

      {data && !data.enabled && (
        <p className="text-sm text-amber-700 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-300 rounded-lg p-3 mb-4">
          {t("ai.mcpDisabled")}
        </p>
      )}

      <div className="mb-4">
        <label className={labelCls}>{t("ai.endpoint")}</label>
        <div className="flex gap-2 items-center">
          <code className="flex-1 min-w-0 truncate text-xs bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg px-3 py-2 text-gray-800 dark:text-slate-200">
            {url}
          </code>
          <CopyButton id="url" text={url} copied={copied} copy={copy} />
        </div>
      </div>

      {/* Creazione token */}
      <form
        className="flex flex-col sm:flex-row sm:items-end gap-3 mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate();
        }}
      >
        <div className="flex-1">
          <label className={labelCls}>{t("ai.tokenName")}</label>
          <input
            type="text"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("ai.tokenNamePlaceholder")}
            className={selectCls}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300 cursor-pointer select-none sm:pb-2">
          <input
            type="checkbox"
            className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
            checked={canReadValues}
            onChange={(e) => setCanReadValues(e.target.checked)}
          />
          {t("ai.canReadValues")}
        </label>
        <Button type="submit" disabled={!name.trim()} loading={create.isPending}>
          <Plus className="w-4 h-4 mr-1.5" />
          {t("ai.createToken")}
        </Button>
      </form>
      {create.isError && <p className="text-sm text-red-600 mb-3">{t("ai.createError")}</p>}

      {/* Token appena creato: mostrato una sola volta */}
      {created && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-4 mb-4">
          <p className="text-sm font-medium text-green-800 dark:text-green-300 flex items-center gap-1.5">
            <KeyRound className="w-4 h-4" />
            {t("ai.tokenCreated")}
          </p>
          <div className="flex gap-2 items-center mt-2">
            <code className="flex-1 min-w-0 break-all text-xs bg-white dark:bg-slate-900 border border-green-200 dark:border-green-800 rounded-lg px-3 py-2">
              {created.token}
            </code>
            <CopyButton id="token" text={created.token} copied={copied} copy={copy} />
          </div>
          <div className="mt-2 text-right">
            <button type="button" className="text-xs text-green-700 dark:text-green-400 underline" onClick={() => setCreated(null)}>
              {t("ai.tokenSaved")}
            </button>
          </div>
        </div>
      )}

      {/* Elenco token */}
      {isLoading ? (
        <div className="h-16 bg-gray-50 dark:bg-slate-800 rounded-xl animate-pulse" />
      ) : data && data.tokens.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 dark:text-slate-400 border-b border-gray-100 dark:border-slate-700">
                <th className="py-2 pr-3 font-medium">{t("ai.tokenName")}</th>
                <th className="py-2 pr-3 font-medium">{t("ai.prefix")}</th>
                <th className="py-2 pr-3 font-medium">{t("ai.permissions")}</th>
                <th className="py-2 pr-3 font-medium">{t("ai.lastUsed")}</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {data.tokens.map((tok) => (
                <tr key={tok.id} className="border-b border-gray-50 dark:border-slate-800 last:border-0">
                  <td className="py-2 pr-3 text-gray-900 dark:text-slate-100">{tok.name}</td>
                  <td className="py-2 pr-3"><code className="text-xs text-gray-500">{tok.token_prefix}…</code></td>
                  <td className="py-2 pr-3 text-xs text-gray-600 dark:text-slate-300">
                    {tok.can_read_values ? t("ai.permValues") : t("ai.permPercent")}
                  </td>
                  <td className="py-2 pr-3 text-xs text-gray-500 dark:text-slate-400 whitespace-nowrap">{fmtDate(tok.last_used_at)}</td>
                  <td className="py-2 text-right whitespace-nowrap">
                    {confirmRevoke === tok.id ? (
                      <span className="inline-flex gap-1">
                        <Button size="sm" className="!bg-red-600 hover:!bg-red-700" onClick={() => revoke.mutate(tok.id)} loading={revoke.isPending}>
                          {t("ai.confirmRevoke")}
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setConfirmRevoke(null)}>{t("common.cancel")}</Button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        title={t("ai.revoke")}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                        onClick={() => setConfirmRevoke(tok.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-gray-400 dark:text-slate-500">{t("ai.noTokens")}</p>
      )}

      {/* Istruzioni di configurazione */}
      <div className="mt-6 space-y-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">{t("ai.setupTitle")}</h3>
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className={labelCls}>Claude Code</span>
            <CopyButton id="cc" text={claudeCode} copied={copied} copy={copy} />
          </div>
          <pre className="text-xs bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg p-3 overflow-x-auto text-gray-800 dark:text-slate-200">{claudeCode}</pre>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className={labelCls}>{t("ai.jsonConfig")}</span>
            <CopyButton id="json" text={jsonConfig} copied={copied} copy={copy} />
          </div>
          <pre className="text-xs bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg p-3 overflow-x-auto text-gray-800 dark:text-slate-200">{jsonConfig}</pre>
        </div>
        <p className="text-xs text-gray-400 dark:text-slate-500">{t("ai.setupHint")}</p>
      </div>
    </section>
  );
}

export function AI() {
  const { t } = useTranslation();
  return (
    <>
      <TopBar title={t("nav.ai")} />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-5 max-w-4xl mx-auto w-full">
        <PromptGenerator />
        <McpSection />
      </main>
    </>
  );
}
