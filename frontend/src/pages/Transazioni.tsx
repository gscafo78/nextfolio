import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload, Trash2 } from "lucide-react";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import { TopBar } from "@/components/layout/TopBar";
import { TransactionForm } from "@/components/transactions/TransactionForm";
import { CsvImport } from "@/components/transactions/CsvImport";
import { AssetBadge } from "@/components/transactions/AssetBadge";
import { Button } from "@/components/ui/Button";
import { transactionService, type TransactionType } from "@/services/transactions";

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
  const qc = useQueryClient();

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => transactionService.list({ limit: 200 }),
  });

  const { mutate: deleteTx } = useMutation({
    mutationFn: transactionService.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["transactions"] }),
  });

  return (
    <>
      <TopBar title="Transazioni" />
      <main className="flex-1 p-6">
        <div className="flex items-center justify-between mb-6">
          <p className="text-sm text-gray-500">{transactions.length} operazioni</p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setModal("import")}>
              <Upload className="w-4 h-4 mr-1.5" /> Importa CSV
            </Button>
            <Button onClick={() => setModal("add")}>
              <Plus className="w-4 h-4 mr-1.5" /> Aggiungi
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="text-center text-gray-400 py-16">Caricamento...</div>
        ) : transactions.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
            <p className="text-gray-400 text-sm">Nessuna transazione ancora.</p>
            <Button className="mt-4" onClick={() => setModal("add")}>
              <Plus className="w-4 h-4 mr-1.5" /> Prima transazione
            </Button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Data</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Asset</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Quantità</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Prezzo</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Totale</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase text-right">Comm.</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-gray-600">
                      {format(new Date(tx.date), "dd MMM yyyy", { locale: it })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`font-medium ${TX_COLORS[tx.type]}`}>{TX_LABELS[tx.type]}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{tx.asset.symbol}</div>
                      <div className="text-xs text-gray-400 truncate max-w-[180px]">{tx.asset.name}</div>
                      <AssetBadge type={tx.asset.type} exchange={tx.asset.exchange} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {tx.quantity.toLocaleString("it-IT", { maximumFractionDigits: 6 })}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      € {tx.price.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      € {(tx.quantity * tx.price).toLocaleString("it-IT", { minimumFractionDigits: 2 })}
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
                ))}
              </tbody>
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
