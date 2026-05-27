import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Building2, Coins, Landmark, Briefcase, HelpCircle, ShieldCheck, ShieldOff, Copy, Check, CheckCircle2, XCircle, Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import QRCode from "react-qr-code";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AccountFavicon } from "@/components/AccountFavicon";
import { accountService, type Account, type AccountType } from "@/services/transactions";
import { authService } from "@/services/auth";
import { adminService } from "@/services/admin";
import { useAuth } from "@/hooks/useAuth";
import { applyTheme, type ThemeMode } from "@/context/ThemeContext";
import i18n from "@/i18n";

// ── Tipi conto ───────────────────────────────────────────────────────────────

const ACCOUNT_TYPE_ICONS: Record<AccountType, { icon: React.ElementType; color: string }> = {
  BROKERAGE: { icon: Briefcase, color: "bg-blue-100 text-blue-700" },
  BANK:      { icon: Landmark,  color: "bg-green-100 text-green-700" },
  CRYPTO:    { icon: Coins,     color: "bg-purple-100 text-purple-700" },
  PENSION:   { icon: Building2, color: "bg-orange-100 text-orange-700" },
  OTHER:     { icon: HelpCircle,color: "bg-gray-100 text-gray-600" },
};

function AccountTypeBadge({ type }: { type: AccountType }) {
  const { t } = useTranslation();
  const meta = ACCOUNT_TYPE_ICONS[type] ?? ACCOUNT_TYPE_ICONS.OTHER;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${meta.color}`}>
      <Icon className="w-3 h-3" />{t(`settings.accountTypes.${type}`)}
    </span>
  );
}

const accountSchema = z.object({
  name:     z.string().min(1, "Nome obbligatorio"),
  type:     z.enum(["BROKERAGE", "BANK", "CRYPTO", "PENSION", "OTHER"]),
  broker:   z.string().optional(),
  url:      z.string().url("URL non valido").optional().or(z.literal("")),
  currency: z.string().length(3, "3 caratteri").default("EUR"),
});
type AccountFormData = z.infer<typeof accountSchema>;

const ACCOUNT_TYPES_LIST = ["BROKERAGE", "BANK", "CRYPTO", "PENSION", "OTHER"] as const;

function AccountForm({ initial, onSave, onCancel, loading }: {
  initial?: Partial<AccountFormData>;
  onSave: (data: AccountFormData) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<AccountFormData>({
    resolver: zodResolver(accountSchema),
    defaultValues: { type: "BROKERAGE", currency: "EUR", ...initial },
  });
  return (
    <form onSubmit={handleSubmit(onSave)} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Input
          label={t("settings.accountName")}
          placeholder={t("settings.accountNamePlaceholder")}
          error={errors.name?.message}
          {...register("name")}
        />
        <Input
          label={t("settings.accountCurrency")}
          placeholder="EUR"
          error={errors.currency?.message}
          {...register("currency")}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">{t("settings.accountType")}</label>
          <select {...register("type")} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500">
            {ACCOUNT_TYPES_LIST.map((type) => (
              <option key={type} value={type}>{t(`settings.accountTypes.${type}`)}</option>
            ))}
          </select>
        </div>
        <Input
          label={t("settings.accountBroker")}
          placeholder={t("settings.accountBrokerPlaceholder")}
          {...register("broker")}
        />
      </div>
      <Input
        label={t("settings.accountUrl")}
        placeholder={t("settings.accountUrlPlaceholder")}
        error={errors.url?.message}
        {...register("url")}
      />
      <div className="flex gap-2 justify-end pt-1">
        <Button type="button" variant="secondary" onClick={onCancel}>{t("common.cancel")}</Button>
        <Button type="submit" loading={loading}>{t("common.save")}</Button>
      </div>
    </form>
  );
}

function AccountRow({ account, onEdit, onDelete }: { account: Account; onEdit: (a: Account) => void; onDelete: (a: Account) => void }) {
  const { t } = useTranslation();
  const nameNode = account.url ? (
    <a
      href={account.url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-gray-900 hover:text-brand-600 hover:underline"
    >
      {account.name}
    </a>
  ) : (
    <span className="font-medium text-gray-900">{account.name}</span>
  );

  return (
    <div className="flex items-center gap-4 py-4 px-5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <AccountFavicon url={account.url} />
          {nameNode}
          <AccountTypeBadge type={account.type} />
          {account.currency !== "EUR" && <span className="text-xs text-gray-400 font-mono">{account.currency}</span>}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {account.broker && <span>{account.broker} · </span>}
          <span>{account.transaction_count} {t("settings.transactions")}</span>
        </div>
      </div>
      <div className="flex gap-1">
        <button onClick={() => onEdit(account)} className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
          <Pencil className="w-4 h-4" />
        </button>
        <button
          onClick={() => onDelete(account)}
          disabled={account.transaction_count > 0}
          className={`p-1.5 rounded-lg transition-colors ${account.transaction_count > 0 ? "text-gray-200 cursor-not-allowed" : "text-gray-400 hover:text-red-500 hover:bg-red-50"}`}
          title={account.transaction_count > 0 ? t("settings.hasTransactions") : t("common.delete")}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ── Sezione 2FA ──────────────────────────────────────────────────────────────

function TwoFactorSection() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [setupData, setSetupData] = useState<{ secret: string; uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const setupMutation = useMutation({
    mutationFn: authService.setup2fa,
    onSuccess: (data) => { setSetupData(data); setCode(""); setError(""); },
  });

  const enableMutation = useMutation({
    mutationFn: () => authService.enable2fa("", code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); setSetupData(null); setCode(""); },
    onError: () => setError(t("settings.invalidCode")),
  });

  const disableMutation = useMutation({
    mutationFn: () => authService.disable2fa("", code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); setCode(""); },
    onError: () => setError(t("settings.invalidCode")),
  });

  const copySecret = () => {
    if (setupData) {
      navigator.clipboard.writeText(setupData.secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!user) return null;

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">{t("settings.twoFactor")}</h2>
        <p className="text-sm text-gray-400 mt-0.5">{t("settings.twoFactorDesc")}</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        {user.two_factor_enabled ? (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <ShieldCheck className="w-5 h-5 text-green-500" />
              <div>
                <p className="text-sm font-medium text-gray-900">{t("settings.twoFactorActive")}</p>
                <p className="text-xs text-gray-400">{t("settings.twoFactorActiveDesc")}</p>
              </div>
            </div>
            {!setupData && (
              <div className="border-t border-gray-100 pt-4">
                <p className="text-sm text-gray-600 mb-3">{t("settings.twoFactorDisablePrompt")}</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    value={code}
                    onChange={(e) => { setCode(e.target.value); setError(""); }}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-32 outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  <Button
                    variant="secondary"
                    onClick={() => disableMutation.mutate()}
                    loading={disableMutation.isPending}
                  >
                    <ShieldOff className="w-4 h-4 mr-1.5" /> {t("settings.twoFactorDisable")}
                  </Button>
                </div>
                {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
              </div>
            )}
          </div>
        ) : setupData ? (
          <div className="space-y-4">
            <p className="text-sm font-medium text-gray-700">
              {t("settings.twoFactorSetupStep1")}
            </p>
            <div className="flex justify-center p-4 bg-white border border-gray-200 rounded-xl">
              <QRCode value={setupData.uri} size={180} />
            </div>
            <div className="flex items-center gap-2">
              <code className="text-xs bg-gray-100 px-3 py-1.5 rounded font-mono flex-1 truncate">
                {setupData.secret}
              </code>
              <button onClick={copySecret} className="p-1.5 text-gray-400 hover:text-gray-700 rounded transition-colors">
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">
                {t("settings.twoFactorSetupStep2")}
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(e) => { setCode(e.target.value); setError(""); }}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-32 outline-none focus:ring-2 focus:ring-brand-500"
                />
                <Button onClick={() => enableMutation.mutate()} loading={enableMutation.isPending}>
                  <ShieldCheck className="w-4 h-4 mr-1.5" /> {t("settings.twoFactorActivate")}
                </Button>
                <Button variant="secondary" onClick={() => setSetupData(null)}>{t("common.cancel")}</Button>
              </div>
              {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <ShieldOff className="w-5 h-5 text-gray-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">{t("settings.twoFactorInactive")}</p>
              <p className="text-xs text-gray-400">{t("settings.twoFactorInactiveDesc")}</p>
            </div>
            <Button onClick={() => setupMutation.mutate()} loading={setupMutation.isPending}>
              {t("settings.twoFactorSetup")}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}

// ── Sezione preferenze ────────────────────────────────────────────────────────

const LANGUAGES = [
  { code: "it", label: "IT", native: "Italiano" },
  { code: "en", label: "EN", native: "English" },
  { code: "fr", label: "FR", native: "Français" },
  { code: "de", label: "DE", native: "Deutsch" },
];

function PreferenceSection() {
  const { t } = useTranslation();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["my-settings"],
    queryFn: authService.getSettings,
  });
  const qc = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: (fields: { theme?: string; display_currency?: string; zen_mode?: boolean; language?: string }) =>
      authService.updateSettings(fields),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-settings"] }),
  });

  if (isLoading || !settings) return null;

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">{t("settings.preferences")}</h2>
        <p className="text-sm text-gray-400 mt-0.5">{t("settings.preferencesDesc")}</p>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-50">
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900">{t("settings.displayCurrency")}</p>
            <p className="text-xs text-gray-400">{t("settings.displayCurrencyDesc")}</p>
          </div>
          <select
            value={settings.display_currency}
            onChange={(e) => updateMutation.mutate({ display_currency: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="EUR">EUR — Euro</option>
            <option value="USD">USD — Dollar</option>
            <option value="GBP">GBP — Pound</option>
            <option value="CHF">CHF — Franc</option>
          </select>
        </div>
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900">{t("settings.theme")}</p>
            <p className="text-xs text-gray-400">{t("settings.themeDesc")}</p>
          </div>
          <select
            value={settings.theme}
            onChange={(e) => {
              const theme = e.target.value as ThemeMode;
              applyTheme(theme);
              updateMutation.mutate({ theme });
            }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:border-slate-600 dark:text-slate-100"
          >
            <option value="light">{t("settings.themeLight")}</option>
            <option value="dark">{t("settings.themeDark")}</option>
            <option value="system">{t("settings.themeSystem")}</option>
          </select>
        </div>
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{t("settings.zenMode")}</p>
            <p className="text-xs text-gray-400 dark:text-slate-500">{t("settings.zenModeDesc")}</p>
          </div>
          <button
            role="switch"
            aria-checked={settings.zen_mode}
            onClick={() => updateMutation.mutate({ zen_mode: !settings.zen_mode })}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 ${
              settings.zen_mode ? "bg-brand-600" : "bg-gray-200 dark:bg-slate-600"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                settings.zen_mode ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{t("settings.language")}</p>
            <p className="text-xs text-gray-400 dark:text-slate-500">{t("settings.languageDesc")}</p>
          </div>
          <select
            value={settings.language ?? "it"}
            onChange={(e) => {
              i18n.changeLanguage(e.target.value);
              updateMutation.mutate({ language: e.target.value });
            }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:border-slate-600 dark:text-slate-100"
          >
            {LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>{lang.label} — {lang.native}</option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}

// ── Sezione Email ─────────────────────────────────────────────────────────────

function EmailSection() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [testTo, setTestTo] = useState(user?.email ?? "");
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  const { data: cfg, isLoading } = useQuery({
    queryKey: ["email-config"],
    queryFn: adminService.getEmailConfig,
  });

  const handleTest = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      await adminService.sendTestEmail(testTo);
      setTestResult("ok");
    } catch {
      setTestResult("error");
    } finally {
      setTestLoading(false);
    }
  };

  if (isLoading || !cfg) return null;

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">{t("settings.email")}</h2>
        <p className="text-sm text-gray-400 mt-0.5">{t("settings.emailDesc")}</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-50">
        <div className="flex items-center gap-3 px-5 py-4">
          {cfg.configured ? (
            <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
          ) : (
            <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900">
              {cfg.configured ? t("settings.smtpConfigured") : t("settings.smtpNotConfigured")}
            </p>
            <p className="text-xs text-gray-400 truncate">
              {cfg.configured
                ? `${cfg.smtp_host}:${cfg.smtp_port} · ${t("settings.smtpFrom")}: ${cfg.emails_from}`
                : t("settings.smtpNotConfiguredHint")}
            </p>
          </div>
        </div>

        {cfg.configured && (
          <div className="px-5 py-4 grid grid-cols-2 gap-x-6 gap-y-2">
            {[
              [t("settings.smtpHost"), cfg.smtp_host],
              [t("settings.smtpPort"), String(cfg.smtp_port)],
              [t("settings.smtpUser"), cfg.smtp_user],
              [t("settings.smtpFrom"), cfg.emails_from],
            ].map(([k, v]) => (
              <div key={k}>
                <p className="text-xs text-gray-400">{k}</p>
                <p className="text-sm text-gray-700 font-mono truncate">{v}</p>
              </div>
            ))}
          </div>
        )}

        {cfg.configured && (
          <div className="px-5 py-4">
            <p className="text-sm font-medium text-gray-700 mb-2">{t("settings.testEmail")}</p>
            <div className="flex gap-2 items-start">
              <input
                type="email"
                value={testTo}
                onChange={(e) => { setTestTo(e.target.value); setTestResult(null); }}
                placeholder="destinatario@esempio.com"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
              />
              <Button onClick={handleTest} loading={testLoading} size="sm">
                <Send className="w-4 h-4 mr-1.5" /> {t("settings.testEmailSend")}
              </Button>
            </div>
            {testResult === "ok" && (
              <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> {t("settings.testEmailOk")}
              </p>
            )}
            {testResult === "error" && (
              <p className="text-xs text-red-600 mt-2 flex items-center gap-1">
                <XCircle className="w-3.5 h-3.5" /> {t("settings.testEmailError")}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Pagina principale ────────────────────────────────────────────────────────

export function Impostazioni() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPERADMIN";
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const qc = useQueryClient();

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["accounts"] });

  const createMutation = useMutation({
    mutationFn: accountService.create,
    onSuccess: () => { invalidate(); setShowCreate(false); },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AccountFormData }) => accountService.update(id, data),
    onSuccess: () => { invalidate(); setEditing(null); },
  });
  const deleteMutation = useMutation({
    mutationFn: accountService.delete,
    onSuccess: invalidate,
  });

  const handleDelete = (acc: Account) => {
    if (acc.transaction_count > 0) return;
    if (confirm(t("settings.deleteAccountConfirm", { name: acc.name }))) {
      deleteMutation.mutate(acc.id);
    }
  };

  return (
    <>
      <TopBar title={t("settings.title")} />
      <main className="flex-1 p-4 md:p-6 max-w-3xl space-y-6 md:space-y-8">

        <PreferenceSection />

        <TwoFactorSection />

        {isSuperAdmin && <EmailSection />}

        <section>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">{t("settings.accounts")}</h2>
              <p className="text-sm text-gray-400 mt-0.5">{t("settings.accountsDesc")}</p>
            </div>
            {!showCreate && (
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="w-4 h-4 mr-1.5" /> {t("settings.newAccount")}
              </Button>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {showCreate && (
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
                <p className="text-sm font-medium text-gray-700 mb-3">{t("settings.newAccountTitle")}</p>
                <AccountForm
                  onSave={(data) => createMutation.mutate(data)}
                  onCancel={() => setShowCreate(false)}
                  loading={createMutation.isPending}
                />
              </div>
            )}
            {isLoading ? (
              <div className="py-12 text-center text-gray-400 text-sm">{t("common.loading")}</div>
            ) : accounts.length === 0 && !showCreate ? (
              <div className="py-12 text-center">
                <p className="text-gray-400 text-sm mb-3">{t("settings.noAccounts")}</p>
                <Button onClick={() => setShowCreate(true)}>
                  <Plus className="w-4 h-4 mr-1.5" /> {t("settings.createFirstAccount")}
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {accounts.map((acc) => (
                  <div key={acc.id}>
                    {editing?.id === acc.id ? (
                      <div className="px-5 py-4 bg-blue-50 border-l-2 border-brand-500">
                        <p className="text-sm font-medium text-gray-700 mb-3">{t("settings.editAccountTitle")}</p>
                        <AccountForm
                          initial={{ name: acc.name, type: acc.type, broker: acc.broker ?? undefined, url: acc.url ?? undefined, currency: acc.currency }}
                          onSave={(data) => updateMutation.mutate({ id: acc.id, data })}
                          onCancel={() => setEditing(null)}
                          loading={updateMutation.isPending}
                        />
                      </div>
                    ) : (
                      <AccountRow account={acc} onEdit={setEditing} onDelete={handleDelete} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {(["BROKERAGE", "BANK", "CRYPTO", "PENSION", "OTHER"] as AccountType[]).map((type) => {
              const meta = ACCOUNT_TYPE_ICONS[type];
              const Icon = meta.icon;
              return (
                <span key={type} className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${meta.color}`}>
                  <Icon className="w-3 h-3" />{t(`settings.accountTypes.${type}`)}
                </span>
              );
            })}
          </div>
        </section>
      </main>
    </>
  );
}
