import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus, Pencil, Trash2, ShieldCheck, ShieldOff, X, ChevronDown, ClipboardList, Mail, KeyRound, Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getIntlLocale } from "@/utils/format";
import i18n from "@/i18n";
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
  const { t } = useTranslation();
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
      }`}
    >
      {active ? t("admin.active") : t("admin.disabled")}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  const { t } = useTranslation();
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        role === "SUPERADMIN" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-600"
      }`}
    >
      {role === "SUPERADMIN" ? t("admin.superadmin") : t("admin.user")}
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
  const { t } = useTranslation();

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{t("admin.editUser")}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-sm text-gray-500">{t("admin.email")}</p>
            <p className="text-sm font-medium text-gray-900">{user.email}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("admin.role")}</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "USER" | "SUPERADMIN")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="USER">{t("admin.user")}</option>
              <option value="SUPERADMIN">{t("admin.superadmin")}</option>
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
              {t("admin.accountActive")}
            </label>
          </div>

          {user.two_factor_enabled && (
            <div className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-amber-800">{t("admin.twoFactorEnabled")}</p>
                <p className="text-xs text-amber-600">{t("admin.reset2fa")}</p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                loading={reset2fa.isPending}
                onClick={() => reset2fa.mutate()}
              >
                <ShieldOff className="w-4 h-4 mr-1" />
                {t("admin.reset")}
              </Button>
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            loading={mutation.isPending}
            onClick={() => mutation.mutate({ role, is_active: isActive })}
          >
            {t("common.save")}
          </Button>
        </div>
        {mutation.isError && (
          <p className="mt-2 text-sm text-red-600 text-center">{t("admin.saveError")}</p>
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
  const { t } = useTranslation();
  const form = useForm<CreateData>({ resolver: zodResolver(createSchema), defaultValues: { role: "USER" } });

  const mutation = useMutation({
    mutationFn: adminService.createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{t("admin.createUser")}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <Input
            label={t("admin.name")}
            error={form.formState.errors.name?.message}
            {...form.register("name")}
          />
          <Input
            label={t("admin.email")}
            type="email"
            error={form.formState.errors.email?.message}
            {...form.register("email")}
          />
          <Input
            label={t("admin.password")}
            type="password"
            error={form.formState.errors.password?.message}
            {...form.register("password")}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("admin.role")}</label>
            <select
              {...form.register("role")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="USER">{t("admin.user")}</option>
              <option value="SUPERADMIN">{t("admin.superadmin")}</option>
            </select>
          </div>

          {mutation.isError && (
            <p className="text-sm text-red-600 text-center">{t("admin.createError")}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {t("common.add")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AuditLogSection() {
  const [open, setOpen] = useState(false);
  const [filterAction, setFilterAction] = useState("");
  const { t } = useTranslation();

  const ACTION_LABELS: Record<string, { label: string; color: string }> = {
    DELETE_TRANSACTION: { label: t("transactions.types.SELL") + " TX", color: "text-red-600 bg-red-50 border-red-200" },
    DELETE_ACCOUNT:     { label: t("common.delete") + " " + t("common.account"), color: "text-red-600 bg-red-50 border-red-200" },
    DELETE_USER:        { label: t("common.delete") + " " + t("admin.user").toLowerCase(), color: "text-red-700 bg-red-100 border-red-300" },
    CREATE_USER:        { label: t("admin.createUser"), color: "text-green-700 bg-green-50 border-green-200" },
    UPDATE_USER:        { label: t("admin.editUser"), color: "text-amber-700 bg-amber-50 border-amber-200" },
    BULK_ENRICH_ASSETS: { label: t("admin.enrichTitle"), color: "text-blue-600 bg-blue-50 border-blue-200" },
  };

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["audit-logs", filterAction],
    queryFn: () => adminService.getAuditLogs({ action: filterAction || undefined, limit: 200 }),
    enabled: open,
  });

  function ActionBadge({ action }: { action: string }) {
    const meta = ACTION_LABELS[action] ?? { label: action, color: "text-gray-600 bg-gray-100 border-gray-200" };
    return (
      <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${meta.color}`}>
        {meta.label}
      </span>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mt-6">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 text-sm font-semibold text-gray-800 hover:bg-gray-50 transition-colors"
      >
        <ClipboardList className="w-4 h-4 text-gray-400" />
        <span>{t("admin.auditLog")}</span>
        <span className="text-xs text-gray-400 font-normal ml-1">{t("admin.auditLogDesc")}</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-gray-100">
          <div className="px-5 py-3 flex items-center gap-3">
            <label className="text-xs text-gray-500 font-medium">{t("admin.filter")}</label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 bg-white"
            >
              <option value="">{t("admin.allActions")}</option>
              {Object.entries(ACTION_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">{t("common.loading")}</div>
          ) : logs.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">{t("admin.noEvents")}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs text-gray-500">
                    <th className="px-4 py-2 font-medium">{t("admin.dateTime")}</th>
                    <th className="px-4 py-2 font-medium">{t("admin.user")}</th>
                    <th className="px-4 py-2 font-medium">{t("admin.action")}</th>
                    <th className="px-4 py-2 font-medium">{t("admin.entity")}</th>
                    <th className="px-4 py-2 font-medium">{t("admin.detail")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {new Date(log.created_at).toLocaleString(getIntlLocale(i18n.language), {
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
  const { t } = useTranslation();

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900">{t("admin.sendWelcome")}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-gray-500">
          {t("admin.welcomeDesc", { email: user.email })}
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t("admin.tempPassword")}</label>
          <input
            type="text"
            value={tempPwd}
            onChange={(e) => { setTempPwd(e.target.value); setResult(null); }}
            placeholder={t("admin.tempPasswordHint")}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        {result === "ok" && <p className="text-sm text-green-600">{t("admin.welcomeSent")}</p>}
        {result === "error" && <p className="text-sm text-red-600">{t("admin.welcomeError")}</p>}
        <div className="flex justify-end gap-3 pt-1">
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button onClick={handleSend} loading={loading} disabled={!tempPwd}>
            <Send className="w-4 h-4 mr-1.5" /> {t("common.send")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ResetLinkButton({ user }: { user: UserAdminOut }) {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const { t } = useTranslation();

  const handleSend = async () => {
    if (!confirm(t("admin.resetLinkDesc", { email: user.email }))) return;
    setLoading(true);
    try {
      await adminService.sendResetLink(user.id);
      setSent(true);
      setTimeout(() => setSent(false), 5000);
    } catch {
      alert(t("admin.resetLinkError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleSend}
      disabled={loading || sent}
      className={`p-1.5 rounded transition-colors ${sent ? "text-green-500" : "text-gray-500 hover:text-brand-600 hover:bg-brand-50"}`}
      title={sent ? t("admin.resetLinkSent") : t("admin.sendResetLink")}
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
  const { t } = useTranslation();

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: adminService.listUsers,
  });

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const handleDelete = (user: UserAdminOut) => {
    if (confirm(t("admin.deleteUserConfirm", { email: user.email }))) {
      deleteMutation.mutate(user.id);
    }
  };

  return (
    <>
      <TopBar title={t("admin.title")} />
      <main className="flex-1">
      <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-end mb-6">
        <Button onClick={() => setCreating(true)}>
          <UserPlus className="w-4 h-4 mr-2" />
          {t("admin.newUser")}
        </Button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">{t("common.loading")}</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">{t("admin.noUsers")}</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-gray-600">{t("admin.name")}</th>
                <th className="hidden sm:table-cell px-4 py-3 font-medium text-gray-600">{t("admin.email")}</th>
                <th className="px-4 py-3 font-medium text-gray-600">{t("admin.role")}</th>
                <th className="hidden md:table-cell px-4 py-3 font-medium text-gray-600">{t("admin.status")}</th>
                <th className="hidden md:table-cell px-4 py-3 font-medium text-gray-600">{t("admin.twoFactor")}</th>
                <th className="hidden lg:table-cell px-4 py-3 font-medium text-gray-600">{t("admin.created")}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 truncate max-w-[120px] sm:max-w-none">{u.name}</div>
                    <div className="sm:hidden text-xs text-gray-400 truncate max-w-[120px]">{u.email}</div>
                    <div className="md:hidden mt-0.5">
                      <Badge active={u.is_active} />
                    </div>
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-gray-600 truncate max-w-[160px]">{u.email}</td>
                  <td className="px-4 py-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="hidden md:table-cell px-4 py-3">
                    <Badge active={u.is_active} />
                  </td>
                  <td className="hidden md:table-cell px-4 py-3">
                    {u.two_factor_enabled ? (
                      <ShieldCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="hidden lg:table-cell px-4 py-3 text-gray-500">
                    {new Date(u.created_at).toLocaleDateString(getIntlLocale(i18n.language))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setWelcomeUser(u)}
                        className="p-1.5 rounded text-gray-500 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                        title={t("admin.sendWelcome")}
                      >
                        <Mail className="w-4 h-4" />
                      </button>
                      <ResetLinkButton user={u} />
                      <button
                        onClick={() => setEditing(u)}
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
                        title={t("common.edit")}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(u)}
                        className="p-1.5 rounded hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors"
                        title={t("common.delete")}
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
