import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useZenMode } from "@/context/ThemeContext";
import { Plus, Upload, Trash2, Filter, Pencil, Tag, MoreVertical, Copy } from "lucide-react";
import { format } from "date-fns";
import { useTranslation } from "react-i18next";
import { getIntlLocale, getDateFnsLocale } from "@/utils/format";
import { TopBar } from "@/components/layout/TopBar";
import { TransactionForm } from "@/components/transactions/TransactionForm";
import { CsvImport } from "@/components/transactions/CsvImport";
import { AssetBadge } from "@/components/transactions/AssetBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { accountService, assetService, transactionService, type Transaction, type TransactionType } from "@/services/transactions";
import { HoldingDetailModal } from "@/components/portfolio/HoldingDetailModal";
import { AccountFavicon } from "@/components/AccountFavicon";

const TX_COLORS: Record<TransactionType, string> = {
  BUY: "text-green-600",
  SELL: "text-red-600",
  DIVIDEND: "text-blue-600",
  COUPON: "text-blue-600",
  FEE: "text-gray-500",
  INTEREST: "text-blue-600",
};

type Modal = null | "add" | "import";

const TX_TYPES_LIST = ["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"] as const;

// ── Edit Transaction Modal ───────────────────────────────────────────────────

function EditTxModal({ tx, onClose }: { tx: Transaction; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    account_id: tx.account_id,
    type: tx.type,
    date: tx.date,
    quantity: tx.quantity,
    price: tx.price,
    exchange_rate: tx.exchange_rate,
    fee: tx.fee,
    notes: tx.notes ?? "",
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => transactionService.update(tx.id, {
      account_id: Number(form.account_id),
      type: form.type,
      date: form.date,
      quantity: Number(form.quantity),
      price: Number(form.price),
      exchange_rate: Number(form.exchange_rate),
      fee: Number(form.fee),
      notes: form.notes || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
      onClose();
    },
  });

  const set = (k: string, v: unknown) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{t("transactions.editTransaction")}</h2>
            <p className="text-xs text-gray-400 mt-0.5">{tx.asset.name} · #{tx.id}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">{t("common.account")}</label>
          <select
            value={form.account_id}
            onChange={(e) => set("account_id", Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}{a.broker ? ` (${a.broker})` : ""}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">{t("common.type")}</label>
            <select
              value={form.type}
              onChange={(e) => set("type", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            >
              {TX_TYPES_LIST.map((type) => <option key={type} value={type}>{t(`transactions.types.${type}`)}</option>)}
            </select>
          </div>
          <Input label={t("common.date")} type="date" value={form.date} onChange={(e) => set("date", e.target.value)} />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Input label={t("common.quantity")} type="number" step="any" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} />
          <Input label={`${t("common.price")} (${tx.price_currency})`} type="number" step="any" value={form.price} onChange={(e) => set("price", e.target.value)} />
          <Input label={t("transactionForm.fees")} type="number" step="any" value={form.fee} onChange={(e) => set("fee", e.target.value)} />
        </div>

        {tx.price_currency !== "EUR" && (
          <Input
            label={t("transactionForm.fxRate", { currency: tx.price_currency })}
            type="number"
            step="any"
            value={form.exchange_rate}
            onChange={(e) => set("exchange_rate", e.target.value)}
          />
        )}

        <Input label={t("transactionForm.notesLabel")} value={form.notes} onChange={(e) => set("notes", e.target.value)} />

        {error && (
          <p className="text-xs text-red-600">{(error as any)?.response?.data?.detail ?? t("transactions.saveError")}</p>
        )}

        <div className="flex gap-3 pt-1">
          <Button variant="secondary" onClick={onClose} className="flex-1">{t("common.cancel")}</Button>
          <Button onClick={() => mutate()} loading={isPending} className="flex-1">{t("common.save")}</Button>
        </div>
      </div>
    </div>
  );
}

// ── Clone Transaction Modal ──────────────────────────────────────────────────

function CloneTxModal({ tx, onClose }: { tx: Transaction; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    account_id: tx.account_id,
    type:       tx.type,
    date:       "",   // svuotata
    quantity:   "",   // svuotata
    price:      "",   // svuotata
    exchange_rate: String(tx.exchange_rate),
    fee:        String(tx.fee),
    notes:      tx.notes ?? "",
  });

  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => transactionService.create({
      account_id:    Number(form.account_id),
      asset_id:      tx.asset_id,
      type:          form.type as TransactionType,
      date:          form.date,
      quantity:      Number(form.quantity),
      price:         Number(form.price),
      price_currency: tx.price_currency,
      exchange_rate: Number(form.exchange_rate),
      fee:           Number(form.fee),
      fee_currency:  tx.fee_currency,
      notes:         form.notes || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      onClose();
    },
  });

  const set = (k: string, v: unknown) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold dark:text-slate-100">{t("transactions.cloneTransaction")}</h2>
            <p className="text-xs text-gray-400 mt-0.5">{tx.asset.name} &middot; {t("transactions.cloneDesc")}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:hover:text-slate-200 text-xl leading-none">&times;</button>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 dark:text-slate-400 block mb-1">{t("common.account")}</label>
          <select
            value={form.account_id}
            onChange={(e) => set("account_id", Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:text-slate-100"
          >
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}{a.broker ? ` (${a.broker})` : ""}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600 dark:text-slate-400 block mb-1">{t("common.type")}</label>
            <select
              value={form.type}
              onChange={(e) => set("type", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:text-slate-100"
            >
              {TX_TYPES_LIST.map((type) => <option key={type} value={type}>{t(`transactions.types.${type}`)}</option>)}
            </select>
          </div>
          <Input label={t("common.date")} type="date" value={form.date} onChange={(e) => set("date", e.target.value)} />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Input label={t("common.quantity")} type="number" step="any" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} />
          <Input label={`${t("common.price")} (${tx.price_currency})`} type="number" step="any" value={form.price} onChange={(e) => set("price", e.target.value)} />
          <Input label={t("transactionForm.fees")} type="number" step="any" value={form.fee} onChange={(e) => set("fee", e.target.value)} />
        </div>

        {tx.price_currency !== "EUR" && (
          <Input
            label={t("transactionForm.fxRate", { currency: tx.price_currency })}
            type="number" step="any"
            value={form.exchange_rate}
            onChange={(e) => set("exchange_rate", e.target.value)}
          />
        )}

        <Input label={t("transactionForm.notesLabel")} value={form.notes} onChange={(e) => set("notes", e.target.value)} />

        {error && <p className="text-xs text-red-600">{(error as any)?.response?.data?.detail ?? t("transactions.saveError")}</p>}

        <div className="flex gap-3 pt-1">
          <Button variant="secondary" onClick={onClose} className="flex-1">{t("common.cancel")}</Button>
          <Button onClick={() => mutate()} loading={isPending} className="flex-1">{t("transactions.clone")}</Button>
        </div>
      </div>
    </div>
  );
}

// ── Kebab menu azioni transazione ────────────────────────────────────────────

function TxActionMenu({
  onEdit, onClone, onDelete,
}: {
  onEdit: () => void;
  onClone: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="text-gray-300 hover:text-gray-600 dark:hover:text-slate-300 transition-colors p-1 rounded-md hover:bg-gray-100 dark:hover:bg-slate-700"
        title={t("transactions.actions")}
      >
        <MoreVertical className="w-4 h-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-36 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl shadow-lg z-50 py-1">
          <button
            onClick={() => { setOpen(false); onEdit(); }}
            className="w-full text-left px-3.5 py-2 text-sm text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-slate-700 flex items-center gap-2 transition-colors"
          >
            <Pencil className="w-3.5 h-3.5 flex-shrink-0" />
            {t("common.edit")}
          </button>
          <button
            onClick={() => { setOpen(false); onClone(); }}
            className="w-full text-left px-3.5 py-2 text-sm text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-slate-700 flex items-center gap-2 transition-colors"
          >
            <Copy className="w-3.5 h-3.5 flex-shrink-0" />
            {t("transactions.clone")}
          </button>
          <div className="my-1 border-t border-gray-100 dark:border-slate-700" />
          <button
            onClick={() => { setOpen(false); onDelete(); }}
            className="w-full text-left px-3.5 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5 flex-shrink-0" />
            {t("common.delete")}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Edit Asset Ticker Modal ──────────────────────────────────────────────────

function EditTickerModal({ assetId, assetName, currentSymbol, currentYahooTicker, onClose }: {
  assetId: number;
  assetName: string;
  currentSymbol: string;
  currentYahooTicker: string | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState(currentSymbol);
  const [yahooTicker, setYahooTicker] = useState(currentYahooTicker ?? "");

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => assetService.update(assetId, {
      symbol: symbol.trim() || currentSymbol,
      yahoo_ticker: yahooTicker.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{t("transactions.assetTicker")}</h2>
            <p className="text-xs text-gray-400 mt-0.5 truncate max-w-[240px]">{assetName}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
        </div>

        <Input
          label={t("transactions.symbolLabel")}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="es. IT0005413171"
        />
        <div>
          <Input
            label={t("transactions.yahooTickerLabel")}
            value={yahooTicker}
            onChange={(e) => setYahooTicker(e.target.value)}
            placeholder="es. SWDA.MI, BTPITALY.MI"
          />
          <p className="text-xs text-gray-400 mt-1">
            {t("transactions.yahooTickerHint")}
          </p>
        </div>

        {error && (
          <p className="text-xs text-red-600">{(error as any)?.response?.data?.detail ?? t("common.error")}</p>
        )}

        <div className="flex gap-3 pt-1">
          <Button variant="secondary" onClick={onClose} className="flex-1">{t("common.cancel")}</Button>
          <Button onClick={() => mutate()} loading={isPending} className="flex-1">{t("common.save")}</Button>
        </div>
      </div>
    </div>
  );
}

export function Transazioni() {
  const { t, i18n } = useTranslation();
  const [modal, setModal] = useState<Modal>(null);
  const [editTx, setEditTx]   = useState<Transaction | null>(null);
  const [cloneTx, setCloneTx] = useState<Transaction | null>(null);
  const [editAsset, setEditAsset] = useState<{ id: number; name: string; symbol: string; yahoo_ticker: string | null } | null>(null);
  const [holdingAssetId, setHoldingAssetId] = useState<number | null>(null);
  const [filterAccountId, setFilterAccountId] = useState<number | "">("");
  const [filterType, setFilterType] = useState<TransactionType | "">("");
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);
  const qc = useQueryClient();
  const zenMode = useZenMode();
  const zen = (v: string) => zenMode ? "•••••" : v;

  const dfLocale = getDateFnsLocale(i18n.language);

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ["transactions", filterAccountId, filterType],
    queryFn: () => transactionService.list({
      limit: 500,
      account_id: filterAccountId || undefined,
      type: (filterType || undefined) as TransactionType | undefined,
    }),
  });

  const { mutate: deleteTx } = useMutation({
    mutationFn: transactionService.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["transactions"] }),
  });

  const totalEur = transactions
    .filter((tx) => tx.type === "BUY" || tx.type === "SELL")
    .reduce((sum, tx) => sum + (tx.type === "BUY" ? tx.total_eur : -tx.total_eur), 0);

  const activeFilters = (filterAccountId !== "" ? 1 : 0) + (filterType !== "" ? 1 : 0);

  const totalPages = Math.max(1, Math.ceil(transactions.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const paginatedTx = transactions.slice((safePage - 1) * pageSize, safePage * pageSize);

  function resetPage() { setCurrentPage(1); }

  return (
    <>
      <TopBar title={t("transactions.title")} />
      <main className="flex-1 p-4 md:p-6">

        {/* Barra filtri */}
        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="flex items-center gap-1.5 text-sm text-gray-500">
            <Filter className="w-4 h-4" />
            <span>{t("transactions.filters")}{activeFilters > 0 ? ` (${activeFilters})` : ""}:</span>
          </div>

          <select
            value={filterAccountId}
            onChange={(e) => { setFilterAccountId(e.target.value ? Number(e.target.value) : ""); resetPage(); }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value="">{t("transactions.allAccounts")}</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>

          <select
            value={filterType}
            onChange={(e) => { setFilterType(e.target.value as TransactionType | ""); resetPage(); }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value="">{t("transactions.allTypes")}</option>
            {TX_TYPES_LIST.map((type) => (
              <option key={type} value={type}>{t(`transactions.types.${type}`)}</option>
            ))}
          </select>

          {activeFilters > 0 && (
            <button
              onClick={() => { setFilterAccountId(""); setFilterType(""); resetPage(); }}
              className="text-xs text-brand-600 hover:underline"
            >
              {t("transactions.removeFilters")}
            </button>
          )}

          <div className="flex-1" />

          <div className="flex items-center gap-1.5 text-sm text-gray-500">
            <span className="hidden sm:inline">{t("transactions.rows")}</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); resetPage(); }}
              className="px-2 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 bg-white"
            >
              {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <span className="text-sm text-gray-500">
            {transactions.length} {t("transactions.ops")}
          </span>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setModal("import")}>
              <Upload className="w-4 h-4 mr-1.5" /> {t("transactions.importCsv")}
            </Button>
            <Button onClick={() => setModal("add")}>
              <Plus className="w-4 h-4 mr-1.5" /> {t("transactions.addTx")}
            </Button>
          </div>
        </div>

        {/* Riepilogo per conto */}
        {filterAccountId === "" && accounts.length > 1 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {accounts.map((acc) => {
              const accTxs = transactions.filter((tx) => tx.account_id === acc.id);
              const invested = accTxs
                .filter((tx) => tx.type === "BUY")
                .reduce((s, tx) => s + tx.total_eur, 0);
              return (
                <button
                  key={acc.id}
                  onClick={() => setFilterAccountId(acc.id)}
                  className="bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-brand-300 hover:shadow-sm transition-all"
                >
                  <p className="text-xs text-gray-400 truncate">{acc.broker ?? acc.name}</p>
                  <p className="text-sm font-semibold text-gray-900 truncate mt-0.5 flex items-center gap-1.5">
                    <AccountFavicon url={acc.url} size={4} />
                    {acc.name}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {accTxs.length} {t("transactions.ops")} · {t("transactions.invested").toLowerCase()} {zen("€ " + invested.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 0 }))}
                  </p>
                </button>
              );
            })}
          </div>
        )}

        {/* Tabella */}
        {isLoading ? (
          <div className="text-center text-gray-400 py-16">{t("common.loading")}</div>
        ) : transactions.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
            <p className="text-gray-400 text-sm">
              {activeFilters > 0 ? t("transactions.noTransactionsFiltered") : t("transactions.noTransactions")}
            </p>
            {activeFilters === 0 && (
              <Button className="mt-4" onClick={() => setModal("add")}>
                <Plus className="w-4 h-4 mr-1.5" /> {t("transactions.firstTransaction")}
              </Button>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

            {/* ── Mobile: card list ── */}
            <div className="md:hidden divide-y divide-gray-100">
              {paginatedTx.map((tx) => {
                const account = accounts.find((a) => a.id === tx.account_id);
                return (
                  <div key={tx.id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-xs font-semibold ${TX_COLORS[tx.type]}`}>{t(`transactions.types.${tx.type}`)}</span>
                          <span className="text-xs text-gray-400">
                            {format(new Date(tx.date), "dd MMM yyyy", { locale: dfLocale })}
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-1">
                          <button
                            onClick={() => setHoldingAssetId(tx.asset.id)}
                            className="text-sm font-medium text-gray-900 hover:text-brand-600 truncate max-w-[160px]"
                          >
                            {tx.asset.yahoo_ticker ?? tx.asset.symbol}
                          </button>
                        </div>
                        <div className="text-xs text-gray-400 truncate">{tx.asset.name}</div>
                        {account && (
                          <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                            <AccountFavicon url={account.url} size={3} />
                            {account.name}
                          </div>
                        )}
                      </div>
                      <div className="flex-shrink-0 text-right">
                        <div className="text-sm font-semibold text-gray-900 tabular-nums">
                          {zen("€ " + tx.total_eur.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2, maximumFractionDigits: 2 }))}
                        </div>
                        <div className="text-xs text-gray-400 tabular-nums mt-0.5">
                          {tx.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 4 })} × {tx.price.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 })}
                        </div>
                        <div className="flex items-center justify-end mt-1.5">
                          <TxActionMenu
                            onEdit={() => setEditTx(tx)}
                            onClone={() => setCloneTx(tx)}
                            onDelete={() => { if (confirm(t("transactions.deleteConfirm"))) deleteTx(tx.id); }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ── Paginazione mobile ── */}
            {totalPages > 1 && (
              <div className="md:hidden flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
                <span className="text-xs">{(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, transactions.length)} {t("transactions.of")} {transactions.length}</span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={safePage === 1} className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">←</button>
                  <span className="px-2 text-xs">{safePage}/{totalPages}</span>
                  <button onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">→</button>
                </div>
              </div>
            )}

            {/* ── Desktop: full table ── */}
            <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">{t("common.date")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">{t("common.type")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">{t("common.asset")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">{t("common.account")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">{t("common.quantity")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">{t("common.price")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">{t("transactions.totalEur")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">{t("transactions.exchangeRate")}</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">{t("transactions.feeAbbr")}</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {paginatedTx.map((tx) => {
                  const account = accounts.find((a) => a.id === tx.account_id);
                  return (
                    <tr key={tx.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-600">
                        {format(new Date(tx.date), "dd MMM yyyy", { locale: dfLocale })}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-medium ${TX_COLORS[tx.type]}`}>{t(`transactions.types.${tx.type}`)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setHoldingAssetId(tx.asset.id)}
                            className="font-medium text-gray-900 truncate max-w-[120px] hover:text-brand-600 hover:underline transition-colors text-left"
                          >
                            {tx.asset.yahoo_ticker ?? tx.asset.symbol}
                          </button>
                          <button
                            onClick={() => setEditAsset({ id: tx.asset.id, name: tx.asset.name, symbol: tx.asset.symbol, yahoo_ticker: tx.asset.yahoo_ticker })}
                            className="text-gray-300 hover:text-brand-500 transition-colors flex-shrink-0"
                            title={t("transactions.editTicker")}
                          >
                            <Tag className="w-3 h-3" />
                          </button>
                        </div>
                        <div className="text-xs text-gray-400 truncate max-w-[160px]">{tx.asset.name}</div>
                        <AssetBadge type={tx.asset.type} exchange={tx.asset.exchange} />
                      </td>
                      <td className="px-4 py-3">
                        {account ? (
                          <div>
                            <div className="text-xs font-medium text-gray-700 flex items-center gap-1">
                              <AccountFavicon url={account.url} size={3} />
                              {account.name}
                            </div>
                            {account.broker && (
                              <div className="text-xs text-gray-400">{account.broker}</div>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {tx.quantity.toLocaleString(getIntlLocale(i18n.language), { maximumFractionDigits: 6 })}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        <div>{tx.price.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 })} {tx.price_currency}</div>
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-gray-900">
                        {zen("€ " + tx.total_eur.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 }))}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400 text-xs">
                        {tx.price_currency !== "EUR"
                          ? <span title={`1 ${tx.price_currency} = ${tx.exchange_rate} EUR`}>{tx.exchange_rate.toFixed(4)}</span>
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400">
                        {tx.fee > 0 ? zen(`€ ${tx.fee.toFixed(2)}`) : "—"}
                      </td>
                      <td className="px-2 py-3 text-right">
                        <TxActionMenu
                          onEdit={() => setEditTx(tx)}
                          onClone={() => setCloneTx(tx)}
                          onDelete={() => { if (confirm(t("transactions.deleteConfirm"))) deleteTx(tx.id); }}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {transactions.some((tx) => tx.type === "BUY" || tx.type === "SELL") && (
                <tfoot>
                  <tr className="border-t border-gray-200 bg-gray-50">
                    <td colSpan={6} className="px-4 py-2 text-xs text-gray-400">
                      {t("transactions.totalNetBuySell")}
                    </td>
                    <td className="px-4 py-2 text-right text-sm font-semibold text-gray-900">
                      {zen("€ " + totalEur.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 }))}
                    </td>
                    <td colSpan={3} />
                  </tr>
                </tfoot>
              )}
            </table>
            </div>

            {/* ── Paginazione ── */}
            {totalPages > 1 && (
              <div className="hidden md:flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
                <span>
                  {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, transactions.length)} {t("transactions.of")} {transactions.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={safePage === 1}
                    className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    ← {t("common.back")}
                  </button>
                  <span className="px-3 text-xs">
                    {safePage} / {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={safePage === totalPages}
                    className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {t("common.next")} →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modal Aggiungi */}
      {modal === "add" && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{t("transactions.newTransaction")}</h2>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
            </div>
            <TransactionForm onSuccess={() => setModal(null)} />
          </div>
        </div>
      )}

      {/* Modal Importa CSV */}
      {modal === "import" && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{t("transactions.importCsvTitle")}</h2>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
            </div>
            <CsvImport onSuccess={() => setModal(null)} />
          </div>
        </div>
      )}

      {editTx  && <EditTxModal  tx={editTx}  onClose={() => setEditTx(null)}  />}
      {cloneTx && <CloneTxModal tx={cloneTx} onClose={() => setCloneTx(null)} />}

      {holdingAssetId != null && (
        <HoldingDetailModal
          assetId={holdingAssetId}
          onClose={() => setHoldingAssetId(null)}
        />
      )}

      {editAsset && (
        <EditTickerModal
          assetId={editAsset.id}
          assetName={editAsset.name}
          currentSymbol={editAsset.symbol}
          currentYahooTicker={editAsset.yahoo_ticker}
          onClose={() => setEditAsset(null)}
        />
      )}
    </>
  );
}
