import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, TrendingDown, TrendingUp, Wallet, AlertCircle, Info } from "lucide-react";
import { taxService, type AnnualTaxReport, type TaxEvent } from "@/services/tax";

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
