import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountService, transactionService, type Asset } from "@/services/transactions";
import { AssetAutocomplete } from "./AssetAutocomplete";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const schema = z.object({
  account_id: z.coerce.number().min(1, "Seleziona un conto"),
  type: z.enum(["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"]),
  date: z.string().min(1, "Inserisci la data"),
  quantity: z.coerce.number().positive("Deve essere > 0"),
  price: z.coerce.number().min(0),
  fee: z.coerce.number().min(0).default(0),
  notes: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const TX_TYPES = [
  { value: "BUY", label: "Acquisto" },
  { value: "SELL", label: "Vendita" },
  { value: "DIVIDEND", label: "Dividendo" },
  { value: "COUPON", label: "Cedola" },
  { value: "FEE", label: "Commissione" },
  { value: "INTEREST", label: "Interesse" },
];

interface TransactionFormProps {
  onSuccess?: () => void;
}

export function TransactionForm({ onSuccess }: TransactionFormProps) {
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const qc = useQueryClient();

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const { register, handleSubmit, formState: { errors }, reset, watch } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { type: "BUY", fee: 0 },
  });

  const { mutate, isPending } = useMutation({
    mutationFn: (data: FormData) => {
      if (!selectedAsset) throw new Error("Seleziona un asset");
      return transactionService.create({ ...data, asset_id: selectedAsset.id });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      reset();
      setSelectedAsset(null);
      onSuccess?.();
    },
  });

  const qty = watch("quantity") || 0;
  const price = watch("price") || 0;
  const fee = watch("fee") || 0;
  const total = qty * price + fee;

  return (
    <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-4">
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">Asset</label>
        <AssetAutocomplete onSelect={setSelectedAsset} />
        {!selectedAsset && <p className="text-xs text-gray-400 mt-1">Cerca l'asset prima di procedere</p>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Conto</label>
          <select
            {...register("account_id")}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">— seleziona —</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {errors.account_id && <p className="text-xs text-red-600 mt-1">{errors.account_id.message}</p>}
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Tipo</label>
          <select
            {...register("type")}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {TX_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      <Input label="Data" type="date" error={errors.date?.message} {...register("date")} />

      <div className="grid grid-cols-3 gap-3">
        <Input label="Quantità" type="number" step="any" error={errors.quantity?.message} {...register("quantity")} />
        <Input label="Prezzo (€)" type="number" step="any" error={errors.price?.message} {...register("price")} />
        <Input label="Commissioni (€)" type="number" step="any" error={errors.fee?.message} {...register("fee")} />
      </div>

      {(qty > 0 && price > 0) && (
        <div className="bg-gray-50 rounded-lg px-4 py-2 text-sm flex justify-between">
          <span className="text-gray-500">Controvalore totale</span>
          <span className="font-semibold text-gray-900">€ {total.toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
        </div>
      )}

      <Input label="Note (opzionale)" {...register("notes")} />

      <Button type="submit" loading={isPending} disabled={!selectedAsset} className="w-full">
        Salva transazione
      </Button>
    </form>
  );
}
