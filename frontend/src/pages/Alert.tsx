import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, Plus, Trash2, X, TrendingUp, TrendingDown, ArrowUp, ArrowDown } from "lucide-react";
import { alertService, type AlertOut, type AlertType, type AlertCreate } from "@/services/alert";
import { assetService, type Asset } from "@/services/transactions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

// ── Helpers ──────────────────────────────────────────────────────────────────

const ALERT_LABELS: Record<AlertType, string> = {
  PRICE_ABOVE: "Prezzo sopra",
  PRICE_BELOW: "Prezzo sotto",
  CHANGE_PCT_UP: "Variazione + oltre",
  CHANGE_PCT_DOWN: "Variazione − oltre",
};

const ALERT_ICONS: Record<AlertType, React.ReactNode> = {
  PRICE_ABOVE: <ArrowUp className="w-4 h-4 text-green-500" />,
  PRICE_BELOW: <ArrowDown className="w-4 h-4 text-red-500" />,
  CHANGE_PCT_UP: <TrendingUp className="w-4 h-4 text-green-500" />,
  CHANGE_PCT_DOWN: <TrendingDown className="w-4 h-4 text-red-500" />,
};

const isPct = (t: AlertType) => t === "CHANGE_PCT_UP" || t === "CHANGE_PCT_DOWN";

function thresholdLabel(alert: AlertOut) {
  const suffix = isPct(alert.alert_type) ? "%" : " €";
  return `${alert.threshold.toLocaleString("it-IT", { maximumFractionDigits: 4 })}${suffix}`;
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins} min fa`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h fa`;
  return new Date(iso).toLocaleDateString("it-IT");
}

// ── Asset autocomplete ────────────────────────────────────────────────────────

function AssetSearch({
  value,
  onChange,
}: {
  value: Asset | null;
  onChange: (a: Asset | null) => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const { data: results = [] } = useQuery({
    queryKey: ["asset-search", q],
    queryFn: () => assetService.search(q),
    enabled: q.length >= 2,
  });

  const handleInput = (v: string) => {
    setQ(v);
    onChange(null);
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setOpen(true), 150);
  };

  const pick = (a: Asset) => {
    onChange(a);
    setQ(a.name);
    setOpen(false);
  };

  return (
    <div className="relative">
      <Input
        label="Asset"
        value={q}
        onChange={(e) => handleInput(e.target.value)}
        onFocus={() => q.length >= 2 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder="Cerca per nome, ticker o ISIN..."
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 w-full bg-white border border-gray-200 rounded-lg shadow-lg mt-1 max-h-48 overflow-y-auto">
          {results.map((a) => (
            <li
              key={a.id}
              onMouseDown={() => pick(a)}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 flex items-center justify-between"
            >
              <span className="font-medium text-gray-900">{a.name}</span>
              <span className="text-xs text-gray-400">{a.symbol}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Create modal ──────────────────────────────────────────────────────────────

function CreateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [asset, setAsset] = useState<Asset | null>(null);
  const [alertType, setAlertType] = useState<AlertType>("PRICE_ABOVE");
  const [threshold, setThreshold] = useState("");
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: (body: AlertCreate) => alertService.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      onClose();
    },
    onError: () => setError("Errore durante la creazione dell'alert."),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!asset) return setError("Seleziona un asset.");
    const val = parseFloat(threshold.replace(",", "."));
    if (isNaN(val) || val <= 0) return setError("Inserisci una soglia valida.");
    mutation.mutate({ asset_id: asset.id, alert_type: alertType, threshold: val });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Nuovo alert</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <AssetSearch value={asset} onChange={setAsset} />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo di alert</label>
            <select
              value={alertType}
              onChange={(e) => setAlertType(e.target.value as AlertType)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {(Object.keys(ALERT_LABELS) as AlertType[]).map((t) => (
                <option key={t} value={t}>
                  {ALERT_LABELS[t]}
                </option>
              ))}
            </select>
          </div>

          <Input
            label={`Soglia ${isPct(alertType) ? "(%)" : "(€)"}`}
            type="number"
            step="any"
            min="0"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder={isPct(alertType) ? "es. 5" : "es. 42.50"}
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <Button type="button" variant="secondary" onClick={onClose}>
              Annulla
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              Crea alert
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Alert card ────────────────────────────────────────────────────────────────

function AlertCard({ alert }: { alert: AlertOut }) {
  const qc = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: () => alertService.update(alert.id, { is_active: !alert.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => alertService.remove(alert.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const wasTriggered = !!alert.last_triggered_at;

  return (
    <div
      className={`bg-white rounded-xl border shadow-sm p-4 flex items-center gap-4 transition-opacity ${
        alert.is_active ? "border-gray-200" : "border-gray-100 opacity-60"
      }`}
    >
      <div className="flex-shrink-0">{ALERT_ICONS[alert.alert_type]}</div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-gray-900 truncate">{alert.asset_name}</p>
          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
            {alert.asset_symbol}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {ALERT_LABELS[alert.alert_type]}{" "}
          <span className="font-medium text-gray-700">{thresholdLabel(alert)}</span>
        </p>
        {wasTriggered && (
          <p className="text-xs text-amber-600 mt-0.5">
            Scattato {timeAgo(alert.last_triggered_at!)}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={() => toggleMutation.mutate()}
          title={alert.is_active ? "Disabilita" : "Abilita"}
          className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
        >
          {alert.is_active ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
        </button>
        <button
          onClick={() => deleteMutation.mutate()}
          title="Elimina"
          className="p-1.5 rounded hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ── Pagina ────────────────────────────────────────────────────────────────────

export function Alert() {
  const [creating, setCreating] = useState(false);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: alertService.list,
    refetchInterval: 60_000,
  });

  const active = alerts.filter((a) => a.is_active);
  const inactive = alerts.filter((a) => !a.is_active);
  const triggered = alerts.filter((a) => a.last_triggered_at && a.is_active);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alert</h1>
          <p className="text-sm text-gray-500 mt-1">Notifiche automatiche sui prezzi</p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Nuovo alert
        </Button>
      </div>

      {/* Badge riepilogo */}
      <div className="flex gap-3 text-sm">
        <span className="bg-gray-100 text-gray-600 px-3 py-1 rounded-full">
          {active.length} attivi
        </span>
        {triggered.length > 0 && (
          <span className="bg-amber-100 text-amber-700 px-3 py-1 rounded-full">
            {triggered.length} scattati
          </span>
        )}
        {inactive.length > 0 && (
          <span className="bg-gray-100 text-gray-400 px-3 py-1 rounded-full">
            {inactive.length} disabilitati
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-sm text-gray-500">Caricamento...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
          <Bell className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-500">Nessun alert configurato</p>
          <p className="text-xs text-gray-400 mt-1">
            Crea un alert per ricevere una notifica quando un asset supera la soglia impostata.
          </p>
          <Button className="mt-4" onClick={() => setCreating(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Crea il primo alert
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          {active.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Attivi
              </h2>
              <div className="space-y-2">
                {active.map((a) => (
                  <AlertCard key={a.id} alert={a} />
                ))}
              </div>
            </section>
          )}

          {inactive.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Disabilitati
              </h2>
              <div className="space-y-2">
                {inactive.map((a) => (
                  <AlertCard key={a.id} alert={a} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">
        Gli alert vengono controllati ogni 5 minuti durante l'orario di mercato.
        Cooldown di 4 ore tra un'attivazione e la successiva.
      </p>

      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  );
}
