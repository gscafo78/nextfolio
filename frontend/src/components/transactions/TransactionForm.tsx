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

const CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"];

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
  const [priceCurrency, setPriceCurrency] = useState("EUR");
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
  // Coerce to number to prevent string-concatenation in total calculation
  const qty = Number(watch("quantity")) || 0;
  const price = Number(watch("price")) || 0;
  const exchangeRate = Number(watch("exchange_rate")) || 1;
  const fee = Number(watch("fee")) || 0;
  const txType = watch("type");

  const needsFx = priceCurrency !== "EUR";
  const totalAssetCurrency = qty * price;
  // BUY: fee is a cost (add). SELL/COUPON/DIVIDEND/INTEREST: fee reduces proceeds (subtract).
  const feeSign = txType === "BUY" ? 1 : -1;
  const totalEur = totalAssetCurrency * exchangeRate + feeSign * fee;

  // When a different asset is selected, default price currency to the asset's currency
  useEffect(() => {
    if (selectedAsset) {
      setPriceCurrency(selectedAsset.currency);
    }
  }, [selectedAsset]);

  // Fetch historical FX rate when price currency or date changes
  const fetchRate = async () => {
    if (!needsFx) return;
    setLoadingRate(true);
    try {
      const result = await fxService.getRate(priceCurrency, date || undefined);
      setValue("exchange_rate", result.rate);
    } catch {
      // keep current rate if API fails
    } finally {
      setLoadingRate(false);
    }
  };

  useEffect(() => {
    if (needsFx && date) fetchRate();
    if (!needsFx) setValue("exchange_rate", 1);
  }, [priceCurrency, date]); // eslint-disable-line react-hooks/exhaustive-deps

  const { mutate, isPending } = useMutation({
    mutationFn: (data: FormData) => {
      if (!selectedAsset) throw new Error("Seleziona un asset");
      return transactionService.create({
        ...data,
        asset_id: selectedAsset.id,
        price_currency: priceCurrency,
        fee_currency: "EUR",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      reset();
      setSelectedAsset(null);
      setPriceCurrency("EUR");
      onSuccess?.();
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-4">
      {/* Asset */}
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">Asset</label>
        <AssetAutocomplete onSelect={(asset) => setSelectedAsset(asset)} />
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

      {/* Quantità + Prezzo con valuta + Commissioni */}
      <div className="grid grid-cols-3 gap-3">
        <Input
          label="Quantità"
          type="number"
          inputMode="decimal"
          step="any"
          error={errors.quantity?.message}
          {...register("quantity")}
        />

        {/* Prezzo + selettore valuta inline */}
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">Prezzo</label>
          <div className="flex rounded-lg border border-gray-300 overflow-hidden focus-within:ring-2 focus-within:ring-brand-500">
            <input
              type="number"
              inputMode="decimal"
              step="any"
              className="flex-1 min-w-0 px-3 py-2 text-sm outline-none bg-white"
              {...register("price")}
            />
            <select
              value={priceCurrency}
              onChange={(e) => setPriceCurrency(e.target.value)}
              className="border-l border-gray-300 px-2 py-2 text-xs bg-gray-50 text-gray-700 outline-none cursor-pointer"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          {errors.price && <p className="text-xs text-red-600">{errors.price.message}</p>}
        </div>

        <Input
          label="Commissioni (EUR)"
          type="number"
          inputMode="decimal"
          step="any"
          error={errors.fee?.message}
          {...register("fee")}
        />
      </div>

      {/* Tasso di cambio — visibile solo se prezzo non è in EUR */}
      {needsFx && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-amber-800">
              Tasso di cambio {priceCurrency}/EUR
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
            inputMode="decimal"
            step="any"
            min="0.000001"
            {...register("exchange_rate")}
            className="w-full px-3 py-2 border border-amber-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-amber-400 bg-white"
          />
          {errors.exchange_rate && (
            <p className="text-xs text-red-600">{errors.exchange_rate.message}</p>
          )}
          <p className="text-xs text-amber-700">
            1 {priceCurrency} = {exchangeRate.toFixed(6)} EUR
            {date && ` — tasso del ${date}`}
          </p>
        </div>
      )}

      {/* Riepilogo controvalore */}
      {qty > 0 && price > 0 && (
        <div className="bg-gray-50 rounded-xl px-4 py-3 space-y-1 text-sm">
          {needsFx && (
            <div className="flex justify-between text-gray-500">
              <span>Controvalore in {priceCurrency}</span>
              <span>{totalAssetCurrency.toLocaleString("it-IT", { minimumFractionDigits: 2 })} {priceCurrency}</span>
            </div>
          )}
          {fee > 0 && (
            <div className="flex justify-between text-gray-500">
              <span>Commissioni</span>
              <span className={feeSign > 0 ? "text-red-500" : "text-gray-500"}>
                {feeSign > 0 ? "+" : "−"} € {fee.toLocaleString("it-IT", { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
          <div className="flex justify-between font-semibold text-gray-900 pt-1 border-t border-gray-200">
            <span>{txType === "BUY" ? "Totale costo EUR" : "Totale netto EUR"}</span>
            <span>€ {totalEur.toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
          </div>
          {(txType === "COUPON" || txType === "DIVIDEND") && (
            <p className="text-xs text-gray-400 pt-0.5">
              La ritenuta fiscale (12,5% BTP / 26% altri) è calcolata automaticamente nella sezione Fiscale.
            </p>
          )}
        </div>
      )}

      <Input label="Note (opzionale)" {...register("notes")} />

      <Button type="submit" loading={isPending} disabled={!selectedAsset} className="w-full">
        Salva transazione
      </Button>
    </form>
  );
}
