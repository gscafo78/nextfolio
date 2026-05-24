import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import {
  accountService,
  fxService,
  transactionService,
  type Asset,
} from "@/services/transactions";
import { AssetAutocomplete } from "./AssetAutocomplete";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const schema = z.object({
  account_id: z.coerce.number().min(1, "Seleziona un conto"),
  type: z.enum(["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"]),
  date: z.string().min(1, "Inserisci la data"),
  quantity: z.coerce.number().positive("Deve essere > 0"),
  price: z.coerce.number().min(0),
  exchange_rate: z.coerce.number().positive("Deve essere > 0").default(1),
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
  const [loadingRate, setLoadingRate] = useState(false);
  const qc = useQueryClient();

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountService.list,
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
    setValue,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { type: "BUY", fee: 0, exchange_rate: 1 },
  });

  const date = watch("date");
  const qty = watch("quantity") || 0;
  const price = watch("price") || 0;
  const exchangeRate = watch("exchange_rate") || 1;
  const fee = watch("fee") || 0;

  const needsFx = selectedAsset ? selectedAsset.currency !== "EUR" : false;
  const totalAssetCurrency = qty * price;
  const totalEur = totalAssetCurrency * exchangeRate + fee;

  // Recupera il tasso di cambio storico quando cambia asset o data
  const fetchRate = async () => {
    if (!selectedAsset || !needsFx) return;
    setLoadingRate(true);
    try {
      const result = await fxService.getRate(selectedAsset.currency, date || undefined);
      setValue("exchange_rate", result.rate);
    } catch {
      // lascia il tasso invariato se l'API non risponde
    } finally {
      setLoadingRate(false);
    }
  };

  useEffect(() => {
    if (needsFx && date) fetchRate();
    if (!needsFx) setValue("exchange_rate", 1);
  }, [selectedAsset, date]); // eslint-disable-line react-hooks/exhaustive-deps

  const { mutate, isPending } = useMutation({
    mutationFn: (data: FormData) => {
      if (!selectedAsset) throw new Error("Seleziona un asset");
      return transactionService.create({
        ...data,
        asset_id: selectedAsset.id,
        price_currency: selectedAsset.currency,
        fee_currency: "EUR",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      reset();
      setSelectedAsset(null);
      onSuccess?.();
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-4">
      {/* Asset */}
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">Asset</label>
        <AssetAutocomplete
          onSelect={(asset) => {
            setSelectedAsset(asset);
          }}
        />
        {selectedAsset && (
          <p className="text-xs text-gray-400 mt-1">
            Valuta asset: <span className="font-medium text-gray-600">{selectedAsset.currency}</span>
          </p>
        )}
      </div>

      {/* Conto + Tipo */}
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

      {/* Data */}
      <Input label="Data" type="date" error={errors.date?.message} {...register("date")} />

      {/* Quantità, Prezzo, Commissioni */}
      <div className="grid grid-cols-3 gap-3">
        <Input
          label="Quantità"
          type="number"
          step="any"
          error={errors.quantity?.message}
          {...register("quantity")}
        />
        <Input
          label={`Prezzo${selectedAsset && needsFx ? ` (${selectedAsset.currency})` : " (EUR)"}`}
          type="number"
          step="any"
          error={errors.price?.message}
          {...register("price")}
        />
        <Input
          label="Commissioni (EUR)"
          type="number"
          step="any"
          error={errors.fee?.message}
          {...register("fee")}
        />
      </div>

      {/* Tasso di cambio — visibile solo se asset non è in EUR */}
      {needsFx && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-amber-800">
              Tasso di cambio {selectedAsset?.currency}/EUR
            </label>
            <button
              type="button"
              onClick={fetchRate}
              disabled={loadingRate || !date}
              title="Aggiorna dal tasso BCE della data selezionata"
              className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-900 disabled:opacity-40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingRate ? "animate-spin" : ""}`} />
              {loadingRate ? "Caricamento..." : "Tasso BCE"}
            </button>
          </div>
          <input
            type="number"
            step="any"
            min="0.000001"
            {...register("exchange_rate")}
            className="w-full px-3 py-2 border border-amber-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-amber-400 bg-white"
          />
          {errors.exchange_rate && (
            <p className="text-xs text-red-600">{errors.exchange_rate.message}</p>
          )}
          <p className="text-xs text-amber-700">
            1 {selectedAsset?.currency} = {exchangeRate.toFixed(6)} EUR
            {date && ` — tasso del ${date}`}
          </p>
        </div>
      )}

      {/* Riepilogo controvalore */}
      {qty > 0 && price > 0 && (
        <div className="bg-gray-50 rounded-xl px-4 py-3 space-y-1 text-sm">
          {needsFx && (
            <div className="flex justify-between text-gray-500">
              <span>Controvalore in {selectedAsset?.currency}</span>
              <span>{totalAssetCurrency.toLocaleString("it-IT", { minimumFractionDigits: 2 })} {selectedAsset?.currency}</span>
            </div>
          )}
          <div className="flex justify-between font-semibold text-gray-900">
            <span>Totale EUR (incl. comm.)</span>
            <span>€ {totalEur.toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      )}

      <Input label="Note (opzionale)" {...register("notes")} />

      <Button type="submit" loading={isPending} disabled={!selectedAsset} className="w-full">
        Salva transazione
      </Button>
    </form>
  );
}
