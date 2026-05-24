import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus, Pencil, Trash2, ShieldCheck, ShieldOff, X } from "lucide-react";
import { adminService, type UserAdminOut, type UserAdminUpdate } from "@/services/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

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

export function Admin() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<UserAdminOut | null>(null);
  const [creating, setCreating] = useState(false);

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
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Amministrazione</h1>
          <p className="text-sm text-gray-500 mt-1">Gestisci gli utenti dell'applicazione</p>
        </div>
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
                    <div className="flex items-center gap-2 justify-end">
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

      {editing && <EditModal user={editing} onClose={() => setEditing(null)} />}
      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  );
}
