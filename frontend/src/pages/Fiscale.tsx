import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, TrendingDown, TrendingUp, Wallet, AlertCircle, Info, Calculator, History } from "lucide-react";
import { taxService, type AnnualTaxReport, type TaxEvent, type SimulateSellOut } from "@/services/tax";
import { portfolioService } from "@/services/portfolio";

// ── Helpers ──────────────────────────────────────────────────────────────────

const eur = (v: number) =>
  v.toLocaleString("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

function sign(v: number) {
  if (v > 0.005) return "+";
  if (v < -0.005) return "−";
  return "";
}

function GainBadge({ value }: { value: number }) {
  const positive = value >= 0;
  return (
    <span className={`font-medium ${positive ? "text-green-600" : "text-red-600"}`}>
      {sign(value)}{eur(Math.abs(value))}
    </span>
  );
}

function Bracket({
  label,
  rate,
  gains,
  losses,
  carryApplied,
  netTaxable,
  tax,
  newCarry,
  priorEntries,
}: {
  label: string;
  rate: number;
  gains: number;
  losses: number;
  carryApplied: number;
  netTaxable: number;
  tax: number;
  newCarry: number;
  priorEntries: { year: number; amount: number; expires_year: number }[];
}) {
  const hasPrior = priorEntries.length > 0;
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-sm font-semibold text-gray-700">{label}</span>
          <span className="ml-2 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
            Aliquota {pct(rate)}
          </span>
        </div>
        <p className="text-xl font-bold text-gray-900">{eur(tax)}</p>
      </div>

      <div className="space-y-2 text-sm">
        <Row label="Plusvalenze lorde" value={gains} positive />
        <Row label="Minusvalenze" value={-losses} />
        {carryApplied > 0 && (
          <Row label="Zainetto fiscale applicato" value={-carryApplied} />
        )}
        <div className="border-t border-dashed border-gray-200 my-2" />
        <Row label="Imponibile netto" value={netTaxable} positive={netTaxable > 0} bold />
        <Row label={`Imposta (${pct(rate)})`} value={tax} bold />
      </div>

      {newCarry > 0 && (
        <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            <strong>{eur(newCarry)}</strong> di minusvalenze portate agli anni successivi (scadono tra 4 anni)
          </span>
        </div>
      )}

      {hasPrior && (
        <div className="mt-4">
          <p className="text-xs font-medium text-gray-500 mb-1">Zainetto disponibile</p>
          <div className="space-y-1">
            {priorEntries.map((e) => (
              <div key={e.year} className="flex justify-between text-xs text-gray-600">
                <span>Perdita {e.year} (scade {e.expires_year})</span>
                <span className="font-medium">{eur(e.amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  positive,
  bold,
}: {
  label: string;
  value: number;
  positive?: boolean;
  bold?: boolean;
}) {
  const color = value === 0 ? "text-gray-500" : positive ? "text-green-600" : "text-red-600";
  return (
    <div className={`flex justify-between ${bold ? "font-semibold" : ""}`}>
      <span className="text-gray-600">{label}</span>
      <span className={color}>{eur(value)}</span>
    </div>
  );
}

const TX_TYPE_LABEL: Record<string, string> = {
  SELL: "Vendita",
  DIVIDEND: "Dividendo",
  COUPON: "Cedola",
  INTEREST: "Interesse",
};

const BRACKET_LABEL: Record<string, string> = {
  standard: "26%",
  government_bond: "12.5%",
};

function EventsTable({ events }: { events: TaxEvent[] }) {
  const [open, setOpen] = useState(false);
  if (events.length === 0) return null;

  const sorted = [...events].sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-gray-800 hover:bg-gray-50 transition-colors"
      >
        <span>Dettaglio eventi ({events.length})</span>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="overflow-x-auto border-t border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left text-gray-600">
                <th className="px-4 py-3 font-medium">Data</th>
                <th className="px-4 py-3 font-medium">Asset</th>
                <th className="px-4 py-3 font-medium">Tipo</th>
                <th className="px-4 py-3 font-medium">Quantità</th>
                <th className="px-4 py-3 font-medium text-right">Costo</th>
                <th className="px-4 py-3 font-medium text-right">Ricavo</th>
                <th className="px-4 py-3 font-medium text-right">Gain/Loss</th>
                <th className="px-4 py-3 font-medium text-right">Aliquota</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.map((ev, i) => (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {new Date(ev.date).toLocaleDateString("it-IT")}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-[180px] truncate">
                    {ev.asset_name}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{TX_TYPE_LABEL[ev.tx_type] ?? ev.tx_type}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {ev.quantity != null ? ev.quantity.toLocaleString("it-IT") : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500">
                    {ev.cost_eur != null ? eur(ev.cost_eur) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">{eur(ev.proceeds_eur)}</td>
                  <td className="px-4 py-3 text-right">
                    <GainBadge value={ev.gain_loss_eur} />
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-500">
                    {BRACKET_LABEL[ev.tax_bracket] ?? ev.tax_bracket}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function IncomeSection({ report }: { report: AnnualTaxReport }) {
  const total =
    report.dividends_eur + report.coupons_govt_eur + report.coupons_standard_eur + report.interests_eur;
  if (total < 0.01) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-3">
        <p className="text-sm font-semibold text-gray-700">Redditi da capitale</p>
        <div className="group relative">
          <Info className="w-3.5 h-3.5 text-gray-400 cursor-help" />
          <div className="absolute left-4 bottom-5 z-10 hidden group-hover:block w-64 bg-gray-800 text-white text-xs rounded-lg p-2 shadow-lg">
            In regime amministrato la ritenuta è applicata alla fonte dal broker. Questi importi sono
            mostrati a titolo informativo.
          </div>
        </div>
      </div>
      <div className="space-y-2 text-sm">
        {report.dividends_eur > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Dividendi azionari (26%)</span>
            <span className="font-medium">{eur(report.dividends_eur)}</span>
          </div>
        )}
        {report.coupons_govt_eur > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Cedole titoli di Stato (12.5%)</span>
            <span className="font-medium">{eur(report.coupons_govt_eur)}</span>
          </div>
        )}
        {report.coupons_standard_eur > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Cedole obbligazioni societarie (26%)</span>
            <span className="font-medium">{eur(report.coupons_standard_eur)}</span>
          </div>
        )}
        {report.interests_eur > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Interessi (26%)</span>
            <span className="font-medium">{eur(report.interests_eur)}</span>
          </div>
        )}
        <div className="border-t border-dashed border-gray-200 pt-2 flex justify-between font-semibold">
          <span className="text-gray-700">Totale redditi</span>
          <span>{eur(total)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Simulatore vendita ────────────────────────────────────────────────────────

function SimResultCard({
  label,
  value,
  positive,
  negative,
  highlight,
}: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
  highlight?: boolean;
}) {
  const valueClass = highlight
    ? "text-brand-700 font-bold"
    : positive
    ? "text-green-600 font-semibold"
    : negative
    ? "text-red-600 font-semibold"
    : "text-gray-900 font-semibold";

  return (
    <div className={`rounded-lg px-3 py-2.5 ${highlight ? "bg-brand-50 border border-brand-200" : "bg-gray-50"}`}>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-sm ${valueClass}`}>{value}</p>
    </div>
  );
}

function SellSimulator() {
  const [assetId, setAssetId] = useState<number | "">("");
  const [quantityStr, setQuantityStr] = useState("");
  const [result, setResult] = useState<SimulateSellOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: positions = [] } = useQuery({
    queryKey: ["positions"],
    queryFn: portfolioService.getPositions,
  });

  const selectedPos = positions.find((p) => p.asset_id === assetId);
  const maxQty = selectedPos?.quantity ?? null;

  async function handleSimulate() {
    if (!assetId || !quantityStr) return;
    const qty = parseFloat(quantityStr.replace(",", "."));
    if (isNaN(qty) || qty <= 0) return;
    setLoading(true);
    setError(null);
    try {
      const out = await taxService.simulateSell(assetId as number, qty);
      setResult(out);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Errore nella simulazione");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-4">
        <Calculator className="w-4 h-4 text-brand-600" />
        <h2 className="text-sm font-semibold text-gray-700">Simulatore vendita</h2>
        <span className="text-xs text-gray-400">— impatto fiscale stimato (FIFO)</span>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <select
          value={assetId}
          onChange={(e) => {
            setAssetId(e.target.value ? Number(e.target.value) : "");
            setResult(null);
            setQuantityStr("");
          }}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
        >
          <option value="">Seleziona un asset...</option>
          {positions.map((p) => (
            <option key={p.asset_id} value={p.asset_id}>
              {p.symbol} — {p.name} ({p.quantity.toLocaleString("it-IT")} quote)
            </option>
          ))}
        </select>

        <div className="relative sm:w-36">
          <input
            type="number"
            inputMode="decimal"
            placeholder="Quantità"
            value={quantityStr}
            onChange={(e) => {
              setQuantityStr(e.target.value);
              setResult(null);
            }}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          {maxQty != null && (
            <button
              onClick={() => setQuantityStr(String(maxQty))}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-brand-600 hover:text-brand-700 font-medium"
            >
              max
            </button>
          )}
        </div>

        <button
          onClick={handleSimulate}
          disabled={!assetId || !quantityStr || loading}
          className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Calcolo..." : "Calcola"}
        </button>
      </div>

      {error && (
        <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-700">
              {result.asset_name}{" "}
              <span className="text-gray-400 font-normal">
                × {result.quantity.toLocaleString("it-IT")} quote
              </span>
            </p>
            <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
              {result.tax_bracket === "government_bond" ? "Titoli di Stato 12.5%" : "Standard 26%"}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <SimResultCard label="Prezzo corrente" value={eur(result.current_price_eur)} />
            <SimResultCard label="Ricavo vendita" value={eur(result.proceeds_eur)} />
            <SimResultCard label="Costo base FIFO" value={eur(result.cost_basis_eur)} />
            <SimResultCard
              label="Gain / Loss"
              value={(result.gain_loss_eur >= 0 ? "+" : "") + eur(result.gain_loss_eur)}
              positive={result.gain_loss_eur > 0.005}
              negative={result.gain_loss_eur < -0.005}
            />
            <SimResultCard
              label="Imposta stimata"
              value={eur(result.estimated_tax_eur)}
              negative={result.estimated_tax_eur > 0}
            />
            <SimResultCard
              label="Netto dopo tasse"
              value={eur(result.net_proceeds_eur)}
              highlight
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Storico minusvalenze ──────────────────────────────────────────────────────

function CarryforwardHistory({ years }: { years: number[] }) {
  const [open, setOpen] = useState(false);

  // Carica i report per tutti gli anni disponibili (lazy)
  const queries = useQuery({
    queryKey: ["tax-carryforward-history", years],
    queryFn: async () => {
      const reports = await Promise.all(years.map((y) => taxService.getReport(y)));
      return reports;
    },
    enabled: open && years.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const reports = queries.data ?? [];

  // Costruisce la storia delle minusvalenze anno per anno
  const history = years
    .map((year, i) => {
      const r = reports[i];
      if (!r) return null;
      return {
        year,
        losses_std: r.losses_standard,
        losses_govt: r.losses_govt,
        carry_applied_std: r.carryforward_applied_standard,
        carry_applied_govt: r.carryforward_applied_govt,
        carry_new_std: r.new_carryforward_standard,
        carry_new_govt: r.new_carryforward_govt,
        available_std: r.prior_carryforward_standard.reduce((s, e) => s + e.amount, 0),
        available_govt: r.prior_carryforward_govt.reduce((s, e) => s + e.amount, 0),
        expiring: r.prior_carryforward_standard
          .filter((e) => e.expires_year === year + 1)
          .reduce((s, e) => s + e.amount, 0),
      };
    })
    .filter(Boolean);

  if (years.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-4"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-semibold text-gray-700">Storico minusvalenze multi-anno</span>
          <span className="text-xs text-gray-400">(Art. 68 TUIR — compensabili entro 4 anni)</span>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-gray-100">
          {queries.isLoading ? (
            <div className="px-5 py-6 text-center text-sm text-gray-400">Caricamento...</div>
          ) : history.length === 0 ? (
            <div className="px-5 py-6 text-center text-sm text-gray-400">Nessun dato.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100 text-xs font-medium text-gray-400 uppercase">
                    <th className="px-5 py-2.5 text-left">Anno</th>
                    <th className="px-5 py-2.5 text-right">Minus. maturate (std)</th>
                    <th className="px-5 py-2.5 text-right">Minus. maturate (TdS)</th>
                    <th className="px-5 py-2.5 text-right">Compensate (std)</th>
                    <th className="px-5 py-2.5 text-right">Residuo disponibile</th>
                    <th className="px-5 py-2.5 text-right">In scadenza</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {[...history].reverse().map((h) => h && (
                    <tr key={h.year} className="hover:bg-gray-50">
                      <td className="px-5 py-3 font-semibold text-gray-900">{h.year}</td>
                      <td className={`px-5 py-3 text-right text-xs ${h.losses_std > 0 ? "text-red-600 font-medium" : "text-gray-300"}`}>
                        {h.losses_std > 0 ? `− ${eur(h.losses_std)}` : "—"}
                      </td>
                      <td className={`px-5 py-3 text-right text-xs ${h.losses_govt > 0 ? "text-red-500" : "text-gray-300"}`}>
                        {h.losses_govt > 0 ? `− ${eur(h.losses_govt)}` : "—"}
                      </td>
                      <td className={`px-5 py-3 text-right text-xs ${h.carry_applied_std > 0 ? "text-green-600 font-medium" : "text-gray-300"}`}>
                        {h.carry_applied_std > 0 ? `+ ${eur(h.carry_applied_std)}` : "—"}
                      </td>
                      <td className={`px-5 py-3 text-right text-xs font-semibold ${(h.available_std + h.available_govt) > 0 ? "text-amber-600" : "text-gray-300"}`}>
                        {(h.available_std + h.available_govt) > 0
                          ? eur(h.available_std + h.available_govt)
                          : "—"}
                      </td>
                      <td className={`px-5 py-3 text-right text-xs ${h.expiring > 0 ? "text-red-500 font-semibold" : "text-gray-300"}`}>
                        {h.expiring > 0 ? `⚠ ${eur(h.expiring)}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-5 py-3 text-xs text-gray-400 bg-gray-50 border-t border-gray-100">
                Le minusvalenze standard (26%) e titoli di Stato (12,5%) sono in zainetti separati e non compensabili tra loro.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Fiscale() {
  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear);

  const { data: years = [] } = useQuery({
    queryKey: ["tax-years"],
    queryFn: taxService.getYears,
  });

  const availableYears = years.includes(selectedYear)
    ? years
    : [...new Set([...years, currentYear])].sort((a, b) => b - a);

  const { data: report, isLoading } = useQuery({
    queryKey: ["tax-report", selectedYear],
    queryFn: () => taxService.getReport(selectedYear),
  });

  const totalCarryStd =
    report?.prior_carryforward_standard.reduce((s, e) => s + e.amount, 0) ?? 0;
  const totalCarryGovt =
    report?.prior_carryforward_govt.reduce((s, e) => s + e.amount, 0) ?? 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fiscale</h1>
          <p className="text-sm text-gray-500 mt-1">Riepilogo imposte — normativa italiana</p>
        </div>
        <select
          value={selectedYear}
          onChange={(e) => setSelectedYear(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {availableYears.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      {/* Simulatore vendita */}
      <SellSimulator />

      {isLoading ? (
        <div className="text-center py-16 text-sm text-gray-500">Calcolo in corso...</div>
      ) : !report || report.events.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
          <Wallet className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-500">Nessun evento fiscale nel {selectedYear}</p>
          <p className="text-xs text-gray-400 mt-1">Le vendite, i dividendi e le cedole appariranno qui.</p>
        </div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <KpiCard
              label="Imposta dovuta"
              value={eur(report.total_tax_due)}
              sub="capital gain"
              icon={<AlertCircle className="w-4 h-4 text-red-500" />}
            />
            <KpiCard
              label="Plusvalenze totali"
              value={eur(report.gains_standard + report.gains_govt)}
              sub="entrambe le aliquote"
              icon={<TrendingUp className="w-4 h-4 text-green-500" />}
            />
            <KpiCard
              label="Minusvalenze totali"
              value={eur(report.losses_standard + report.losses_govt)}
              sub="compensabili"
              icon={<TrendingDown className="w-4 h-4 text-red-500" />}
            />
            <KpiCard
              label="Zainetto disponibile"
              value={eur(totalCarryStd + totalCarryGovt)}
              sub="da anni precedenti"
              icon={<Wallet className="w-4 h-4 text-brand-600" />}
            />
          </div>

          {/* Bracket cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Bracket
              label="Azioni, ETF, Crypto"
              rate={0.26}
              gains={report.gains_standard}
              losses={report.losses_standard}
              carryApplied={report.carryforward_applied_standard}
              netTaxable={report.net_taxable_standard}
              tax={report.tax_standard}
              newCarry={report.new_carryforward_standard}
              priorEntries={report.prior_carryforward_standard}
            />
            <Bracket
              label="Titoli di Stato (BTP/BOT/CCT)"
              rate={0.125}
              gains={report.gains_govt}
              losses={report.losses_govt}
              carryApplied={report.carryforward_applied_govt}
              netTaxable={report.net_taxable_govt}
              tax={report.tax_govt}
              newCarry={report.new_carryforward_govt}
              priorEntries={report.prior_carryforward_govt}
            />
          </div>

          {/* Income */}
          <IncomeSection report={report} />

          {/* Storico minusvalenze */}
          <CarryforwardHistory years={availableYears} />

          {/* Disclaimer */}
          <div className="flex items-start gap-3 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-700">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              I calcoli sono effettuati con metodo <strong>FIFO</strong> a scopo informativo e potrebbero
              differire da quanto calcolato dal tuo broker (che usa PMC in regime amministrato o LIFO in
              regime dichiarativo). Per la dichiarazione fiscale consulta un commercialista o usa i report
              ufficiali del tuo intermediario.
            </p>
          </div>

          {/* Events table */}
          <EventsTable events={report.events} />
        </>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-4 py-4">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
