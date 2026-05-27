import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus, Pencil, Trash2, ShieldCheck, ShieldOff, X, ChevronDown, ClipboardList, Mail, KeyRound, Send } from "lucide-react";
import { adminService, type UserAdminOut, type UserAdminUpdate } from "@/services/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TopBar } from "@/components/layout/TopBar";

const createSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(8, "Minimo 8 caratteri"),
  name: z.string().min(1, "Campo obbligatorio"),
  role: z.enum(["USER", "SUPERADMIN"]),
});
type CreateData = z.infer<typeof createSchema>;

function Badge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
      }`}
    >
      {active ? "Attivo" : "Disabilitato"}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        role === "SUPERADMIN" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-600"
      }`}
    >
      {role === "SUPERADMIN" ? "Superadmin" : "Utente"}
    </span>
  );
}

interface EditModalProps {
  user: UserAdminOut;
  onClose: () => void;
}

function EditModal({ user, onClose }: EditModalProps) {
  const qc = useQueryClient();
  const [role, setRole] = useState<"USER" | "SUPERADMIN">(user.role);
  const [isActive, setIsActive] = useState(user.is_active);

  const mutation = useMutation({
    mutationFn: (body: UserAdminUpdate) => adminService.updateUser(user.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      onClose();
    },
  });

  const reset2fa = useMutation({
    mutationFn: () => adminService.updateUser(user.id, { reset_2fa: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Modifica utente</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-sm text-gray-500">Email</p>
            <p className="text-sm font-medium text-gray-900">{user.email}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ruolo</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "USER" | "SUPERADMIN")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="USER">Utente</option>
              <option value="SUPERADMIN">Superadmin</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <input
              id="active-toggle"
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
            <label htmlFor="active-toggle" className="text-sm font-medium text-gray-700">
              Account attivo
            </label>
          </div>

          {user.two_factor_enabled && (
            <div className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-amber-800">2FA abilitato</p>
                <p className="text-xs text-amber-600">Reimposta il 2FA per questo utente</p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                loading={reset2fa.isPending}
                onClick={() => reset2fa.mutate()}
              >
                <ShieldOff className="w-4 h-4 mr-1" />
                Reset
              </Button>
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            Annulla
          </Button>
          <Button
            loading={mutation.isPending}
            onClick={() => mutation.mutate({ role, is_active: isActive })}
          >
            Salva
          </Button>
        </div>
        {mutation.isError && (
          <p className="mt-2 text-sm text-red-600 text-center">Errore durante il salvataggio.</p>
        )}
      </div>
    </div>
  );
}

interface CreateModalProps {
  onClose: () => void;
}

function CreateModal({ onClose }: CreateModalProps) {
  const qc = useQueryClient();
  const form = useForm<CreateData>({ resolver: zodResolver(createSchema), defaultValues: { role: "USER" } });

  const mutation = useMutation({
    mutationFn: adminService.createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Crea utente</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <Input
            label="Nome"
            error={form.formState.errors.name?.message}
            {...form.register("name")}
          />
          <Input
            label="Email"
            type="email"
            error={form.formState.errors.email?.message}
            {...form.register("email")}
          />
          <Input
            label="Password"
            type="password"
            error={form.formState.errors.password?.message}
            {...form.register("password")}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ruolo</label>
            <select
              {...form.register("role")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="USER">Utente</option>
              <option value="SUPERADMIN">Superadmin</option>
            </select>
          </div>

          {mutation.isError && (
            <p className="text-sm text-red-600 text-center">Errore durante la creazione.</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Annulla
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              Crea
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  DELETE_TRANSACTION: { label: "Elimina transazione", color: "text-red-600 bg-red-50 border-red-200" },
  DELETE_ACCOUNT:     { label: "Elimina conto",       color: "text-red-600 bg-red-50 border-red-200" },
  DELETE_USER:        { label: "Elimina utente",       color: "text-red-700 bg-red-100 border-red-300" },
  CREATE_USER:        { label: "Crea utente",          color: "text-green-700 bg-green-50 border-green-200" },
  UPDATE_USER:        { label: "Modifica utente",      color: "text-amber-700 bg-amber-50 border-amber-200" },
  BULK_ENRICH_ASSETS: { label: "Enrichment asset",    color: "text-blue-600 bg-blue-50 border-blue-200" },
};

function ActionBadge({ action }: { action: string }) {
  const meta = ACTION_LABELS[action] ?? { label: action, color: "text-gray-600 bg-gray-100 border-gray-200" };
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${meta.color}`}>
      {meta.label}
    </span>
  );
}

function AuditLogSection() {
  const [open, setOpen] = useState(false);
  const [filterAction, setFilterAction] = useState("");

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["audit-logs", filterAction],
    queryFn: () => adminService.getAuditLogs({ action: filterAction || undefined, limit: 200 }),
    enabled: open,
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mt-6">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 text-sm font-semibold text-gray-800 hover:bg-gray-50 transition-colors"
      >
        <ClipboardList className="w-4 h-4 text-gray-400" />
        <span>Audit log</span>
        <span className="text-xs text-gray-400 font-normal ml-1">— operazioni sensibili</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-gray-100">
          <div className="px-5 py-3 flex items-center gap-3">
            <label className="text-xs text-gray-500 font-medium">Filtra:</label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 bg-white"
            >
              <option value="">Tutte le azioni</option>
              {Object.entries(ACTION_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">Caricamento...</div>
          ) : logs.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">Nessun evento registrato.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs text-gray-500">
                    <th className="px-4 py-2 font-medium">Data/ora</th>
                    <th className="px-4 py-2 font-medium">Utente</th>
                    <th className="px-4 py-2 font-medium">Azione</th>
                    <th className="px-4 py-2 font-medium">Entità</th>
                    <th className="px-4 py-2 font-medium">Dettaglio</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {new Date(log.created_at).toLocaleString("it-IT", {
                          dateStyle: "short",
                          timeStyle: "medium",
                        })}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 text-xs">
                        {log.user_email ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <ActionBadge action={log.action} />
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500">
                        {log.entity_type ? (
                          <span>
                            {log.entity_type}{log.entity_id != null ? ` #${log.entity_id}` : ""}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 max-w-xs truncate">
                        {log.detail
                          ? Object.entries(log.detail)
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(" · ")
                          : <span className="text-gray-300">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Email actions ─────────────────────────────────────────────────────────────

function WelcomeEmailModal({ user, onClose }: { user: UserAdminOut; onClose: () => void }) {
  const [tempPwd, setTempPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<"ok" | "error" | null>(null);

  const handleSend = async () => {
    if (!tempPwd) return;
    setLoading(true);
    try {
      await adminService.sendWelcomeEmail(user.id, tempPwd);
      setResult("ok");
    } catch {
      setResult("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900">Invia email di benvenuto</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-gray-500">
          Verrà inviata un'email a <strong>{user.email}</strong> con le credenziali di accesso.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password temporanea</label>
          <input
            type="text"
            value={tempPwd}
            onChange={(e) => { setTempPwd(e.target.value); setResult(null); }}
            placeholder="Inserisci la password che hai assegnato"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        {result === "ok" && <p className="text-sm text-green-600">Email di benvenuto inviata!</p>}
        {result === "error" && <p className="text-sm text-red-600">Errore nell'invio. Controlla la config SMTP.</p>}
        <div className="flex justify-end gap-3 pt-1">
          <Button variant="secondary" onClick={onClose}>Annulla</Button>
          <Button onClick={handleSend} loading={loading} disabled={!tempPwd}>
            <Send className="w-4 h-4 mr-1.5" /> Invia
          </Button>
        </div>
      </div>
    </div>
  );
}

function ResetLinkButton({ user }: { user: UserAdminOut }) {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    if (!confirm(`Inviare link di reset password a ${user.email}?`)) return;
    setLoading(true);
    try {
      await adminService.sendResetLink(user.id);
      setSent(true);
      setTimeout(() => setSent(false), 5000);
    } catch {
      alert("Errore nell'invio. Controlla la configurazione SMTP.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleSend}
      disabled={loading || sent}
      className={`p-1.5 rounded transition-colors ${sent ? "text-green-500" : "text-gray-500 hover:text-brand-600 hover:bg-brand-50"}`}
      title={sent ? "Link inviato!" : "Invia link reset password"}
    >
      <KeyRound className="w-4 h-4" />
    </button>
  );
}

export function Admin() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<UserAdminOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [welcomeUser, setWelcomeUser] = useState<UserAdminOut | null>(null);

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: adminService.listUsers,
  });

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const handleDelete = (user: UserAdminOut) => {
    if (confirm(`Eliminare l'utente ${user.email}?`)) {
      deleteMutation.mutate(user.id);
    }
  };

  return (
    <>
      <TopBar title="Amministrazione" />
      <main className="flex-1">
      <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-end mb-6">
        <Button onClick={() => setCreating(true)}>
          <UserPlus className="w-4 h-4 mr-2" />
          Nuovo utente
        </Button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Caricamento...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">Nessun utente trovato.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-gray-600">Nome</th>
                <th className="px-4 py-3 font-medium text-gray-600">Email</th>
                <th className="px-4 py-3 font-medium text-gray-600">Ruolo</th>
                <th className="px-4 py-3 font-medium text-gray-600">Stato</th>
                <th className="px-4 py-3 font-medium text-gray-600">2FA</th>
                <th className="px-4 py-3 font-medium text-gray-600">Creato</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.name}</td>
                  <td className="px-4 py-3 text-gray-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-3">
                    <Badge active={u.is_active} />
                  </td>
                  <td className="px-4 py-3">
                    {u.two_factor_enabled ? (
                      <ShieldCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(u.created_at).toLocaleDateString("it-IT")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setWelcomeUser(u)}
                        className="p-1.5 rounded text-gray-500 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                        title="Invia email di benvenuto"
                      >
                        <Mail className="w-4 h-4" />
                      </button>
                      <ResetLinkButton user={u} />
                      <button
                        onClick={() => setEditing(u)}
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
                        title="Modifica"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(u)}
                        className="p-1.5 rounded hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors"
                        title="Elimina"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <AuditLogSection />

      {editing && <EditModal user={editing} onClose={() => setEditing(null)} />}
      {creating && <CreateModal onClose={() => setCreating(false)} />}
      {welcomeUser && <WelcomeEmailModal user={welcomeUser} onClose={() => setWelcomeUser(null)} />}
    </div>
      </main>
    </>
  );
}
