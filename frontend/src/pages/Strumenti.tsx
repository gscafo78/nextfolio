import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, Wallet, PiggyBank, Percent, Download } from "lucide-react";
import { api } from "@/services/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

const eur = (v: number) =>
  v.toLocaleString("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

// ── PAC Calculator ────────────────────────────────────────────────────────────

interface PacPoint {
  year: number;
  invested: number;
  value: number;
}

interface PacResult {
  total_invested: number;
  final_value: number;
  total_gain: number;
  gain_pct: number;
  series: PacPoint[];
}

function calculatePac(
  initial: number,
  monthly: number,
  years: number,
  annualRate: number,
): PacResult {
  const r = Math.pow(1 + annualRate / 100, 1 / 12) - 1;
  const months = years * 12;

  let value = initial;
  const series: PacPoint[] = [{ year: 0, invested: initial, value: initial }];

  for (let m = 1; m <= months; m++) {
    value = value * (1 + r) + monthly;
    if (m % 12 === 0) {
      series.push({
        year: m / 12,
        invested: initial + m * monthly,
        value: Math.round(value),
      });
    }
  }

  const total_invested = initial + months * monthly;
  const total_gain = value - total_invested;

  return {
    total_invested: Math.round(total_invested),
    final_value: Math.round(value),
    total_gain: Math.round(total_gain),
    gain_pct: total_invested > 0 ? (total_gain / total_invested) * 100 : 0,
    series,
  };
}

function KpiCard({
  label,
  value,
  sub,
  icon,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border shadow-sm px-4 py-4 ${
        highlight ? "bg-brand-600 border-brand-700" : "bg-white border-gray-200"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className={`text-xs ${highlight ? "text-brand-200" : "text-gray-500"}`}>{label}</span>
      </div>
      <p className={`text-lg font-bold ${highlight ? "text-white" : "text-gray-900"}`}>{value}</p>
      {sub && (
        <p className={`text-xs mt-0.5 ${highlight ? "text-brand-200" : "text-gray-400"}`}>{sub}</p>
      )}
    </div>
  );
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; name: string; color: string }[];
  label?: number;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 mb-1">Anno {label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {eur(p.value)}
        </p>
      ))}
    </div>
  );
};

function PacCalculator() {
  const [initial, setInitial] = useState(5000);
  const [monthly, setMonthly] = useState(300);
  const [years, setYears] = useState(20);
  const [rate, setRate] = useState(7);
  const [result, setResult] = useState<PacResult>(() =>
    calculatePac(5000, 300, 20, 7),
  );

  function handleCalculate() {
    setResult(calculatePac(initial, monthly, years, rate));
  }

  const doublingYears = rate > 0 ? (72 / rate).toFixed(1) : "∞";

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-gray-800 mb-1">Calcolatore PAC</h2>
        <p className="text-xs text-gray-400">
          Simulazione piano di accumulo con capitalizzazione composta mensile
        </p>
      </div>

      {/* Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <label className="block">
          <span className="text-xs font-medium text-gray-600 mb-1 block">Capitale iniziale (€)</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={initial}
            onChange={(e) => setInitial(Math.max(0, Number(e.target.value)))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 mb-1 block">Rata mensile (€)</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={monthly}
            onChange={(e) => setMonthly(Math.max(0, Number(e.target.value)))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 mb-1 block">
            Durata: <strong>{years} anni</strong>
          </span>
          <input
            type="range"
            min={1}
            max={40}
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="w-full accent-brand-600 mt-1"
          />
          <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
            <span>1 anno</span>
            <span>40 anni</span>
          </div>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 mb-1 block">
            Rendimento annuo: <strong>{rate}%</strong>
          </span>
          <input
            type="range"
            min={0}
            max={20}
            step={0.5}
            value={rate}
            onChange={(e) => setRate(Number(e.target.value))}
            className="w-full accent-brand-600 mt-1"
          />
          <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
            <span>0%</span>
            <span>20%</span>
          </div>
        </label>
      </div>

      <button
        onClick={handleCalculate}
        className="px-5 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
      >
        Calcola proiezione
      </button>

      {/* KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          label="Capitale versato"
          value={eur(result.total_invested)}
          icon={<Wallet className="w-4 h-4 text-gray-400" />}
        />
        <KpiCard
          label="Rendimento netto"
          value={eur(result.total_gain)}
          sub={`+${result.gain_pct.toFixed(1)}% sul versato`}
          icon={<TrendingUp className="w-4 h-4 text-green-500" />}
        />
        <KpiCard
          label="Regola del 72"
          value={`${doublingYears} anni`}
          sub="per raddoppiare il capitale"
          icon={<Percent className="w-4 h-4 text-amber-500" />}
        />
        <KpiCard
          label="Valore finale stimato"
          value={eur(result.final_value)}
          sub={`dopo ${years} anni`}
          icon={<PiggyBank className="w-4 h-4 text-brand-300" />}
          highlight
        />
      </div>

      {/* Chart */}
      <div>
        <p className="text-xs font-medium text-gray-500 mb-3">Proiezione anno per anno</p>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={result.series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gradInvested" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#93c5fd" stopOpacity={0.5} />
                <stop offset="95%" stopColor="#93c5fd" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="gradValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1d4ed8" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#1d4ed8" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="year"
              tickFormatter={(v) => `${v}a`}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
            />
            <YAxis
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(v) => (
                <span className="text-xs text-gray-600">
                  {v === "invested" ? "Capitale versato" : "Valore stimato"}
                </span>
              )}
            />
            <Area
              type="monotone"
              dataKey="invested"
              name="invested"
              stroke="#93c5fd"
              fill="url(#gradInvested)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="value"
              name="value"
              stroke="#1d4ed8"
              fill="url(#gradValue)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Yearly table */}
      <div>
        <p className="text-xs font-medium text-gray-500 mb-2">Dettaglio annuale</p>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left text-gray-600">
                <th className="px-4 py-2.5 font-medium text-xs">Anno</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right">Versato</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right">Valore stimato</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right">Rendimento</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right">Rend. %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {result.series
                .filter((p) => p.year > 0)
                .map((p) => {
                  const gain = p.value - p.invested;
                  const gainPct = p.invested > 0 ? (gain / p.invested) * 100 : 0;
                  return (
                    <tr key={p.year} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2 text-gray-700 font-medium">{p.year}</td>
                      <td className="px-4 py-2 text-right text-gray-500">{eur(p.invested)}</td>
                      <td className="px-4 py-2 text-right font-medium text-gray-900">
                        {eur(p.value)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right font-medium ${gain >= 0 ? "text-green-600" : "text-red-600"}`}
                      >
                        {gain >= 0 ? "+" : ""}
                        {eur(gain)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right text-xs ${gain >= 0 ? "text-green-600" : "text-red-600"}`}
                      >
                        {gain >= 0 ? "+" : ""}
                        {gainPct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-gray-400 leading-relaxed">
        Simulazione a scopo illustrativo. Il rendimento annuo è ipotetico e costante — i mercati
        reali sono volatili. I valori non tengono conto di inflazione, tasse o commissioni di
        prodotto.
      </p>
    </div>
  );
}

// ── Export portafoglio ────────────────────────────────────────────────────────

function ExportCard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/portfolio/export", { responseType: "blob" });
      const blob = new Blob([resp.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const cd = resp.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename=(.+)/);
      a.download = match ? match[1] : "nextfolio_export.xlsx";
      a.click();
      URL.revokeObjectURL(url);
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
      const blob = new Blob([resp.data], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const cd = resp.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename=(.+)/);
      a.download = match ? match[1] : "nextfolio_ghostfolio.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Errore durante l'esportazione. Riprova.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-800 mb-1">Esporta dati</h2>
      <p className="text-xs text-gray-400 mb-4">
        Scarica un file Excel con tutte le transazioni e le posizioni aperte,
        oppure esporta in formato Ghostfolio per migrazione.
      </p>

      <div className="flex flex-col sm:flex-row sm:items-start gap-4">
        <div className="flex flex-col gap-2">
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

        <div className="text-xs text-gray-400 space-y-1">
          <p><strong>Excel:</strong> Fogli Transazioni, Posizioni, Info — per commercialista</p>
          <p><strong>Ghostfolio:</strong> Formato JSON v3 compatibile con import Ghostfolio</p>
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

// ── Pagina principale ─────────────────────────────────────────────────────────

export function Strumenti() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-6 md:py-8 space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-gray-900">Strumenti</h1>
        <p className="text-sm text-gray-500 mt-1">Calcolatori e utilità per la gestione del portafoglio</p>
      </div>

      <PacCalculator />
      <ExportCard />
    </div>
  );
}
