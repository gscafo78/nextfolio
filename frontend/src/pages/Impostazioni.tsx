import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Building2, Coins, Landmark, Briefcase, HelpCircle, ShieldCheck, ShieldOff, Copy, Check } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import QRCode from "react-qr-code";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { accountService, type Account, type AccountType } from "@/services/transactions";
import { authService } from "@/services/auth";
import { useAuth } from "@/hooks/useAuth";

// ── Tipi conto ───────────────────────────────────────────────────────────────

const ACCOUNT_TYPES: { value: AccountType; label: string; icon: React.ElementType; color: string }[] = [
  { value: "BROKERAGE", label: "Broker",      icon: Briefcase, color: "bg-blue-100 text-blue-700" },
  { value: "BANK",      label: "Banca",       icon: Landmark,  color: "bg-green-100 text-green-700" },
  { value: "CRYPTO",    label: "Crypto",      icon: Coins,     color: "bg-purple-100 text-purple-700" },
  { value: "PENSION",   label: "Previdenza",  icon: Building2, color: "bg-orange-100 text-orange-700" },
  { value: "OTHER",     label: "Altro",       icon: HelpCircle,color: "bg-gray-100 text-gray-600" },
];

function AccountTypeBadge({ type }: { type: AccountType }) {
  const t = ACCOUNT_TYPES.find((x) => x.value === type) ?? ACCOUNT_TYPES[4];
  const Icon = t.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${t.color}`}>
      <Icon className="w-3 h-3" />{t.label}
    </span>
  );
}

const accountSchema = z.object({
  name:     z.string().min(1, "Nome obbligatorio"),
  type:     z.enum(["BROKERAGE", "BANK", "CRYPTO", "PENSION", "OTHER"]),
  broker:   z.string().optional(),
  currency: z.string().length(3, "3 caratteri").default("EUR"),
});
type AccountFormData = z.infer<typeof accountSchema>;

function AccountForm({ initial, onSave, onCancel, loading }: {
  initial?: Partial<AccountFormData>;
  onSave: (data: AccountFormData) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<AccountFormData>({
    resolver: zodResolver(accountSchema),
    defaultValues: { type: "BROKERAGE", currency: "EUR", ...initial },
  });
  return (
    <form onSubmit={handleSubmit(onSave)} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Nome conto" placeholder="Es. Fineco principale" error={errors.name?.message} {...register("name")} />
        <Input label="Valuta" placeholder="EUR" error={errors.currency?.message} {...register("currency")} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Tipo</label>
          <select {...register("type")} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500">
            {ACCOUNT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <Input label="Broker / Istituto (opzionale)" placeholder="Es. Fineco, Degiro" {...register("broker")} />
      </div>
      <div className="flex gap-2 justify-end pt-1">
        <Button type="button" variant="secondary" onClick={onCancel}>Annulla</Button>
        <Button type="submit" loading={loading}>Salva</Button>
      </div>
    </form>
  );
}

function AccountRow({ account, onEdit, onDelete }: { account: Account; onEdit: (a: Account) => void; onDelete: (a: Account) => void }) {
  return (
    <div className="flex items-center gap-4 py-4 px-5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900">{account.name}</span>
          <AccountTypeBadge type={account.type} />
          {account.currency !== "EUR" && <span className="text-xs text-gray-400 font-mono">{account.currency}</span>}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {account.broker && <span>{account.broker} · </span>}
          <span>{account.transaction_count} transazioni</span>
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
          title={account.transaction_count > 0 ? "Hai transazioni in questo conto" : "Elimina"}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ── Sezione 2FA ──────────────────────────────────────────────────────────────

function TwoFactorSection() {
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
    onError: () => setError("Codice non valido. Riprova."),
  });

  const disableMutation = useMutation({
    mutationFn: () => authService.disable2fa("", code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); setCode(""); },
    onError: () => setError("Codice non valido. Riprova."),
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
        <h2 className="text-base font-semibold text-gray-900">Autenticazione a due fattori (2FA)</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          Proteggi il tuo account con un codice TOTP (Google Authenticator, Authy, ecc.)
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        {user.two_factor_enabled ? (
          // 2FA attivo — opzione disattivazione
          <div>
            <div className="flex items-center gap-3 mb-4">
              <ShieldCheck className="w-5 h-5 text-green-500" />
              <div>
                <p className="text-sm font-medium text-gray-900">2FA attivo</p>
                <p className="text-xs text-gray-400">Il tuo account è protetto dalla verifica in due passaggi.</p>
              </div>
            </div>
            {!setupData && (
              <div className="border-t border-gray-100 pt-4">
                <p className="text-sm text-gray-600 mb-3">Per disattivare inserisci il codice dalla tua app:</p>
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
                    <ShieldOff className="w-4 h-4 mr-1.5" /> Disattiva
                  </Button>
                </div>
                {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
              </div>
            )}
          </div>
        ) : setupData ? (
          // Step 2: scan QR + inserisci codice
          <div className="space-y-4">
            <p className="text-sm font-medium text-gray-700">
              1. Scansiona il QR con la tua app di autenticazione
            </p>
            <div className="flex justify-center p-4 bg-white border border-gray-200 rounded-xl inline-block">
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
                2. Inserisci il codice generato per attivare
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
                  <ShieldCheck className="w-4 h-4 mr-1.5" /> Attiva 2FA
                </Button>
                <Button variant="secondary" onClick={() => setSetupData(null)}>Annulla</Button>
              </div>
              {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
            </div>
          </div>
        ) : (
          // Step 1: avvia setup
          <div className="flex items-center gap-3">
            <ShieldOff className="w-5 h-5 text-gray-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">2FA non attivo</p>
              <p className="text-xs text-gray-400">Aumenta la sicurezza del tuo account.</p>
            </div>
            <Button onClick={() => setupMutation.mutate()} loading={setupMutation.isPending}>
              Configura 2FA
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}

// ── Sezione preferenze ────────────────────────────────────────────────────────

function PreferenceSection() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ["my-settings"],
    queryFn: authService.getSettings,
  });
  const qc = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: (fields: { theme?: string; display_currency?: string }) =>
      authService.updateSettings(fields),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-settings"] }),
  });

  if (isLoading || !settings) return null;

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">Preferenze</h2>
        <p className="text-sm text-gray-400 mt-0.5">Impostazioni personali dell'interfaccia.</p>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-50">
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900">Valuta di visualizzazione</p>
            <p className="text-xs text-gray-400">Usata per i totali nel portafoglio</p>
          </div>
          <select
            value={settings.display_currency}
            onChange={(e) => updateMutation.mutate({ display_currency: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="EUR">EUR — Euro</option>
            <option value="USD">USD — Dollaro</option>
            <option value="GBP">GBP — Sterlina</option>
            <option value="CHF">CHF — Franco svizzero</option>
          </select>
        </div>
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-medium text-gray-900">Tema</p>
            <p className="text-xs text-gray-400">Aspetto dell'interfaccia</p>
          </div>
          <select
            value={settings.theme}
            onChange={(e) => updateMutation.mutate({ theme: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="light">Chiaro</option>
            <option value="dark">Scuro (presto)</option>
          </select>
        </div>
      </div>
    </section>
  );
}

// ── Pagina principale ────────────────────────────────────────────────────────

export function Impostazioni() {
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
    if (confirm(`Eliminare il conto "${acc.name}"? L'operazione è irreversibile.`)) {
      deleteMutation.mutate(acc.id);
    }
  };

  return (
    <>
      <TopBar title="Impostazioni" />
      <main className="flex-1 p-6 max-w-3xl space-y-8">

        {/* Preferenze personali */}
        <PreferenceSection />

        {/* 2FA */}
        <TwoFactorSection />

        {/* Conti di investimento */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Conti di investimento</h2>
              <p className="text-sm text-gray-400 mt-0.5">
                Gestisci i tuoi broker e conti. Ogni transazione è associata a un conto.
              </p>
            </div>
            {!showCreate && (
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="w-4 h-4 mr-1.5" /> Nuovo conto
              </Button>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {showCreate && (
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
                <p className="text-sm font-medium text-gray-700 mb-3">Nuovo conto</p>
                <AccountForm
                  onSave={(data) => createMutation.mutate(data)}
                  onCancel={() => setShowCreate(false)}
                  loading={createMutation.isPending}
                />
              </div>
            )}
            {isLoading ? (
              <div className="py-12 text-center text-gray-400 text-sm">Caricamento...</div>
            ) : accounts.length === 0 && !showCreate ? (
              <div className="py-12 text-center">
                <p className="text-gray-400 text-sm mb-3">Nessun conto ancora.</p>
                <Button onClick={() => setShowCreate(true)}>
                  <Plus className="w-4 h-4 mr-1.5" /> Crea il primo conto
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {accounts.map((acc) => (
                  <div key={acc.id}>
                    {editing?.id === acc.id ? (
                      <div className="px-5 py-4 bg-blue-50 border-l-2 border-brand-500">
                        <p className="text-sm font-medium text-gray-700 mb-3">Modifica conto</p>
                        <AccountForm
                          initial={{ name: acc.name, type: acc.type, broker: acc.broker ?? undefined, currency: acc.currency }}
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
            {ACCOUNT_TYPES.map((t) => {
              const Icon = t.icon;
              return (
                <span key={t.value} className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${t.color}`}>
                  <Icon className="w-3 h-3" />{t.label}
                </span>
              );
            })}
          </div>
        </section>
      </main>
    </>
  );
}
