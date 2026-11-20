import { useEffect, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { planningService, type PlanAssetType, type SearchResult } from "@/services/planning";

const TYPES: (PlanAssetType | "")[] = ["", "ETF", "STOCK", "BOND", "CRYPTO", "COMMODITY"];
const ISIN_RE = /^[A-Z]{2}[A-Z0-9]{10}$/;
export const MIN_CHARS = 3;

/**
 * Ricerca titoli per nome, ticker o ISIN: suggerimenti dopo 3 caratteri da Nextfolio
 * e da Yahoo Finance (anche titoli mai acquistati), filtro per tipo, tastiera ↑ ↓ Invio Esc.
 */
export function SecuritySearch({ onSelect, autoFocus }: { onSelect: (r: SearchResult) => void; autoFocus?: boolean }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<PlanAssetType | "">("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [error, setError] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const reqId = useRef(0);

  const q = query.trim();
  const isIsin = ISIN_RE.test(q.toUpperCase());

  useEffect(() => {
    if (q.length < MIN_CHARS) {
      setResults([]);
      setOpen(false);
      return;
    }
    const id = ++reqId.current;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await planningService.search(isIsin ? q.toUpperCase() : q, type || undefined);
        if (id !== reqId.current) return;   // risposta superata da una ricerca più recente
        setResults(res);
        setError(false);
        setActive(0);
        setOpen(true);
      } catch {
        if (id === reqId.current) setError(true);
      } finally {
        if (id === reqId.current) setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [q, type, isIsin]);

  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, []);

  const choose = (r: SearchResult) => {
    onSelect(r);
    setOpen(false);
    setQuery("");
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!open || !results.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(results[active]); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div ref={boxRef} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          autoFocus={autoFocus}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          onKeyDown={onKey}
          placeholder={t("planning.search.placeholder")}
          className="w-full pl-9 pr-9 py-2.5 border border-gray-300 dark:border-slate-600 rounded-xl text-sm bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
        />
        {loading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />}
      </div>

      <div className="flex flex-wrap gap-1.5 mt-2">
        {TYPES.map((ty) => (
          <button
            key={ty || "all"}
            type="button"
            onClick={() => setType(ty)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              type === ty ? "bg-brand-600 border-brand-600 text-white" : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            {ty ? t(`ai.assetTypes.${ty}`) : t("planning.search.allTypes")}
          </button>
        ))}
        {q.length > 0 && q.length < MIN_CHARS && (
          <span className="text-xs text-gray-400 self-center ml-1">{t("planning.search.minChars", { n: MIN_CHARS })}</span>
        )}
        {isIsin && <span className="text-xs text-brand-600 self-center ml-1">{t("planning.search.isinDetected")}</span>}
      </div>

      {open && (
        <div className="absolute z-30 mt-1 w-full bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-lg max-h-96 overflow-y-auto" role="listbox">
          {error ? (
            <p className="px-4 py-3 text-sm text-red-600">{t("planning.search.error")}</p>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400">{t("planning.search.noResults")}</p>
          ) : (
            results.map((r, i) => (
              <button
                key={`${r.source}-${r.asset_id ?? r.symbol}`}
                type="button"
                role="option"
                aria-selected={i === active}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(r)}
                className={`w-full text-left px-4 py-2.5 flex items-center gap-3 border-b border-gray-50 dark:border-slate-800 last:border-0 ${
                  i === active ? "bg-brand-50 dark:bg-slate-800" : ""
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 dark:text-slate-100 truncate">{r.name}</p>
                  <p className="text-xs text-gray-400 truncate">
                    {[r.ticker, r.isin, r.exchange_label ?? r.exchange, r.currency].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <span className="text-[10px] uppercase tracking-wide text-gray-400">{t(`ai.assetTypes.${r.type}`)}</span>
                {r.in_portfolio ? (
                  <span className="text-[10px] rounded-full bg-green-100 text-green-700 px-2 py-0.5">{t("planning.search.owned")}</span>
                ) : r.in_watchlist ? (
                  <span className="text-[10px] rounded-full bg-sky-100 text-sky-700 px-2 py-0.5">{t("planning.search.watched")}</span>
                ) : r.source === "yahoo" ? (
                  <span className="text-[10px] rounded-full bg-gray-100 text-gray-500 px-2 py-0.5">{t("planning.search.new")}</span>
                ) : null}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
