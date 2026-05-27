import { useState, useEffect, useRef, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Save, RefreshCw, ChevronDown, Search, Plus, Trash2, Info } from "lucide-react";
import { api } from "@/services/api";

// ── Types ────────────────────────────────────────────────────────────────────

export type AssetType = "STOCK" | "ETF" | "BOND" | "CRYPTO" | "COMMODITY" | "REIT" | "OTHER";
export type Exchange = "MIL" | "EuroTLX" | "MOT" | "XETRA" | "NYSE" | "NASDAQ" | "CRYPTO" | "OTHER";

export interface AssetFull {
  id: number;
  isin: string | null;
  wkn: string | null;
  symbol: string;
  yahoo_ticker: string | null;
  name: string;
  type: AssetType;
  exchange: Exchange;
  currency: string;
  sector: string | null;
  sectors_override: { name: string; weight: number }[] | null;
  countries_override: { code: string; name: string; weight: number }[] | null;
  enriched_at: string | null;
}

interface WeightedSector { name: string; weight: number }
interface WeightedCountry { code: string; name: string; weight: number }

// ── Constants ────────────────────────────────────────────────────────────────

const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: "STOCK", label: "Azione" },
  { value: "ETF", label: "ETF" },
  { value: "BOND", label: "Obbligazione" },
  { value: "CRYPTO", label: "Crypto" },
  { value: "COMMODITY", label: "Commodity" },
  { value: "REIT", label: "REIT" },
  { value: "OTHER", label: "Altro" },
];

const EXCHANGES: { value: Exchange; label: string }[] = [
  { value: "MIL", label: "Borsa Italiana (MIL)" },
  { value: "EuroTLX", label: "EuroTLX" },
  { value: "MOT", label: "MOT" },
  { value: "XETRA", label: "Xetra (DE)" },
  { value: "NYSE", label: "NYSE" },
  { value: "NASDAQ", label: "NASDAQ" },
  { value: "CRYPTO", label: "Crypto" },
  { value: "OTHER", label: "Altro" },
];

const COMMON_CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"];

// GICS standard sectors + extra for bond/mixed ETFs
const GICS_SECTORS = [
  "Communication Services",
  "Consumer Discretionary",
  "Consumer Staples",
  "Energy",
  "Financials",
  "Health Care",
  "Industrials",
  "Information Technology",
  "Materials",
  "Real Estate",
  "Utilities",
  "Bonds",
  "Cash",
  "Mutual Fund",
];

// ISO2 → Italian name (subset of most common)
const COUNTRY_LIST: { code: string; name: string }[] = [
  { code: "US", name: "Stati Uniti" },
  { code: "JP", name: "Giappone" },
  { code: "GB", name: "Regno Unito" },
  { code: "FR", name: "Francia" },
  { code: "DE", name: "Germania" },
  { code: "CH", name: "Svizzera" },
  { code: "CA", name: "Canada" },
  { code: "AU", name: "Australia" },
  { code: "NL", name: "Paesi Bassi" },
  { code: "SE", name: "Svezia" },
  { code: "DK", name: "Danimarca" },
  { code: "NO", name: "Norvegia" },
  { code: "FI", name: "Finlandia" },
  { code: "BE", name: "Belgio" },
  { code: "IT", name: "Italia" },
  { code: "ES", name: "Spagna" },
  { code: "PT", name: "Portogallo" },
  { code: "AT", name: "Austria" },
  { code: "IE", name: "Irlanda" },
  { code: "LU", name: "Lussemburgo" },
  { code: "GR", name: "Grecia" },
  { code: "PL", name: "Polonia" },
  { code: "CZ", name: "Repubblica Ceca" },
  { code: "HU", name: "Ungheria" },
  { code: "RO", name: "Romania" },
  { code: "SK", name: "Slovacchia" },
  { code: "SI", name: "Slovenia" },
  { code: "HR", name: "Croazia" },
  { code: "BG", name: "Bulgaria" },
  { code: "LV", name: "Lettonia" },
  { code: "LT", name: "Lituania" },
  { code: "EE", name: "Estonia" },
  { code: "RS", name: "Serbia" },
  { code: "IS", name: "Islanda" },
  { code: "CY", name: "Cipro" },
  { code: "MT", name: "Malta" },
  { code: "LI", name: "Liechtenstein" },
  { code: "SG", name: "Singapore" },
  { code: "HK", name: "Hong Kong" },
  { code: "NZ", name: "Nuova Zelanda" },
  { code: "IL", name: "Israele" },
  { code: "CN", name: "Cina" },
  { code: "IN", name: "India" },
  { code: "BR", name: "Brasile" },
  { code: "KR", name: "Corea del Sud" },
  { code: "TW", name: "Taiwan" },
  { code: "MX", name: "Messico" },
  { code: "ZA", name: "Sudafrica" },
  { code: "RU", name: "Russia" },
  { code: "ID", name: "Indonesia" },
  { code: "TH", name: "Tailandia" },
  { code: "MY", name: "Malesia" },
  { code: "TR", name: "Turchia" },
  { code: "SA", name: "Arabia Saudita" },
  { code: "AE", name: "Emirati Arabi" },
  { code: "EG", name: "Egitto" },
  { code: "AR", name: "Argentina" },
  { code: "CL", name: "Cile" },
  { code: "CO", name: "Colombia" },
  { code: "PE", name: "Perù" },
  { code: "PH", name: "Filippine" },
  { code: "PK", name: "Pakistan" },
  { code: "VN", name: "Vietnam" },
  { code: "NG", name: "Nigeria" },
  { code: "KE", name: "Kenya" },
  { code: "MA", name: "Marocco" },
  { code: "KW", name: "Kuwait" },
  { code: "QA", name: "Qatar" },
  { code: "UA", name: "Ucraina" },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

async function getAsset(id: number): Promise<AssetFull> {
  const { data } = await api.get<AssetFull>(`/assets/${id}`);
  return data;
}

async function patchAsset(id: number, body: Partial<AssetFull> & { sectors_override?: WeightedSector[] | null; countries_override?: WeightedCountry[] | null }): Promise<AssetFull> {
  const { data } = await api.patch<AssetFull>(`/assets/${id}`, body);
  return data;
}

async function enrichAsset(id: number): Promise<AssetFull> {
  const { data } = await api.post<AssetFull>(`/assets/${id}/enrich`);
  return data;
}

function pctSum(items: { weight: number }[]) {
  return Math.round(items.reduce((s, i) => s + i.weight, 0) * 100);
}

// ── Tooltip ──────────────────────────────────────────────────────────────────

function Tooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex items-center ml-1">
      <Info
        className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 cursor-help transition-colors"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <span className="absolute left-5 top-0 z-50 w-56 rounded-lg bg-gray-900 text-white text-xs px-3 py-2 shadow-xl leading-relaxed whitespace-pre-line">
          {text}
        </span>
      )}
    </span>
  );
}

// ── SectorPicker ──────────────────────────────────────────────────────────────

function SectorPicker({ value, onChange }: { value: WeightedSector[]; onChange: (v: WeightedSector[]) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectedNames = new Set(value.map((s) => s.name));

  function toggle(name: string) {
    if (selectedNames.has(name)) {
      onChange(value.filter((s) => s.name !== name));
    } else {
      const equal = parseFloat((1 / (value.length + 1)).toFixed(4));
      const newItems = [...value.map((s) => ({ ...s, weight: equal })), { name, weight: equal }];
      onChange(newItems);
    }
  }

  function setWeight(name: string, pct: string) {
    const w = Math.min(1, Math.max(0, parseFloat(pct) / 100)) || 0;
    onChange(value.map((s) => (s.name === name ? { ...s, weight: w } : s)));
  }

  function remove(name: string) {
    onChange(value.filter((s) => s.name !== name));
  }

  const total = pctSum(value);
  const totalOk = total >= 99 && total <= 101;

  return (
    <div className="space-y-2" ref={ref}>
      {/* Selected chips + weight inputs */}
      {value.length > 0 && (
        <div className="space-y-1.5">
          {value.map((s) => (
            <div key={s.name} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-1.5">
              <span className="flex-1 text-xs font-medium text-gray-700 truncate">{s.name}</span>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={parseFloat((s.weight * 100).toFixed(2))}
                  onChange={(e) => setWeight(s.name, e.target.value)}
                  className="w-16 text-right text-xs rounded border border-gray-200 px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <span className="text-xs text-gray-400">%</span>
              </div>
              <button onClick={() => remove(s.name)} className="text-gray-300 hover:text-red-400 transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <div className={`text-xs text-right pr-1 font-medium ${totalOk ? "text-green-600" : "text-amber-600"}`}>
            Totale: {total}%{!totalOk && " (dovrebbe essere 100%)"}
          </div>
        </div>
      )}

      {/* Dropdown trigger */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-xs font-medium text-brand-600 hover:text-brand-700 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Aggiungi settore
          <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>

        {open && (
          <div className="absolute top-6 left-0 z-50 w-56 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
            <div className="max-h-52 overflow-y-auto py-1">
              {GICS_SECTORS.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggle(name)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-xs hover:bg-gray-50 transition-colors"
                >
                  <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${selectedNames.has(name) ? "bg-brand-600 border-brand-600" : "border-gray-300"}`}>
                    {selectedNames.has(name) && (
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </span>
                  <span className={selectedNames.has(name) ? "font-medium text-gray-900" : "text-gray-600"}>{name}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── CountryPicker ─────────────────────────────────────────────────────────────

function CountryPicker({ value, onChange }: { value: WeightedCountry[]; onChange: (v: WeightedCountry[]) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectedCodes = new Set(value.map((c) => c.code));

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return COUNTRY_LIST.filter(
      (c) => !selectedCodes.has(c.code) && (c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q))
    ).slice(0, 30);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, value]);

  function add(country: { code: string; name: string }) {
    const equal = parseFloat((1 / (value.length + 1)).toFixed(4));
    const updated = [...value.map((c) => ({ ...c, weight: equal })), { ...country, weight: equal }];
    onChange(updated);
    setQuery("");
  }

  function setWeight(code: string, pct: string) {
    const w = Math.min(1, Math.max(0, parseFloat(pct) / 100)) || 0;
    onChange(value.map((c) => (c.code === code ? { ...c, weight: w } : c)));
  }

  function remove(code: string) {
    onChange(value.filter((c) => c.code !== code));
  }

  const total = pctSum(value);
  const totalOk = total >= 99 && total <= 101;

  return (
    <div className="space-y-2" ref={ref}>
      {/* Selected rows */}
      {value.length > 0 && (
        <div className="space-y-1.5">
          {value.map((c) => (
            <div key={c.code} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-1.5">
              <span className="w-8 text-xs font-mono font-bold text-gray-500 flex-shrink-0">{c.code}</span>
              <span className="flex-1 text-xs font-medium text-gray-700 truncate">{c.name}</span>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={parseFloat((c.weight * 100).toFixed(2))}
                  onChange={(e) => setWeight(c.code, e.target.value)}
                  className="w-16 text-right text-xs rounded border border-gray-200 px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <span className="text-xs text-gray-400">%</span>
              </div>
              <button onClick={() => remove(c.code)} className="text-gray-300 hover:text-red-400 transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <div className={`text-xs text-right pr-1 font-medium ${totalOk ? "text-green-600" : "text-amber-600"}`}>
            Totale: {total}%{!totalOk && " (dovrebbe essere 100%)"}
          </div>
        </div>
      )}

      {/* Search + dropdown */}
      <div className="relative">
        <div
          className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 focus-within:ring-2 focus-within:ring-brand-500 bg-white cursor-text"
          onClick={() => setOpen(true)}
        >
          <Search className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder="Cerca paese..."
            className="flex-1 text-xs bg-transparent outline-none placeholder-gray-400"
          />
        </div>

        {open && filtered.length > 0 && (
          <div className="absolute top-10 left-0 z-50 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
            <div className="max-h-48 overflow-y-auto py-1">
              {filtered.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); add(c); setOpen(false); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-xs hover:bg-gray-50 transition-colors"
                >
                  <span className="w-8 font-mono font-bold text-gray-500 flex-shrink-0">{c.code}</span>
                  <span className="text-gray-700">{c.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Field ────────────────────────────────────────────────────────────────────

function Field({ label, tooltip, children }: { label: string; tooltip?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="flex items-center text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
        {tooltip && <Tooltip text={tooltip} />}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow";
const selectCls =
  "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow appearance-none cursor-pointer";

function SelectChevron() {
  return (
    <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
      <svg className="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

interface Props {
  assetId: number;
  initialData: {
    name: string;
    symbol: string;
    isin: string | null;
    asset_type: string;
    exchange: string;
    currency: string;
  };
  onClose: () => void;
  onSaved: () => void;
}

export function AssetEditModal({ assetId, initialData, onClose, onSaved }: Props) {
  const qc = useQueryClient();

  const [name, setName] = useState(initialData.name);
  const [symbol, setSymbol] = useState(initialData.symbol);
  const [yahooTicker, setYahooTicker] = useState("");
  const [isin, setIsin] = useState(initialData.isin ?? "");
  const [wkn, setWkn] = useState("");
  const [assetType, setAssetType] = useState<AssetType>((initialData.asset_type as AssetType) ?? "OTHER");
  const [exchange, setExchange] = useState<Exchange>((initialData.exchange as Exchange) ?? "OTHER");
  const [currency, setCurrency] = useState(initialData.currency);
  const [sectors, setSectors] = useState<WeightedSector[]>([]);
  const [countries, setCountries] = useState<WeightedCountry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Fetch full asset on open
  useEffect(() => {
    getAsset(assetId).then((a) => {
      if (a.yahoo_ticker) setYahooTicker(a.yahoo_ticker);
      if (a.wkn) setWkn(a.wkn);
      if (a.sectors_override?.length) setSectors(a.sectors_override);
      if (a.countries_override?.length) setCountries(a.countries_override);
      setLoaded(true);
    });
  }, [assetId]);

  const saveMut = useMutation({
    mutationFn: () =>
      patchAsset(assetId, {
        name,
        symbol,
        yahoo_ticker: yahooTicker || null,
        isin: isin || null,
        wkn: wkn || null,
        type: assetType,
        exchange,
        currency,
        sectors_override: sectors.length > 0 ? sectors : null,
        countries_override: countries.length > 0 ? countries : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holding-detail", assetId] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["country-allocation"] });
      qc.invalidateQueries({ queryKey: ["allocation"] });
      onSaved();
      onClose();
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Errore durante il salvataggio.");
    },
  });

  const enrichMut = useMutation({
    mutationFn: () => enrichAsset(assetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holding-detail", assetId] });
      qc.invalidateQueries({ queryKey: ["etf-holdings"] });
      qc.invalidateQueries({ queryKey: ["country-allocation"] });
      onSaved();
      onClose();
    },
    onError: () => setError("Errore durante l'enrichment."),
  });

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-base font-bold text-gray-900">Modifica titolo</h2>
            <p className="text-xs text-gray-400 mt-0.5">{initialData.symbol} · {initialData.isin ?? "nessun ISIN"}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700">{error}</div>
          )}

          {/* ── Anagrafica ─────────────────────────────────────────── */}
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Anagrafica</p>

          <Field label="Nome">
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome completo del titolo" />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Simbolo"
              tooltip={"Ticker usato nel portafoglio.\nEs. AAPL, SWDA, BTP2030"}
            >
              <input
                className={inputCls}
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="es. AAPL"
              />
            </Field>
            <Field
              label="Yahoo Ticker"
              tooltip={"Ticker Yahoo Finance per\nlo scaricamento dei prezzi.\nEs. AAPL, SWDA.MI, BTC-USD\n\nAggiungere il suffisso di borsa:\n.MI = Milano, .DE = Xetra"}
            >
              <input
                className={inputCls}
                value={yahooTicker}
                onChange={(e) => setYahooTicker(e.target.value)}
                placeholder="es. SWDA.MI"
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label="ISIN"
              tooltip={"Codice ISIN a 12 caratteri.\nEs. US0378331005\n\nPrimi 2 caratteri: codice paese\nSeguiti da 9 alfanumerici + 1 check digit"}
            >
              <input
                className={inputCls}
                value={isin}
                onChange={(e) => setIsin(e.target.value.toUpperCase())}
                placeholder="es. US0378331005"
                maxLength={12}
              />
            </Field>
            <Field
              label="WKN"
              tooltip={"Codice identificativo tedesco\n(Wertpapierkennnummer).\n6 caratteri alfanumerici.\nEs. 865985"}
            >
              <input
                className={inputCls}
                value={wkn}
                onChange={(e) => setWkn(e.target.value.toUpperCase())}
                placeholder="es. 865985"
                maxLength={6}
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Classe di asset">
              <div className="relative">
                <select className={selectCls} value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
                  {ASSET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <SelectChevron />
              </div>
            </Field>
            <Field label="Borsa">
              <div className="relative">
                <select className={selectCls} value={exchange} onChange={(e) => setExchange(e.target.value as Exchange)}>
                  {EXCHANGES.map((ex) => <option key={ex.value} value={ex.value}>{ex.label}</option>)}
                </select>
                <SelectChevron />
              </div>
            </Field>
          </div>

          <Field label="Valuta">
            <div className="relative w-1/2">
              <select className={selectCls} value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {COMMON_CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <SelectChevron />
            </div>
          </Field>

          {/* ── Composizione ───────────────────────────────────────── */}
          <div className="pt-2 border-t border-gray-100">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Composizione</p>

            <Field
              label="Settori"
              tooltip={"Settori GICS con peso percentuale.\nSeleziona uno o più settori e imposta il peso di ciascuno.\nI pesi dovrebbero sommare a 100%.\n\nEsempio per un ETF misto:\nInformation Technology 35%\nHealth Care 15%\nFinancials 20%"}
            >
              {!loaded ? (
                <div className="h-8 bg-gray-100 rounded-lg animate-pulse" />
              ) : (
                <SectorPicker value={sectors} onChange={setSectors} />
              )}
            </Field>
          </div>

          <Field
            label="Paesi"
            tooltip={"Allocazione geografica con peso percentuale.\nCerca il paese per nome o codice ISO2 (es. US, DE, JP).\nI pesi dovrebbero sommare a 100%.\n\nEsempio per un ETF globale:\nUS 65%\nJP 6%\nGB 4%"}
          >
            {!loaded ? (
              <div className="h-8 bg-gray-100 rounded-lg animate-pulse" />
            ) : (
              <CountryPicker value={countries} onChange={setCountries} />
            )}
          </Field>

          {/* ── Enrichment ─────────────────────────────────────────── */}
          <div className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 mt-2">
            <p className="text-xs font-medium text-gray-700 mb-1">Re-enrichment Yahoo Finance</p>
            <p className="text-xs text-gray-400 mb-3">
              Aggiorna prezzi storici, settori, holding e paesi da Yahoo Finance usando il Yahoo Ticker impostato sopra.
            </p>
            <button
              type="button"
              onClick={() => enrichMut.mutate()}
              disabled={enrichMut.isPending}
              className="flex items-center gap-2 text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${enrichMut.isPending ? "animate-spin" : ""}`} />
              {enrichMut.isPending ? "Enrichment in corso..." : "Esegui enrichment"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-3 flex-shrink-0 bg-white">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
            Annulla
          </button>
          <button
            type="button"
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold shadow-sm disabled:opacity-60 transition-colors"
          >
            <Save className="w-3.5 h-3.5" />
            {saveMut.isPending ? "Salvataggio..." : "Salva"}
          </button>
        </div>
      </div>
    </div>
  );
}
