import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Eye, Plus, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/Button";
import { api } from "@/services/api";
import { accountService } from "@/services/transactions";
import { planningService, type PlanItem, type SearchResult } from "@/services/planning";
import { getIntlLocale } from "@/utils/format";

const pct = (v: number | null | undefined) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2">
      <p className="text-[11px] text-gray-400">{label}</p>
      <p className="text-sm font-semibold text-gray-800 dark:text-slate-100 tabular-nums">{value}</p>
    </div>
  );
}

function TopList({ title, items }: { title: string; items: { label: string; weight: number }[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 mb-1">{title}</p>
      {items.slice(0, 5).map((it) => (
        <div key={it.label} className="flex justify-between text-xs text-gray-600 dark:text-slate-300">
          <span className="truncate">{it.label}</span>
          <span className="tabular-nums">{(it.weight * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

/** Scheda di un titolo (in Nextfolio o trovato su Yahoo) con aggiunta alla simulazione. */
export function SecurityCard({ result, onAdd, onClose }: {
  result: SearchResult;
  onAdd: (item: PlanItem) => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [mode, setMode] = useState<"amount" | "quantity">("amount");
  const [value, setValue] = useState("");
  const [fee, setFee] = useState("");
  const [accountId, setAccountId] = useState<string>("");

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["planning-security", result.asset_id ?? result.symbol],
    queryFn: () => planningService.security({ asset_id: result.asset_id, symbol: result.symbol, type: result.type, name: result.name }),
    staleTime: 10 * 60 * 1000,
  });
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });

  const watch = useMutation({
    mutationFn: async () => {
      let assetId = card?.asset_id ?? null;
      if (!assetId && card?.symbol) {
        assetId = (await planningService.importSecurity({ symbol: card.symbol, name: card.name, type: card.type })).asset_id;
      }
      await api.post("/watchlist", { asset_id: assetId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["planning-security", result.asset_id ?? result.symbol] });
    },
  });

  const num = Number(value.replace(",", "."));
  const valid = value.trim() !== "" && num > 0 && !!card?.price_eur;
  const fmtEur = (v: number) => v.toLocaleString(getIntlLocale(i18n.language), { style: "currency", currency: "EUR" });

  const add = () => {
    if (!card || !valid) return;
    onAdd({
      asset_id: card.asset_id, symbol: card.symbol, name: card.name, type: card.type, isin: card.isin,
      amount_eur: mode === "amount" ? num : null, quantity: mode === "quantity" ? num : null,
      fee_eur: Number(fee.replace(",", ".")) || 0, account_id: accountId ? Number(accountId) : null,
    });
    setValue("");
  };

  const history = (card?.history ?? []).filter((_, i, arr) => arr.length < 400 || i % 3 === 0);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-bold text-gray-900 dark:text-slate-100">{result.name}</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {[card?.ticker ?? result.ticker, card?.isin ?? result.isin, t(`ai.assetTypes.${result.type}`), card?.asset_class].filter(Boolean).join(" · ")}
          </p>
        </div>
        {card?.price_eur != null && (
          <div className="text-right">
            <p className="text-lg font-bold tabular-nums">{fmtEur(card.price_eur)}</p>
            {card.change_pct != null && (
              <p className={`text-xs ${card.change_pct >= 0 ? "text-green-600" : "text-red-600"}`}>{pct(card.change_pct)}</p>
            )}
          </div>
        )}
        <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600" title={t("common.close")}>
          <X className="w-4 h-4" />
        </button>
      </div>

      {isLoading ? (
        <div className="h-40 mt-4 bg-gray-50 dark:bg-slate-800 rounded-xl animate-pulse" />
      ) : isError || !card ? (
        <p className="text-sm text-red-600 mt-4">{t("planning.card.loadError")}</p>
      ) : (
        <>
          {history.length > 1 && (
            <div className="h-40 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history}>
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["auto", "auto"]} hide />
                  <Tooltip
                    formatter={(v: number) => [fmtEur(v), ""]}
                    labelFormatter={(d: string) => new Date(d).toLocaleDateString(i18n.language)}
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  />
                  <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-4">
            <Metric label={t("planning.card.return1y")} value={pct(card.metrics.return_1y_pct)} />
            <Metric label={t("planning.card.return3y")} value={pct(card.metrics.return_3y_ann_pct)} />
            <Metric label={t("planning.card.return5y")} value={pct(card.metrics.return_5y_ann_pct)} />
            <Metric label={t("planning.card.volatility")} value={card.metrics.volatility_1y_pct == null ? "—" : `${card.metrics.volatility_1y_pct.toFixed(1)}%`} />
            <Metric label={t("planning.card.maxDrawdown")} value={pct(card.metrics.max_drawdown_1y_pct)} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
            <TopList title={t("planning.card.currencies")} items={Object.entries(card.currency_exposure).map(([label, weight]) => ({ label, weight })).sort((a, b) => b.weight - a.weight)} />
            <TopList title={t("planning.card.sectors")} items={card.sectors.map((s) => ({ label: s.name, weight: s.weight }))} />
            <TopList title={t("planning.card.countries")} items={card.countries.map((c) => ({ label: c.name ?? c.code ?? "?", weight: c.weight }))} />
          </div>
          {card.holdings.length > 0 && (
            <p className="text-xs text-gray-400 mt-3">
              {t("planning.card.topHoldings")}: {card.holdings.slice(0, 5).map((h) => h.name ?? h.symbol).join(", ")}
            </p>
          )}

          {/* Aggiunta alla simulazione */}
          <div className="mt-5 pt-4 border-t border-gray-100 dark:border-slate-800 flex flex-wrap items-end gap-2">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
              {(["amount", "quantity"] as const).map((m) => (
                <button key={m} type="button" onClick={() => setMode(m)}
                  className={`px-2.5 py-1.5 ${mode === m ? "bg-brand-600 text-white" : "text-gray-600"}`}>
                  {t(`planning.card.${m}`)}
                </button>
              ))}
            </div>
            <input
              value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal"
              placeholder={mode === "amount" ? "€ 1.000" : "10"}
              className="w-28 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              onKeyDown={(e) => e.key === "Enter" && add()}
            />
            <input
              value={fee} onChange={(e) => setFee(e.target.value)} inputMode="decimal" placeholder={t("planning.card.fee")}
              className="w-24 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)}
              className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm">
              <option value="">{t("planning.card.anyAccount")}</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <Button type="button" size="sm" onClick={add} disabled={!valid}>
              <Plus className="w-4 h-4 mr-1" /> {t("planning.card.addToSimulation")}
            </Button>
            {!card.in_watchlist && (
              <Button type="button" size="sm" variant="secondary" onClick={() => watch.mutate()} loading={watch.isPending}
                disabled={watch.isSuccess}>
                <Eye className="w-4 h-4 mr-1" /> {watch.isSuccess ? t("planning.card.watched") : t("planning.card.addToWatchlist")}
              </Button>
            )}
            {valid && card.price_eur && (
              <span className="text-xs text-gray-400 w-full">
                {mode === "amount"
                  ? t("planning.card.approxQty", { qty: (num / card.price_eur).toFixed(4) })
                  : t("planning.card.approxAmount", { amount: fmtEur(num * card.price_eur) })}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
