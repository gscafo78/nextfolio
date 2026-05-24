import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { accountService, transactionService, type BrokerFormat } from "@/services/transactions";
import { Button } from "@/components/ui/Button";

const BROKERS: { value: BrokerFormat; label: string }[] = [
  { value: "fineco", label: "Fineco" },
  { value: "directa", label: "Directa Plus" },
  { value: "degiro", label: "Degiro" },
];

interface CsvImportProps {
  onSuccess?: (count: number) => void;
}

export function CsvImport({ onSuccess }: CsvImportProps) {
  const [broker, setBroker] = useState<BrokerFormat>("fineco");
  const [accountId, setAccountId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: accountService.list });

  const { mutate, isPending, error, isSuccess, data } = useMutation({
    mutationFn: () => {
      if (!file || !accountId) throw new Error("Completa tutti i campi");
      return transactionService.importCsv(accountId as number, broker, file);
    },
    onSuccess: (imported) => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      onSuccess?.(imported.length);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Broker</label>
          <select
            value={broker}
            onChange={(e) => setBroker(e.target.value as BrokerFormat)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {BROKERS.map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Conto</label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">— seleziona —</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div
        onClick={() => fileRef.current?.click()}
        className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors"
      >
        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        {file ? (
          <p className="text-sm font-medium text-gray-700">{file.name}</p>
        ) : (
          <p className="text-sm text-gray-500">Clicca per selezionare il file CSV</p>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {error && <p className="text-sm text-red-600">Errore: {(error as Error).message}</p>}
      {isSuccess && (
        <p className="text-sm text-green-600 font-medium">
          Importate {data?.length ?? 0} transazioni con successo.
        </p>
      )}

      <Button
        onClick={() => mutate()}
        loading={isPending}
        disabled={!file || !accountId}
        className="w-full"
      >
        Importa CSV
      </Button>
    </div>
  );
}
