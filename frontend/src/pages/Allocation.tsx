import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieIcon, ChevronDown, ChevronRight, Pencil, X, Check, Globe } from "lucide-react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { TopBar } from "@/components/layout/TopBar";
import { portfolioService, type AllocationItem, type PositionOut, type ETFHoldingOut, type CountryItem } from "@/services/portfolio";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/services/api";

// ── Costanti ──────────────────────────────────────────────────────────────────

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
  "#ef4444", "#06b6d4", "#84cc16", "#f97316",
  "#ec4899", "#14b8a6", "#a855f7", "#fb923c",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, d = 2) {
  return v.toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function buildHoldingItems(positions: PositionOut[], total: number): AllocationItem[] {
  if (total <= 0) return [];
  return positions
    .filter((p) => p.current_value_eur != null && p.current_value_eur > 0)
    .map((p) => ({
      label: p.symbol,
      value_eur: p.current_value_eur!,
      pct: Math.round((p.current_value_eur! / total) * 1000) / 10,
      count: 1,
    }))
    .sort((a, b) => b.value_eur - a.value_eur);
}

function buildExchangeItems(positions: PositionOut[], total: number): AllocationItem[] {
  if (total <= 0) return [];
  const map = new Map<string, number>();
  for (const p of positions) {
    if (p.current_value_eur) {
      map.set(p.exchange, (map.get(p.exchange) ?? 0) + p.current_value_eur);
    }
  }
  return [...map.entries()]
    .map(([label, value_eur]) => ({
      label,
      value_eur: Math.round(value_eur * 100) / 100,
      pct: Math.round((value_eur / total) * 1000) / 10,
      count: 0,
    }))
    .sort((a, b) => b.value_eur - a.value_eur);
}

// ── Sub-componenti ────────────────────────────────────────────────────────────

function SmallDonutCard({ title, items }: { title: string; items: AllocationItem[] }) {
  if (!items.length) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="flex flex-col sm:flex-row gap-3 items-center sm:items-start">
        <ResponsiveContainer width={130} height={130}>
          <PieChart>
            <Pie
              data={items}
              dataKey="value_eur"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={60}
              strokeWidth={1}
              stroke="#f8fafc"
            >
              {items.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => [`€ ${fmt(v)}`, ""]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="w-full sm:flex-1 space-y-1.5 min-w-0">
          {items.map((item, i) => (
            <div key={item.label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="text-xs text-gray-600 truncate flex-1">{item.label}</span>
              <span className="text-xs font-semibold text-gray-800 tabular-nums">{item.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── ETF Holdings Table ────────────────────────────────────────────────────────

function EtfHoldingRow({
  etf,
  isSuperAdmin,
  onEdit,
}: {
  etf: ETFHoldingOut;
  isSuperAdmin: boolean;
  onEdit: (etf: ETFHoldingOut) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className="hover:bg-gray-50 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
            )}
            <span className="text-sm font-semibold text-gray-900">{etf.symbol}</span>
            {etf.is_override && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">
                override
              </span>
            )}
            {etf.countries_override && etf.countries_override.length > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium flex items-center gap-0.5">
                <Globe className="w-2.5 h-2.5" />paesi
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-xs text-gray-500 hidden sm:table-cell truncate max-w-[200px]">
          {etf.name}
        </td>
        <td className="px-4 py-3 text-sm text-right tabular-nums text-gray-700">
          {etf.value_eur != null ? `€ ${fmt(etf.value_eur)}` : "—"}
        </td>
        <td className="px-4 py-3 text-xs text-right text-gray-400">
          {etf.holdings.length} holdings
        </td>
        {isSuperAdmin && (
          <td className="px-4 py-3 text-right">
            <button
              className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-700"
              onClick={(e) => { e.stopPropagation(); onEdit(etf); }}
              title="Override manuale"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
          </td>
        )}
      </tr>
      {expanded && (
        <tr>
          <td colSpan={isSuperAdmin ? 5 : 4} className="px-4 pb-3 pt-0">
            <div className="ml-5 space-y-2">

              {/* Holdings table */}
              {etf.holdings.length > 0 ? (
                <div className="rounded-lg border border-gray-100 overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-gray-500">
                        <th className="px-3 py-1.5 text-left font-medium">Simbolo</th>
                        <th className="px-3 py-1.5 text-left font-medium hidden sm:table-cell">Nome</th>
                        <th className="px-3 py-1.5 text-right font-medium">Peso</th>
                      </tr>
                    </thead>
                    <tbody>
                      {etf.holdings.slice(0, 20).map((h, i) => (
                        <tr key={i} className="border-t border-gray-100">
                          <td className="px-3 py-1.5 font-medium text-gray-700">{h.symbol}</td>
                          <td className="px-3 py-1.5 text-gray-500 hidden sm:table-cell truncate max-w-[180px]">{h.name}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums text-gray-700">
                            {(h.weight * 100).toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                      {etf.holdings.length > 20 && (
                        <tr className="border-t border-gray-100">
                          <td colSpan={3} className="px-3 py-1.5 text-gray-400 text-center">
                            +{etf.holdings.length - 20} altri
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic py-1">
                  Nessun holding disponibile.{isSuperAdmin ? " Usa l'override manuale per aggiungerne." : ""}
                </p>
              )}

              {/* Countries breakdown */}
              {etf.countries_override && etf.countries_override.length > 0 && (
                <div className="rounded-lg border border-blue-100 bg-blue-50/40 overflow-hidden">
                  <div className="px-3 py-1.5 text-[10px] font-semibold text-blue-600 uppercase tracking-wide border-b border-blue-100">
                    Allocazione geografica
                  </div>
                  <table className="w-full text-xs">
                    <tbody>
                      {etf.countries_override.slice(0, 10).map((c, i) => (
                        <tr key={i} className={i > 0 ? "border-t border-blue-100/60" : ""}>
                          <td className="px-3 py-1.5 font-medium text-gray-700">{c.code}</td>
                          <td className="px-3 py-1.5 text-gray-500 hidden sm:table-cell">{c.name}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums text-gray-700">
                            {(c.weight * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                      {etf.countries_override.length > 10 && (
                        <tr className="border-t border-blue-100/60">
                          <td colSpan={3} className="px-3 py-1.5 text-gray-400 text-center">
                            +{etf.countries_override.length - 10} altri
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function EtfHoldingsSection({ isSuperAdmin }: { isSuperAdmin: boolean }) {
  const [editTarget, setEditTarget] = useState<ETFHoldingOut | null>(null);

  const { data: etfHoldings, isLoading } = useQuery({
    queryKey: ["etf-holdings"],
    queryFn: portfolioService.getEtfHoldings,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return null;
  if (!etfHoldings || etfHoldings.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Holdings ETF / Fondi</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Composizione interna dei fondi in portafoglio
          </p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-xs text-gray-500 bg-gray-50 border-b border-gray-100">
              <th className="px-4 py-2 text-left font-medium">Simbolo</th>
              <th className="px-4 py-2 text-left font-medium hidden sm:table-cell">Nome</th>
              <th className="px-4 py-2 text-right font-medium">Valore</th>
              <th className="px-4 py-2 text-right font-medium">N° holdings</th>
              {isSuperAdmin && <th className="px-4 py-2 w-10" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {etfHoldings.map((etf) => (
              <EtfHoldingRow
                key={etf.asset_id}
                etf={etf}
                isSuperAdmin={isSuperAdmin}
                onEdit={setEditTarget}
              />
            ))}
          </tbody>
        </table>
      </div>

      {editTarget && (
        <OverrideModal
          etf={editTarget}
          onClose={() => setEditTarget(null)}
        />
      )}
    </div>
  );
}

// ── Override Modal ────────────────────────────────────────────────────────────

function OverrideModal({ etf, onClose }: { etf: ETFHoldingOut; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"holdings" | "paesi">("holdings");

  const [holdingsText, setHoldingsText] = useState<string>(() => {
    if (etf.is_override && etf.holdings.length > 0) {
      return etf.holdings
        .map((h) => `${h.symbol}|${h.name}|${(h.weight * 100).toFixed(4)}`)
        .join("\n");
    }
    return "";
  });

  const [countriesText, setCountriesText] = useState<string>(() => {
    if (etf.countries_override && etf.countries_override.length > 0) {
      return (etf.countries_override as CountryItem[])
        .map((c) => `${c.code}|${(c.weight * 100).toFixed(2)}`)
        .join("\n");
    }
    return "";
  });

  const mutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const { data } = await api.patch(`/admin/assets/${etf.asset_id}/profile`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["etf-holdings"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["country-allocation"] });
      onClose();
    },
  });

  function handleSave() {
    const payload: Record<string, unknown> = {};

    if (!holdingsText.trim()) {
      payload.holdings_override = null;
    } else {
      payload.holdings_override = holdingsText.trim().split("\n").filter(Boolean).map((line) => {
        const [sym, name, w] = line.split("|").map((s) => s.trim());
        return { symbol: sym ?? "", name: name ?? "", weight: parseFloat(w ?? "0") / 100 };
      });
    }

    if (!countriesText.trim()) {
      payload.countries_override = null;
    } else {
      payload.countries_override = countriesText.trim().split("\n").filter(Boolean).map((line) => {
        const [code, w] = line.split("|").map((s) => s.trim());
        return { code: (code ?? "").toUpperCase(), name: code ?? "", weight: parseFloat(w ?? "0") / 100 };
      });
    }

    mutation.mutate(payload);
  }

  const tabCls = (t: "holdings" | "paesi") =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-700"
    }`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Override dati — {etf.symbol}</h2>
            <p className="text-xs text-gray-400 mt-0.5">{etf.name}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex border-b border-gray-100 px-6">
          <button className={tabCls("holdings")} onClick={() => setTab("holdings")}>Holdings</button>
          <button className={tabCls("paesi")} onClick={() => setTab("paesi")}>
            <span className="flex items-center gap-1.5"><Globe className="w-3.5 h-3.5" />Paesi</span>
          </button>
        </div>

        <div className="px-6 py-4 space-y-3">
          {tab === "holdings" ? (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                Una per riga: <code className="bg-gray-100 px-1 rounded">SIMBOLO|Nome|peso%</code>
              </label>
              <textarea
                className="w-full h-52 text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                value={holdingsText}
                onChange={(e) => setHoldingsText(e.target.value)}
                placeholder={"AAPL|Apple Inc|6.5\nMSFT|Microsoft Corp|6.2\n..."}
              />
              <p className="text-xs text-gray-400 mt-1">Lascia vuoto per rimuovere l&apos;override.</p>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                Una per riga: <code className="bg-gray-100 px-1 rounded">ISO2|peso%</code>
                <span className="ml-2 text-gray-400">(es. US|65.2, JP|6.1)</span>
              </label>
              <textarea
                className="w-full h-52 text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                value={countriesText}
                onChange={(e) => setCountriesText(e.target.value)}
                placeholder={"US|65.20\nJP|6.10\nGB|4.20\nFR|3.10\n..."}
              />
              <p className="text-xs text-gray-400 mt-1">Lascia vuoto per rimuovere. I pesi vengono normalizzati automaticamente.</p>
            </div>
          )}
          {mutation.isError && <p className="text-xs text-red-600">Errore nel salvataggio. Riprova.</p>}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
            Annulla
          </button>
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-60"
          >
            <Check className="w-4 h-4" />
            {mutation.isPending ? "Salvataggio..." : "Salva Override"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── World Map ─────────────────────────────────────────────────────────────────

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

const ISO2_NUMERIC: Record<string, string> = {
  US: "840", DE: "276", FR: "250", GB: "826", JP: "392", CA: "124",
  CH: "756", AU: "036", NL: "528", SE: "752", DK: "208", NO: "578",
  FI: "246", BE: "056", IT: "380", ES: "724", PT: "620", AT: "040",
  IE: "372", SG: "702", HK: "344", NZ: "554", IL: "376",
  CN: "156", IN: "356", BR: "076", KR: "410", TW: "158", MX: "484",
  ZA: "710", RU: "643", ID: "360", TH: "764", MY: "458", PL: "616",
  TR: "792", SA: "682", AE: "784", EG: "818", AR: "032", CL: "152",
  CO: "170", PE: "604", PH: "608", CZ: "203", HU: "348", GR: "300",
  MA: "504", KW: "414", QA: "634", LU: "442", RO: "642", UA: "804",
  PK: "586", VN: "704", NG: "566", KE: "404",
  SK: "703", LV: "428", LT: "440", SI: "705", EE: "233",
  HR: "191", BG: "100", RS: "688", BA: "070", MK: "807",
  IS: "352", CY: "196", MT: "470", LI: "438",
};

function _tealScale(pct: number): string {
  if (!pct || pct <= 0) return "#f1f5f9";
  const t = Math.min(Math.sqrt(pct / 55), 1);
  const r = Math.round(224 + (3 - 224) * t);
  const g = Math.round(242 + (105 - 242) * t);
  const b = Math.round(254 + (161 - 254) * t);
  return `rgb(${r},${g},${b})`;
}

function WorldMapSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["country-allocation"],
    queryFn: () => portfolioService.getCountryAllocation(),
    staleTime: 5 * 60 * 1000,
  });

  const [tooltip, setTooltip] = useState<{ name: string; pct: number; x: number; y: number } | null>(null);

  const numericToData = useMemo(() => {
    if (!data?.countries) return {} as Record<string, { name: string; pct: number }>;
    const map: Record<string, { name: string; pct: number }> = {};
    for (const c of data.countries) {
      const numeric = ISO2_NUMERIC[c.code];
      if (numeric) map[numeric] = { name: c.name, pct: c.pct };
    }
    return map;
  }, [data]);

  if (isLoading) return null;

  const hasData = data && data.countries.length > 0;
  const { totals } = data ?? { totals: { developed_pct: 0, emerging_pct: 0, other_pct: 0, no_data_pct: 100 } };
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Mappa Geografica</h3>
      {!hasData ? (
        <div className="rounded-lg bg-slate-50 flex items-center justify-center h-40 text-sm text-gray-400">
          Nessun dato geografico disponibile. Avvia l&apos;arricchimento degli asset per popolare la mappa.
        </div>
      ) : (
      <div
        className="relative rounded-lg overflow-hidden bg-slate-50"
        onMouseLeave={() => setTooltip(null)}
      >
        <ComposableMap
          projectionConfig={{ scale: 140, center: [10, 10] }}
          style={{ width: "100%", height: "auto" }}
          height={300}
        >
          <Geographies geography={GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const d = numericToData[String(geo.id)];
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={_tealScale(d?.pct ?? 0)}
                    stroke="#ffffff"
                    strokeWidth={0.4}
                    style={{
                      default: { outline: "none" },
                      hover: { outline: "none", opacity: 0.75 },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(evt) => {
                      if (d) setTooltip({ name: d.name, pct: d.pct, x: (evt as unknown as MouseEvent).clientX, y: (evt as unknown as MouseEvent).clientY });
                    }}
                    onMouseMove={(evt) => {
                      if (d) setTooltip({ name: d.name, pct: d.pct, x: (evt as unknown as MouseEvent).clientX, y: (evt as unknown as MouseEvent).clientY });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })
            }
          </Geographies>
        </ComposableMap>
        {tooltip && (
          <div
            className="fixed z-50 pointer-events-none bg-gray-900 text-white text-xs rounded px-2 py-1 shadow-lg"
            style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}
          >
            <span className="font-medium">{tooltip.name}</span>
            <span className="ml-2 text-blue-200">{fmt(tooltip.pct, 2)}%</span>
          </div>
        )}
      </div>
      )}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
        <div>
          <div className="text-xs text-gray-400">Mercati Sviluppati</div>
          <div className="text-sm font-bold text-blue-700">{fmt(totals.developed_pct, 2)} %</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Mercati Emergenti</div>
          <div className="text-sm font-bold text-emerald-700">{fmt(totals.emerging_pct, 2)} %</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Altri Mercati</div>
          <div className="text-sm font-bold text-amber-700">{fmt(totals.other_pct, 2)} %</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Dati non disponibili</div>
          <div className="text-sm font-bold text-gray-400">{fmt(totals.no_data_pct, 2)} %</div>
        </div>
      </div>
    </div>
  );
}

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Allocation() {
  const { isSuperAdmin } = useAuth();

  const { data: dashboard } = useQuery({
    queryKey: ["portfolio-dashboard"],
    queryFn: portfolioService.getDashboard,
    staleTime: 5 * 60 * 1000,
  });
  const allocation = dashboard?.allocation;
  const positions = dashboard?.positions ?? [];

  const total = allocation?.total_value_eur ?? 0;
  const holdingItems = buildHoldingItems(positions, total);
  const exchangeItems = buildExchangeItems(positions, total);

  const continentItems = (allocation?.by_continent ?? []).filter(
    (c) => c.label !== "Altro" || (allocation?.by_continent ?? []).every((x) => x.label === "Altro")
  );

  const isEmpty = !allocation || total === 0;

  return (
    <>
      <TopBar title="Allocazioni" />
      <main className="flex-1 p-4 md:p-6 space-y-4 md:space-y-6">

        {isEmpty ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
            <PieIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Aggiungi transazioni per vedere l&apos;allocazione.</p>
          </div>
        ) : (
          <>
            {/* Quota del patrimonio netto */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-sm font-medium text-gray-600">
                  Quota del patrimonio netto
                  <span className="ml-2 text-xs text-amber-500 font-semibold">● Portafoglio</span>
                </span>
                <span className="text-sm font-bold text-gray-900 tabular-nums">100,00 %</span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full bg-emerald-400" style={{ width: "100%" }} />
              </div>
              <div className="mt-2 text-xs text-gray-400 text-right">
                Totale: <span className="font-semibold text-gray-700">€ {fmt(total)}</span>
              </div>
            </div>

            {/* Per Piattaforma / Valuta / Asset Class / Borsa */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <SmallDonutCard title="Per Piattaforma" items={allocation.by_account} />
              <SmallDonutCard title="Per Valuta" items={allocation.by_currency} />
              <SmallDonutCard title="Per Classe di Asset" items={allocation.by_type} />
              {exchangeItems.length > 0 && (
                <SmallDonutCard title="Per Borsa" items={exchangeItems} />
              )}
            </div>

            {/* Mappa Geografica — primo */}
            <WorldMapSection />

            {/* Per Settore / Per Continente / Per Holding — stessa riga */}
            {(allocation.by_sector?.filter(s => s.label !== "Non classificato").length > 0 ||
              continentItems.length > 0 ||
              holdingItems.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {allocation.by_sector && allocation.by_sector.filter(s => s.label !== "Non classificato").length > 0 && (
                  <SmallDonutCard
                    title="Per Settore"
                    items={allocation.by_sector.filter(s => s.label !== "Non classificato")}
                  />
                )}
                {continentItems.length > 0 && (
                  <SmallDonutCard title="Per Continente" items={continentItems} />
                )}
                {holdingItems.length > 0 && (
                  <SmallDonutCard title="Per Holding" items={holdingItems} />
                )}
              </div>
            )}

            {/* ETF Holdings look-through */}
            <EtfHoldingsSection isSuperAdmin={isSuperAdmin} />
          </>
        )}
      </main>
    </>
  );
}
