import { useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { assetService, type Asset, type AssetType, type Exchange } from "@/services/transactions";

interface AssetAutocompleteProps {
  onSelect: (asset: Asset) => void;
  placeholder?: string;
}

const ASSET_TYPES: AssetType[] = ["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT"];
const EXCHANGES: Exchange[] = ["MIL", "EuroTLX", "MOT", "XETRA", "NYSE", "NASDAQ", "CRYPTO", "OTHER"];

const labelClass = "block text-xs font-medium text-gray-500 mb-1";
const inputClass = "w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent";

export function AssetAutocomplete({ onSelect, placeholder = "Cerca per nome, ticker o ISIN..." }: AssetAutocompleteProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Asset[]>([]);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [form, setForm] = useState({
    isin: "",
    symbol: "",
    name: "",
    type: "BOND" as AssetType,
    exchange: "MOT" as Exchange,
    currency: "EUR",
  });
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 2) { setResults([]); setOpen(false); return; }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const res = await assetService.search(query);
        setResults(res);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 300);
  }, [query]);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const choose = (asset: Asset) => {
    setSelected(asset);
    setQuery(asset.symbol);
    setOpen(false);
    setShowCreate(false);
    onSelect(asset);
  };

  const handleCreate = async () => {
    if (!form.name.trim() || !form.symbol.trim()) {
      setCreateError("Nome e simbolo sono obbligatori");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      const asset = await assetService.create({
        isin: form.isin.trim() || undefined,
        symbol: form.symbol.trim().toUpperCase(),
        name: form.name.trim(),
        type: form.type,
        exchange: form.exchange,
        currency: form.currency.trim().toUpperCase() || "EUR",
      });
      choose(asset);
      setShowCreate(false);
      setForm({ isin: "", symbol: "", name: "", type: "BOND", exchange: "MOT", currency: "EUR" });
    } catch (e: any) {
      setCreateError(e?.response?.data?.detail ?? "Errore nella creazione dell'asset");
    } finally {
      setCreating(false);
    }
  };

  // Pre-fill form when the user opens create panel with current query
  const openCreate = () => {
    const q = query.trim();
    const looksLikeIsin = /^[A-Z]{2}[A-Z0-9]{10}$/.test(q.toUpperCase());
    setForm((f) => ({
      ...f,
      isin: looksLikeIsin ? q.toUpperCase() : f.isin,
      symbol: looksLikeIsin ? q.toUpperCase() : q.toUpperCase(),
    }));
    setOpen(false);
    setShowCreate(true);
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Search input */}
      <input
        type="text"
        value={selected ? `${selected.symbol} — ${selected.name}` : query}
        onChange={(e) => { setSelected(null); setQuery(e.target.value); setShowCreate(false); }}
        onFocus={() => results.length > 0 && !selected && setOpen(true)}
        placeholder={placeholder}
        className={inputClass}
      />

      {/* Dropdown results */}
      {open && (
        <ul className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
          {results.map((a) => (
            <li key={a.id} onClick={() => choose(a)} className="px-3 py-2 hover:bg-gray-50 cursor-pointer">
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm text-gray-900">{a.symbol}</span>
                <span className="text-xs text-gray-400">{a.isin ?? a.exchange}</span>
              </div>
              <div className="text-xs text-gray-500 truncate">{a.name}</div>
            </li>
          ))}
          {/* Crea nuovo — sempre visibile in fondo al dropdown */}
          <li
            onClick={openCreate}
            className="px-3 py-2 hover:bg-brand-50 cursor-pointer border-t border-gray-100 flex items-center gap-2 text-brand-600"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="text-sm font-medium">Crea nuovo asset…</span>
          </li>
        </ul>
      )}

      {/* Bottone crea quando non ci sono risultati ma c'è testo */}
      {!open && !selected && query.length >= 2 && results.length === 0 && !showCreate && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
          <div className="px-3 py-2 text-xs text-gray-400">Nessun asset trovato.</div>
          <button
            type="button"
            onClick={openCreate}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-brand-600 font-medium hover:bg-brand-50 border-t border-gray-100"
          >
            <Plus className="w-3.5 h-3.5" />
            Crea nuovo asset…
          </button>
        </div>
      )}

      {/* Pannello creazione inline */}
      {showCreate && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-xl p-4 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-semibold text-gray-800">Nuovo asset</span>
            <button type="button" onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>ISIN</label>
              <input className={inputClass} placeholder="IT0005415291" value={form.isin}
                onChange={(e) => setForm((f) => ({ ...f, isin: e.target.value }))} />
            </div>
            <div>
              <label className={labelClass}>Simbolo *</label>
              <input className={inputClass} placeholder="BTP-FUTURA-LG30" value={form.symbol}
                onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))} />
            </div>
          </div>

          <div>
            <label className={labelClass}>Nome *</label>
            <input className={inputClass} placeholder="BTP Futura Luglio 2030" value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={labelClass}>Tipo *</label>
              <select className={inputClass} value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as AssetType }))}>
                {ASSET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Borsa *</label>
              <select className={inputClass} value={form.exchange}
                onChange={(e) => setForm((f) => ({ ...f, exchange: e.target.value as Exchange }))}>
                {EXCHANGES.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Valuta *</label>
              <input className={inputClass} placeholder="EUR" maxLength={3} value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} />
            </div>
          </div>

          {createError && <p className="text-xs text-red-600">{createError}</p>}

          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className="w-full py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            {creating ? "Creazione…" : "Crea e seleziona"}
          </button>
        </div>
      )}
    </div>
  );
}
