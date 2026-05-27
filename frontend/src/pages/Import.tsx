import { useState, useRef, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Upload, ChevronRight, Check, AlertCircle, Search,
  Plus, SkipForward, ArrowRight, Loader2, X, Download,
} from "lucide-react";
import { api } from "@/services/api";
import { TopBar } from "@/components/layout/TopBar";
import {
  importerService,
  type GhostfolioPreview,
  type GfAccountInfo,
  type GfAssetInfo,
  type AccountResolution,
  type AssetResolution,
} from "@/services/importer";
import { accountService } from "@/services/transactions";
import { assetService } from "@/services/transactions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

// ── Export helpers ────────────────────────────────────────────────────────────

function downloadBlob(blob: Blob, fallbackName: string, headers: Record<string, string>) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cd = headers["content-disposition"] as string | undefined;
  const match = cd?.match(/filename=(.+)/);
  a.download = match ? match[1] : fallbackName;
  a.click();
  URL.revokeObjectURL(url);
}

function ExportCard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/portfolio/export", { responseType: "blob" });
      downloadBlob(
        new Blob([resp.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
        "nextfolio_export.xlsx",
        resp.headers,
      );
    } catch {
      setError("Errore durante l'esportazione. Riprova.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGhostfolioExport() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/portfolio/export/ghostfolio", { responseType: "blob" });
      downloadBlob(new Blob([resp.data], { type: "application/json" }), "nextfolio_ghostfolio.json", resp.headers);
    } catch {
      setError("Errore durante l'esportazione. Riprova.");
    } finally {
      setLoading(false);
    }
  }

  async function handleNextfolioExport() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/portfolio/export/nextfolio", { responseType: "blob" });
      downloadBlob(new Blob([resp.data], { type: "application/json" }), "nextfolio_backup.json", resp.headers);
    } catch {
      setError("Errore durante l'esportazione. Riprova.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100 mb-1">Esporta dati</h2>
      <p className="text-xs text-gray-400 dark:text-slate-500 mb-4">
        Backup completo, Excel per il commercialista, o formato Ghostfolio per migrazione.
      </p>

      <div className="flex flex-col sm:flex-row sm:items-start gap-4">
        <div className="flex flex-col gap-2">
          <button
            onClick={handleNextfolioExport}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-4 h-4" />
            Backup Nextfolio (.json)
          </button>
          <button
            onClick={handleExport}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-4 h-4" />
            {loading ? "Preparazione..." : "Scarica Excel (.xlsx)"}
          </button>
          <button
            onClick={handleGhostfolioExport}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gray-700 text-white text-sm font-medium hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-4 h-4" />
            Esporta Ghostfolio (.json)
          </button>
        </div>

        <div className="text-xs text-gray-400 dark:text-slate-500 space-y-1">
          <p><strong className="text-gray-600 dark:text-slate-400">Backup Nextfolio:</strong> Tutti i dati (conti, asset, transazioni) — per ripristino o migrazione</p>
          <p><strong className="text-gray-600 dark:text-slate-400">Excel:</strong> Fogli Transazioni, Posizioni, Info — per commercialista</p>
          <p><strong className="text-gray-600 dark:text-slate-400">Ghostfolio:</strong> Formato JSON v3 compatibile con import Ghostfolio</p>
        </div>
      </div>

      {error && (
        <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}

function RestoreCard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    accounts_created: number;
    assets_created: number;
    transactions_imported: number;
    transactions_skipped: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const text = await file.text();
      const raw = JSON.parse(text);
      const resp = await api.post("/import/nextfolio", { raw });
      setResult(resp.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Errore durante l'importazione. Verifica che il file sia un backup Nextfolio valido.");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-100 mb-1">Ripristina backup</h2>
      <p className="text-xs text-gray-400 dark:text-slate-500 mb-4">
        Importa un file <code className="bg-gray-100 dark:bg-slate-800 px-1 rounded">nextfolio_backup_*.json</code>.
        I duplicati vengono ignorati automaticamente.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={handleFile}
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={loading}
        className="flex items-center gap-2 px-5 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <Download className="w-4 h-4 rotate-180" />
        {loading ? "Importazione in corso..." : "Seleziona backup (.json)"}
      </button>

      {result && (
        <div className="mt-4 text-xs bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-4 py-3 space-y-0.5">
          <p className="font-semibold text-green-700 dark:text-green-400 mb-1">Importazione completata</p>
          <p className="text-green-600 dark:text-green-500">Conti creati: <strong>{result.accounts_created}</strong></p>
          <p className="text-green-600 dark:text-green-500">Asset creati: <strong>{result.assets_created}</strong></p>
          <p className="text-green-600 dark:text-green-500">Transazioni importate: <strong>{result.transactions_imported}</strong></p>
          {result.transactions_skipped > 0 && (
            <p className="text-gray-500 dark:text-slate-400">Transazioni duplicate saltate: {result.transactions_skipped}</p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STEPS = ["Carica file", "Account", "Asset", "Importa"];

const ASSET_TYPES = ["ETF", "STOCK", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"];
const EXCHANGES = ["MIL", "EuroTLX", "MOT", "XETRA", "NYSE", "NASDAQ", "CRYPTO", "OTHER"];

// ── Stepper ───────────────────────────────────────────────────────────────────

function Stepper({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
              i < current
                ? "bg-brand-600 text-white"
                : i === current
                ? "bg-brand-100 text-brand-700 ring-2 ring-brand-400"
                : "bg-gray-100 text-gray-400"
            }`}
          >
            {i < current ? <Check className="w-4 h-4" /> : i + 1}
          </div>
          <span className={`text-sm font-medium hidden sm:block ${i === current ? "text-brand-700" : "text-gray-400"}`}>
            {label}
          </span>
          {i < STEPS.length - 1 && <ChevronRight className="w-4 h-4 text-gray-300" />}
        </div>
      ))}
    </div>
  );
}

// ── Step 0: File upload ───────────────────────────────────────────────────────

function UploadStep({ onParsed }: { onParsed: (raw: unknown) => void }) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((file: File) => {
    setError("");
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        if (!json.activities || !Array.isArray(json.activities)) {
          setError("File non valido: manca il campo 'activities'. Assicurati di esportare da Ghostfolio in formato JSON.");
          return;
        }
        onParsed(json);
      } catch {
        setError("Impossibile leggere il file. Assicurati che sia un JSON valido.");
      }
    };
    reader.readAsText(file);
  }, [onParsed]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-lg font-semibold text-gray-900 mb-2">Carica export Ghostfolio</h2>
      <p className="text-sm text-gray-500 mb-6">
        Esporta il tuo portafoglio da Ghostfolio (<em>Impostazioni → Importa/Esporta → Esporta JSON</em>) e carica il file qui.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? "border-brand-400 bg-brand-50" : "border-gray-300 hover:border-brand-300 hover:bg-gray-50"
        }`}
      >
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
        <p className="text-sm font-medium text-gray-700">Trascina qui il file JSON</p>
        <p className="text-xs text-gray-400 mt-1">oppure clicca per scegliere</p>
        <input
          ref={inputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}

// ── Step 1: Account mapping ───────────────────────────────────────────────────

function AccountStep({
  preview,
  resolutions,
  onChange,
}: {
  preview: GhostfolioPreview;
  resolutions: Record<string, AccountResolution>;
  onChange: (id: string, r: AccountResolution) => void;
}) {
  const { data: existingAccounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Mapping account</h2>
        <p className="text-sm text-gray-500">
          Per ogni conto trovato nel file scegli se crearlo o collegarlo a uno esistente in Nextfolio.
        </p>
      </div>

      {preview.accounts.map((acc) => {
        const r = resolutions[acc.ghostfolio_id] ?? {
          ghostfolio_id: acc.ghostfolio_id,
          action: acc.existing_match ? "use_existing" : "create",
          existing_id: acc.existing_match?.id,
          name: acc.name === "(nessun conto)" ? "Importato" : acc.name,
          broker: acc.broker ?? undefined,
          currency: acc.currency,
        };

        return (
          <div key={acc.ghostfolio_id} className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-gray-900">{acc.name}</p>
                <p className="text-xs text-gray-400">{acc.broker ?? "—"} · {acc.transaction_count} transazioni</p>
              </div>
              {acc.is_null && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">senza conto</span>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => onChange(acc.ghostfolio_id, { ...r, action: "use_existing" })}
                className={`flex-1 text-sm py-1.5 rounded-lg border transition-colors ${
                  r.action === "use_existing"
                    ? "border-brand-400 bg-brand-50 text-brand-700 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                Usa esistente
              </button>
              <button
                onClick={() => onChange(acc.ghostfolio_id, { ...r, action: "create" })}
                className={`flex-1 text-sm py-1.5 rounded-lg border transition-colors ${
                  r.action === "create"
                    ? "border-brand-400 bg-brand-50 text-brand-700 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                Crea nuovo
              </button>
            </div>

            {r.action === "use_existing" && (
              <select
                value={r.existing_id ?? ""}
                onChange={(e) => onChange(acc.ghostfolio_id, { ...r, existing_id: Number(e.target.value) })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">— seleziona conto —</option>
                {existingAccounts.map((a: any) => (
                  <option key={a.id} value={a.id}>{a.name} ({a.broker ?? a.type})</option>
                ))}
              </select>
            )}

            {r.action === "create" && (
              <div className="grid grid-cols-2 gap-2">
                <Input
                  label="Nome"
                  value={r.name ?? ""}
                  onChange={(e) => onChange(acc.ghostfolio_id, { ...r, name: e.target.value })}
                />
                <Input
                  label="Broker"
                  value={r.broker ?? ""}
                  onChange={(e) => onChange(acc.ghostfolio_id, { ...r, broker: e.target.value })}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Step 2: Asset mapping ─────────────────────────────────────────────────────

function AssetSearchBox({
  value,
  onSelect,
}: {
  value: { id: number; name: string } | null;
  onSelect: (a: { id: number; symbol: string; name: string; type: string } | null) => void;
}) {
  const [q, setQ] = useState(value?.name ?? "");
  const [open, setOpen] = useState(false);

  const { data: results = [] } = useQuery({
    queryKey: ["asset-search-import", q],
    queryFn: () => assetService.search(q),
    enabled: q.length >= 2,
  });

  return (
    <div className="relative">
      <div className="flex items-center gap-2">
        <input
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="Cerca asset esistente…"
          value={q}
          onChange={(e) => { setQ(e.target.value); onSelect(null); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
        />
        <Search className="w-4 h-4 text-gray-400 -ml-8 pointer-events-none" />
      </div>
      {open && results.length > 0 && (
        <ul className="absolute z-20 w-full bg-white border border-gray-200 rounded-lg shadow-lg mt-1 max-h-40 overflow-y-auto">
          {results.map((a: any) => (
            <li
              key={a.id}
              onMouseDown={() => { onSelect(a); setQ(a.name); setOpen(false); }}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 flex justify-between"
            >
              <span className="font-medium">{a.name}</span>
              <span className="text-xs text-gray-400">{a.symbol}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AssetRow({
  asset,
  resolution,
  onChange,
}: {
  asset: GfAssetInfo;
  resolution: AssetResolution;
  onChange: (r: AssetResolution) => void;
}) {
  const r = resolution;
  const isAutoResolved = !asset.is_uuid && !!asset.db_match;

  return (
    <div className={`bg-white rounded-xl border p-4 space-y-3 ${
      r.action === "skip" ? "opacity-50 border-gray-100" : "border-gray-200"
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-900 truncate">{asset.name}</p>
            {asset.is_uuid && (
              <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded flex-shrink-0">MANUAL</span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {asset.ghostfolio_symbol.length > 36 ? asset.ghostfolio_symbol.slice(0, 8) + "…" : asset.ghostfolio_symbol}
            {" · "}{asset.transaction_count} transazioni ({asset.tx_types.join(", ")})
            {asset.has_price_history && ` · ${asset.price_history_count} prezzi storici`}
          </p>
        </div>
        {isAutoResolved && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded flex-shrink-0">auto</span>
        )}
      </div>

      {/* Action toggle */}
      <div className="flex gap-2">
        {["use_existing", "create", "skip"].map((action) => (
          <button
            key={action}
            onClick={() => onChange({ ...r, action: action as AssetResolution["action"] })}
            className={`flex-1 text-xs py-1.5 rounded-lg border transition-colors ${
              r.action === action
                ? "border-brand-400 bg-brand-50 text-brand-700 font-medium"
                : "border-gray-200 text-gray-400 hover:border-gray-300"
            }`}
          >
            {action === "use_existing" ? "Collega" : action === "create" ? "Crea" : "Salta"}
          </button>
        ))}
      </div>

      {r.action === "use_existing" && (
        <div>
          {r.existing_id ? (
            <div className="flex items-center justify-between text-sm bg-green-50 rounded-lg px-3 py-2">
              <span className="text-green-700 font-medium">Asset selezionato (id {r.existing_id})</span>
              <button onClick={() => onChange({ ...r, existing_id: undefined })} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <AssetSearchBox
              value={null}
              onSelect={(a) => a && onChange({ ...r, existing_id: a.id })}
            />
          )}
          {/* Suggerimenti automatici */}
          {!r.existing_id && asset.db_match && (
            <button
              onClick={() => onChange({ ...r, existing_id: asset.db_match!.id })}
              className="mt-2 w-full text-left text-xs bg-brand-50 text-brand-700 px-3 py-2 rounded-lg hover:bg-brand-100 transition-colors"
            >
              Suggerito: <strong>{asset.db_match.name}</strong> ({asset.db_match.symbol})
            </button>
          )}
          {!r.existing_id && asset.suggestions.map((s) => (
            <button
              key={s.id}
              onClick={() => onChange({ ...r, existing_id: s.id })}
              className="mt-1 w-full text-left text-xs bg-gray-50 text-gray-700 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              Suggerito: <strong>{s.name}</strong> ({s.symbol})
            </button>
          ))}
        </div>
      )}

      {r.action === "create" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Nome"
              value={r.name ?? asset.name}
              onChange={(e) => onChange({ ...r, name: e.target.value })}
            />
            <div>
              <Input
                label="Simbolo ticker (opzionale)"
                value={r.symbol ?? (asset.is_uuid ? "" : asset.ghostfolio_symbol)}
                onChange={(e) => onChange({ ...r, symbol: e.target.value })}
                placeholder="es. SWDA.MI"
              />
              <p className="text-xs text-gray-400 mt-0.5">Se assente viene usato ISIN o WKN</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Tipo</label>
              <select
                value={r.type ?? asset.suggested_type}
                onChange={(e) => onChange({ ...r, type: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {ASSET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Borsa</label>
              <select
                value={r.exchange ?? asset.suggested_exchange}
                onChange={(e) => onChange({ ...r, exchange: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {EXCHANGES.map((ex) => <option key={ex} value={ex}>{ex}</option>)}
              </select>
            </div>
            <Input
              label="Valuta"
              value={r.currency ?? asset.currency}
              onChange={(e) => onChange({ ...r, currency: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="ISIN"
              value={r.isin ?? ""}
              onChange={(e) => onChange({ ...r, isin: e.target.value.trim() || undefined })}
              placeholder="IT0005217390"
            />
            <Input
              label="WKN"
              value={r.wkn ?? ""}
              onChange={(e) => onChange({ ...r, wkn: e.target.value.toUpperCase().slice(0, 6) || undefined })}
              placeholder="A2H9AX"
            />
          </div>
          {asset.has_price_history && (
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={r.import_price_history !== false}
                onChange={(e) => onChange({ ...r, import_price_history: e.target.checked })}
                className="rounded border-gray-300 text-brand-600"
              />
              Importa storico prezzi ({asset.price_history_count} date)
            </label>
          )}
        </div>
      )}

      {r.action === "skip" && (
        <p className="text-xs text-gray-400">
          Le {asset.transaction_count} transazioni di questo asset verranno ignorate.
        </p>
      )}
    </div>
  );
}

function AssetStep({
  preview,
  resolutions,
  onChange,
}: {
  preview: GhostfolioPreview;
  resolutions: Record<string, AssetResolution>;
  onChange: (sym: string, r: AssetResolution) => void;
}) {
  const needsAttention = preview.assets.filter((a) => !a.db_match);
  const autoResolved = preview.assets.filter((a) => a.db_match && !a.is_uuid);
  const [showAuto, setShowAuto] = useState(false);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Mapping asset</h2>
        <p className="text-sm text-gray-500">
          Collega ogni asset del file a uno già presente in Nextfolio, creane uno nuovo o salta le sue transazioni.
        </p>
      </div>

      {needsAttention.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Da risolvere ({needsAttention.length})
          </p>
          <div className="space-y-3">
            {needsAttention.map((a) => (
              <AssetRow
                key={a.ghostfolio_symbol}
                asset={a}
                resolution={resolutions[a.ghostfolio_symbol]}
                onChange={(r) => onChange(a.ghostfolio_symbol, r)}
              />
            ))}
          </div>
        </div>
      )}

      {autoResolved.length > 0 && (
        <div>
          <button
            onClick={() => setShowAuto((s) => !s)}
            className="text-xs font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-600 transition-colors flex items-center gap-1 mb-2"
          >
            Asset auto-riconosciuti ({autoResolved.length})
            <ChevronRight className={`w-3.5 h-3.5 transition-transform ${showAuto ? "rotate-90" : ""}`} />
          </button>
          {showAuto && (
            <div className="space-y-3">
              {autoResolved.map((a) => (
                <AssetRow
                  key={a.ghostfolio_symbol}
                  asset={a}
                  resolution={resolutions[a.ghostfolio_symbol]}
                  onChange={(r) => onChange(a.ghostfolio_symbol, r)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Step 3: Preview & execute ─────────────────────────────────────────────────

function SummaryStep({
  preview,
  accountResolutions,
  assetResolutions,
  onExecute,
  isPending,
  result,
  error,
}: {
  preview: GhostfolioPreview;
  accountResolutions: Record<string, AccountResolution>;
  assetResolutions: Record<string, AssetResolution>;
  onExecute: () => void;
  isPending: boolean;
  result: any | null;
  error: string | null;
}) {
  const accountsToCreate = Object.values(accountResolutions).filter((r) => r.action === "create").length;
  const assetsToCreate = Object.values(assetResolutions).filter((r) => r.action === "create").length;
  const assetsSkipped = Object.values(assetResolutions).filter((r) => r.action === "skip").length;
  const txSkipped = preview.assets
    .filter((a) => assetResolutions[a.ghostfolio_symbol]?.action === "skip")
    .reduce((s, a) => s + a.transaction_count, 0);

  if (result) {
    return (
      <div className="max-w-md mx-auto text-center space-y-4">
        <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto">
          <Check className="w-7 h-7 text-green-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">Import completato</h2>
        <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-left space-y-2">
          <Row label="Account creati" value={result.accounts_created} />
          <Row label="Asset creati" value={result.assets_created} />
          <Row label="Prezzi storici importati" value={result.price_history_inserted} />
          <Row label="Transazioni importate" value={result.transactions_created} />
          {result.transactions_skipped > 0 && <Row label="Transazioni saltate" value={result.transactions_skipped} warn />}
        </div>
        {result.errors.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 text-left space-y-1">
            {result.errors.map((e: string, i: number) => <p key={i}>• {e}</p>)}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Riepilogo</h2>
        <p className="text-sm text-gray-500">Controlla prima di importare.</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm space-y-2">
        <Row label="Account da creare" value={accountsToCreate} />
        <Row label="Asset da creare" value={assetsToCreate} />
        <Row label="Asset saltati" value={assetsSkipped} warn={assetsSkipped > 0} />
        <Row label="Transazioni totali" value={preview.total_transactions} />
        {txSkipped > 0 && <Row label="Transazioni che verranno saltate" value={txSkipped} warn />}
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}

      <Button className="w-full" onClick={onExecute} loading={isPending}>
        <ArrowRight className="w-4 h-4 mr-2" />
        Avvia import
      </Button>
    </div>
  );
}

function Row({ label, value, warn = false }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-600">{label}</span>
      <span className={`font-semibold ${warn && value > 0 ? "text-amber-600" : "text-gray-900"}`}>{value}</span>
    </div>
  );
}

// ── Wizard principale ─────────────────────────────────────────────────────────

function buildDefaultAccountResolutions(preview: GhostfolioPreview): Record<string, AccountResolution> {
  return Object.fromEntries(
    preview.accounts.map((acc) => [
      acc.ghostfolio_id,
      {
        ghostfolio_id: acc.ghostfolio_id,
        action: acc.existing_match ? "use_existing" : "create",
        existing_id: acc.existing_match?.id,
        name: acc.is_null ? "Importato" : acc.name,
        broker: acc.broker ?? undefined,
        currency: acc.currency,
      } satisfies AccountResolution,
    ])
  );
}

function buildDefaultAssetResolutions(preview: GhostfolioPreview): Record<string, AssetResolution> {
  return Object.fromEntries(
    preview.assets.map((a) => [
      a.ghostfolio_symbol,
      {
        ghostfolio_symbol: a.ghostfolio_symbol,
        action: a.db_match ? "use_existing" : "create",
        existing_id: a.db_match?.id,
        name: a.name,
        symbol: a.is_uuid ? "" : a.ghostfolio_symbol,
        type: a.suggested_type,
        exchange: a.suggested_exchange,
        currency: a.currency,
        import_price_history: a.has_price_history,
      } satisfies AssetResolution,
    ])
  );
}

export function Import() {
  const [step, setStep] = useState(0);
  const [rawJson, setRawJson] = useState<unknown>(null);
  const [preview, setPreview] = useState<GhostfolioPreview | null>(null);
  const [accountRes, setAccountRes] = useState<Record<string, AccountResolution>>({});
  const [assetRes, setAssetRes] = useState<Record<string, AssetResolution>>({});
  const [importResult, setImportResult] = useState<any>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: (raw: unknown) => importerService.preview(raw),
    onSuccess: (data) => {
      setPreview(data);
      setAccountRes(buildDefaultAccountResolutions(data));
      setAssetRes(buildDefaultAssetResolutions(data));
      setStep(1);
    },
  });

  const executeMutation = useMutation({
    mutationFn: () =>
      importerService.execute(
        rawJson,
        Object.values(accountRes),
        Object.values(assetRes),
      ),
    onSuccess: (data) => {
      setImportError(null);
      setImportResult(data);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? err?.message ?? "Errore sconosciuto";
      setImportError(String(detail));
    },
  });

  const canAdvanceAccounts = preview
    ? preview.accounts.every((acc) => {
        const r = accountRes[acc.ghostfolio_id];
        if (!r) return false;
        if (r.action === "use_existing") return !!r.existing_id;
        if (r.action === "create") return !!r.name?.trim();
        return false;
      })
    : false;

  const canAdvanceAssets = preview
    ? preview.assets.every((a) => {
        const r = assetRes[a.ghostfolio_symbol];
        if (!r) return false;
        if (r.action === "use_existing") return !!r.existing_id;
        if (r.action === "create") return !!(r.name?.trim() && (r.symbol?.trim() || r.isin?.trim() || r.wkn?.trim() || a.is_uuid));
        if (r.action === "skip") return true;
        return false;
      })
    : false;

  return (
    <>
      <TopBar title="Importa / Esporta" />
      <main className="flex-1">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <ExportCard />
      <RestoreCard />

      <div className="border-t border-gray-200 dark:border-slate-700 pt-6">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Importa da Ghostfolio</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Wizard interattivo — risolvi ogni ambiguità prima di importare</p>
        </div>

      <Stepper current={step} />

      {step === 0 && (
        <div className="space-y-4">
          <UploadStep
            onParsed={(raw) => {
              setRawJson(raw);
            }}
          />
          {rawJson && (
            <div className="max-w-xl mx-auto">
              <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center gap-2 mb-4">
                <Check className="w-4 h-4 flex-shrink-0" />
                File caricato correttamente. Clicca "Analizza" per proseguire.
              </div>
              <Button
                className="w-full"
                onClick={() => previewMutation.mutate(rawJson)}
                loading={previewMutation.isPending}
              >
                Analizza file
              </Button>
              {previewMutation.isError && (
                <p className="mt-2 text-sm text-red-600 text-center">
                  Errore: {(previewMutation.error as any)?.response?.data?.detail ?? "File non valido"}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {step === 1 && preview && (
        <div className="space-y-6">
          <AccountStep
            preview={preview}
            resolutions={accountRes}
            onChange={(id, r) => setAccountRes((prev) => ({ ...prev, [id]: r }))}
          />
          <div className="flex justify-between pt-2">
            <Button variant="secondary" onClick={() => setStep(0)}>Indietro</Button>
            <Button onClick={() => setStep(2)} disabled={!canAdvanceAccounts}>
              Avanti <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {step === 2 && preview && (
        <div className="space-y-6">
          <AssetStep
            preview={preview}
            resolutions={assetRes}
            onChange={(sym, r) => setAssetRes((prev) => ({ ...prev, [sym]: r }))}
          />
          <div className="flex justify-between pt-2">
            <Button variant="secondary" onClick={() => setStep(1)}>Indietro</Button>
            <Button onClick={() => setStep(3)} disabled={!canAdvanceAssets}>
              Avanti <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {step === 3 && preview && (
        <div className="space-y-6">
          <SummaryStep
            preview={preview}
            accountResolutions={accountRes}
            assetResolutions={assetRes}
            onExecute={() => { setImportError(null); executeMutation.mutate(); }}
            isPending={executeMutation.isPending}
            result={importResult}
            error={importError}
          />
          {!importResult && (
            <div className="max-w-md mx-auto">
              <Button variant="secondary" onClick={() => setStep(2)}>Indietro</Button>
            </div>
          )}
        </div>
      )}
      </div>
      </div>
      </main>
    </>
  );
}
