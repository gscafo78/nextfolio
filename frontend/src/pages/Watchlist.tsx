import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Eye, Trash2, Plus, TrendingUp, TrendingDown, Minus,
  Target, X, Check,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { TopBar } from "@/components/layout/TopBar";
import { AssetAutocomplete } from "@/components/transactions/AssetAutocomplete";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/services/api";
import type { Asset } from "@/services/transactions";

// ── Tipi ─────────────────────────────────────────────────────────────────────

interface WatchlistItem {
  id: number;
  asset_id: number;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  note: string | null;
  target_price: number | null;
  current_price: number | null;
  current_price_eur: number | null;
  change_pct: number | null;
  added_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function ChangeChip({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-gray-300 text-xs">—</span>;
  const pos = pct >= 0;
  const Icon = pos ? TrendingUp : pct < 0 ? TrendingDown : Minus;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold tabular-nums ${pos ? "text-green-600" : "text-red-500"}`}>
      <Icon className="w-3 h-3" />
      {pos ? "+" : ""}{pct.toFixed(2)}%
    </span>
  );
}

function TargetDistance({ current, target }: { current: number | null; target: number | null }) {
  if (current == null || target == null) return null;
  const dist = ((current - target) / target) * 100;
  const reached = Math.abs(dist) <= 5;
  return (
    <span className={`text-xs tabular-nums font-medium ${reached ? "text-green-600" : "text-gray-400"}`}>
      {reached ? "🎯" : ""} {dist >= 0 ? "+" : ""}{dist.toFixed(1)}% dal target
    </span>
  );
}

// ── Modal aggiungi ────────────────────────────────────────────────────────────

function AddModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [asset, setAsset] = useState<Asset | null>(null);
  const [note, setNote] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [error, setError] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.post("/watchlist", {
      asset_id: asset!.id,
      note: note.trim() || null,
      target_price: targetPrice ? parseFloat(targetPrice) : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      onClose();
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? t("common.error")),
  });

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold dark:text-slate-100">{t("watchlist.add")}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 dark:text-slate-400 block mb-1">{t("common.asset")}</label>
          <AssetAutocomplete onSelect={setAsset} />
        </div>

        {asset && (
          <>
            <div className="flex items-center gap-2 bg-brand-50 dark:bg-brand-900/20 rounded-lg px-3 py-2">
              <Check className="w-4 h-4 text-brand-600 flex-shrink-0" />
              <span className="text-sm font-medium text-brand-700 dark:text-brand-300">{asset.symbol} — {asset.name}</span>
              <button onClick={() => setAsset(null)} className="ml-auto text-brand-400 hover:text-brand-600">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <Input
              label={`${t("watchlist.targetPrice")} (${asset.currency})`}
              type="number" step="any"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              placeholder={t("watchlist.targetPricePlaceholder")}
            />
            <Input
              label={t("watchlist.note")}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("watchlist.notePlaceholder")}
            />
          </>
        )}

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="flex gap-3 pt-1">
          <Button variant="secondary" onClick={onClose} className="flex-1">{t("common.cancel")}</Button>
          <Button onClick={() => mutate()} loading={isPending} disabled={!asset} className="flex-1">
            {t("watchlist.addToWatchlist")}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Componente principale ─────────────────────────────────────────────────────

export function Watchlist() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: items = [], isLoading } = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"],
    queryFn: async () => {
      const { data } = await api.get<WatchlistItem[]>("/watchlist");
      return data;
    },
    staleTime: 60 * 1000,
  });

  const { mutate: remove } = useMutation({
    mutationFn: (id: number) => api.delete(`/watchlist/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  return (
    <>
      <TopBar title={t("nav.watchlist")} />
      <main className="flex-1 p-4 md:p-6 space-y-4 max-w-5xl mx-auto w-full">

        {/* Header + aggiungi */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 dark:text-slate-400">
            {items.length > 0
              ? t("watchlist.subtitle", { count: items.length })
              : t("watchlist.empty")}
          </p>
          <Button onClick={() => setShowAdd(true)} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            {t("watchlist.add")}
          </Button>
        </div>

        {/* Tabella desktop */}
        {isLoading ? (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-50 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center justify-between px-5 py-4">
                <div className="space-y-1.5">
                  <div className="h-4 w-24 bg-gray-100 dark:bg-slate-700 rounded" />
                  <div className="h-3 w-40 bg-gray-100 dark:bg-slate-700 rounded" />
                </div>
                <div className="h-4 w-20 bg-gray-100 dark:bg-slate-700 rounded" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-16 text-center">
            <Eye className="w-10 h-10 text-gray-200 dark:text-slate-700 mx-auto mb-3" />
            <p className="text-sm text-gray-400 dark:text-slate-500">{t("watchlist.emptyHint")}</p>
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden md:block bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-slate-700 text-left">
                    <th className="px-5 py-3 text-xs font-medium text-gray-400 uppercase">{t("common.asset")}</th>
                    <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("common.price")}</th>
                    <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("dashboard.change")}</th>
                    <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase text-right">{t("watchlist.targetPrice")}</th>
                    <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase">{t("watchlist.note")}</th>
                    <th className="px-4 py-3 w-10" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-slate-700/50">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50/70 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="font-medium text-gray-900 dark:text-slate-100">{item.symbol}</div>
                        <div className="text-xs text-gray-400 dark:text-slate-500 truncate max-w-[200px]">{item.name}</div>
                      </td>
                      <td className="px-4 py-3.5 text-right tabular-nums">
                        {item.current_price != null ? (
                          <span className="font-semibold text-gray-900 dark:text-slate-100">
                            {item.current_price.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 4 })} {item.currency}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <ChangeChip pct={item.change_pct} />
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        {item.target_price != null ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center justify-end gap-1 text-xs font-medium text-gray-600 dark:text-slate-300 tabular-nums">
                              <Target className="w-3 h-3 text-gray-400" />
                              {item.target_price.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                            </div>
                            <TargetDistance current={item.current_price} target={item.target_price} />
                          </div>
                        ) : <span className="text-gray-300 text-xs">—</span>}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-gray-500 dark:text-slate-400 max-w-[180px] truncate">
                        {item.note ?? "—"}
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => remove(item.id)}
                          className="text-gray-300 hover:text-red-500 transition-colors"
                          title={t("common.delete")}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile: card list */}
            <div className="md:hidden bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-50 dark:divide-slate-700/50">
              {items.map((item) => (
                <div key={item.id} className="flex items-start justify-between px-4 py-3.5 gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-gray-900 dark:text-slate-100 text-sm">{item.symbol}</div>
                    <div className="text-xs text-gray-400 truncate">{item.name}</div>
                    <div className="flex items-center gap-2 mt-1">
                      {item.current_price != null && (
                        <span className="text-xs tabular-nums text-gray-700 dark:text-slate-300">
                          {item.current_price.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 4 })} {item.currency}
                        </span>
                      )}
                      <ChangeChip pct={item.change_pct} />
                    </div>
                    {item.target_price != null && (
                      <TargetDistance current={item.current_price} target={item.target_price} />
                    )}
                    {item.note && <p className="text-xs text-gray-400 mt-0.5 truncate">{item.note}</p>}
                  </div>
                  <button onClick={() => remove(item.id)} className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0 mt-0.5">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </>
        )}
      </main>

      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
    </>
  );
}
