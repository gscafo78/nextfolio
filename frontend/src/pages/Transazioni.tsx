import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload, Trash2, Filter } from "lucide-react";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import { TopBar } from "@/components/layout/TopBar";
import { TransactionForm } from "@/components/transactions/TransactionForm";
import { CsvImport } from "@/components/transactions/CsvImport";
import { AssetBadge } from "@/components/transactions/AssetBadge";
import { Button } from "@/components/ui/Button";
import { accountService, transactionService, type TransactionType } from "@/services/transactions";

const TX_LABELS: Record<TransactionType, string> = {
  BUY: "Acquisto",
  SELL: "Vendita",
  DIVIDEND: "Dividendo",
  COUPON: "Cedola",
  FEE: "Commissione",
  INTEREST: "Interesse",
};

const TX_COLORS: Record<TransactionType, string> = {
  BUY: "text-green-600",
  SELL: "text-red-600",
  DIVIDEND: "text-blue-600",
  COUPON: "text-blue-600",
  FEE: "text-gray-500",
  INTEREST: "text-blue-600",
};

type Modal = null | "add" | "import";

export function Transazioni() {
  const [modal, setModal] = useState<Modal>(null);
  const [filterAccountId, setFilterAccountId] = useState<number | "">("");
  const [filterType, setFilterType] = useState<TransactionType | "">("");
  const qc = useQueryClient();

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

  // Totale filtrato
  const totalEur = transactions
    .filter((tx) => tx.type === "BUY" || tx.type === "SELL")
    .reduce((sum, tx) => sum + (tx.type === "BUY" ? tx.total_eur : -tx.total_eur), 0);

  const activeFilters = (filterAccountId !== "" ? 1 : 0) + (filterType !== "" ? 1 : 0);

  return (
    <>
      <TopBar title="Transazioni" />
      <main className="flex-1 p-6">

        {/* Barra filtri */}
        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="flex items-center gap-1.5 text-sm text-gray-500">
            <Filter className="w-4 h-4" />
            <span>Filtri{activeFilters > 0 ? ` (${activeFilters})` : ""}:</span>
          </div>

          <select
            value={filterAccountId}
            onChange={(e) => setFilterAccountId(e.target.value ? Number(e.target.value) : "")}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value="">Tutti i conti</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as TransactionType | "")}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value="">Tutti i tipi</option>
            {Object.entries(TX_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>

          {activeFilters > 0 && (
            <button
              onClick={() => { setFilterAccountId(""); setFilterType(""); }}
              className="text-xs text-brand-600 hover:underline"
            >
              Rimuovi filtri
            </button>
          )}

          <div className="flex-1" />

          {/* Sommario rapido */}
          <span className="text-sm text-gray-500">
            {transactions.length} operazioni
          </span>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setModal("import")}>
              <Upload className="w-4 h-4 mr-1.5" /> Importa CSV
            </Button>
            <Button onClick={() => setModal("add")}>
              <Plus className="w-4 h-4 mr-1.5" /> Aggiungi
            </Button>
          </div>
        </div>

        {/* Riepilogo per conto quando nessun filtro */}
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
                  <p className="text-sm font-semibold text-gray-900 truncate mt-0.5">{acc.name}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {accTxs.length} op · investito € {invested.toLocaleString("it-IT", { maximumFractionDigits: 0 })}
                  </p>
                </button>
              );
            })}
          </div>
        )}

        {/* Tabella */}
        {isLoading ? (
          <div className="text-center text-gray-400 py-16">Caricamento...</div>
        ) : transactions.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
            <p className="text-gray-400 text-sm">
              {activeFilters > 0 ? "Nessuna transazione con questi filtri." : "Nessuna transazione ancora."}
            </p>
            {activeFilters === 0 && (
              <Button className="mt-4" onClick={() => setModal("add")}>
                <Plus className="w-4 h-4 mr-1.5" /> Prima transazione
              </Button>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Data</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Asset</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Conto</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Quantità</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Prezzo</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Totale EUR</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Cambio</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Comm.</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {transactions.map((tx) => {
                  const account = accounts.find((a) => a.id === tx.account_id);
                  return (
                    <tr key={tx.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-600">
                        {format(new Date(tx.date), "dd MMM yyyy", { locale: it })}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-medium ${TX_COLORS[tx.type]}`}>{TX_LABELS[tx.type]}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{tx.asset.symbol}</div>
                        <div className="text-xs text-gray-400 truncate max-w-[160px]">{tx.asset.name}</div>
                        <AssetBadge type={tx.asset.type} exchange={tx.asset.exchange} />
                      </td>
                      <td className="px-4 py-3">
                        {account ? (
                          <div>
                            <div className="text-xs font-medium text-gray-700">{account.name}</div>
                            {account.broker && (
                              <div className="text-xs text-gray-400">{account.broker}</div>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {tx.quantity.toLocaleString("it-IT", { maximumFractionDigits: 6 })}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        <div>{tx.price.toLocaleString("it-IT", { minimumFractionDigits: 2 })} {tx.price_currency}</div>
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-gray-900">
                        € {tx.total_eur.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400 text-xs">
                        {tx.price_currency !== "EUR"
                          ? <span title={`1 ${tx.price_currency} = ${tx.exchange_rate} EUR`}>{tx.exchange_rate.toFixed(4)}</span>
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400">
                        {tx.fee > 0 ? `€ ${tx.fee.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => { if (confirm("Eliminare la transazione?")) deleteTx(tx.id); }}
                          className="text-gray-300 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {/* Footer con totale investito */}
              {transactions.some((tx) => tx.type === "BUY" || tx.type === "SELL") && (
                <tfoot>
                  <tr className="border-t border-gray-200 bg-gray-50">
                    <td colSpan={6} className="px-4 py-2 text-xs text-gray-400">
                      Totale netto acquisti/vendite
                    </td>
                    <td className="px-4 py-2 text-right text-sm font-semibold text-gray-900">
                      € {totalEur.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                    </td>
                    <td colSpan={3} />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </main>

      {/* Modal Aggiungi */}
      {modal === "add" && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">Nuova transazione</h2>
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
              <h2 className="text-lg font-semibold">Importa da CSV</h2>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-gray-700 text-xl leading-none">&times;</button>
            </div>
            <CsvImport onSuccess={() => setModal(null)} />
          </div>
        </div>
      )}
    </>
  );
}
