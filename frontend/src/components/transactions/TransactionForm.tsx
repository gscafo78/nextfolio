import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Sparkles, ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getIntlLocale } from "@/utils/format";
import i18n from "@/i18n";
import {
  accountService,
  fxService,
  transactionService,
  type Asset,
} from "@/services/transactions";
import { bondService, type BondDetailCreate, FREQUENCY_LABELS, type CouponFrequency } from "@/services/bonds";
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

const TX_TYPES_LIST = ["BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "INTEREST"] as const;

interface TransactionFormProps {
  onSuccess?: () => void;
}

export function TransactionForm({ onSuccess }: TransactionFormProps) {
  const { t } = useTranslation();
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [priceCurrency, setPriceCurrency] = useState("EUR");
  const [loadingRate, setLoadingRate] = useState(false);
  const [showBondSection, setShowBondSection] = useState(false);
  const [bondFields, setBondFields] = useState<BondDetailCreate>({
    face_value: 100,
    coupon_rate: 0,
    coupon_frequency: "SEMI_ANNUAL",
    first_coupon_date: "",
    maturity_date: "",
    issue_date: "",
  });
  const [enriching, setEnriching] = useState(false);
  const [enrichError, setEnrichError] = useState<string | null>(null);
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
  const qty = Number(watch("quantity")) || 0;
  const price = Number(watch("price")) || 0;
  const exchangeRate = Number(watch("exchange_rate")) || 1;
  const fee = Number(watch("fee")) || 0;
  const txType = watch("type");

  const isBond = selectedAsset?.type === "BOND";
  const isBuyBond = txType === "BUY" && isBond;

  const needsFx = priceCurrency !== "EUR";
  const totalAssetCurrency = qty * price;
  const feeSign = txType === "BUY" ? 1 : -1;
  const totalEur = totalAssetCurrency * exchangeRate + feeSign * fee;

  useEffect(() => {
    if (selectedAsset) {
      setPriceCurrency(selectedAsset.currency);
    }
  }, [selectedAsset]);

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

  // Precarica bond_detail se già esistente per l'asset
  useEffect(() => {
    if (!isBond || !selectedAsset) return;
    bondService.get(selectedAsset.id).then((bd) => {
      if (bd) {
        setBondFields({
          face_value: bd.face_value,
          coupon_rate: bd.coupon_rate * 100, // converti in % per la UI
          coupon_frequency: bd.coupon_frequency,
          first_coupon_date: bd.first_coupon_date,
          maturity_date: bd.maturity_date ?? "",
          issue_date: bd.issue_date ?? "",
        });
        setShowBondSection(true);
      }
    });
  }, [selectedAsset?.id, isBond]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleEnrich = async () => {
    if (!selectedAsset) return;
    setEnriching(true);
    setEnrichError(null);
    try {
      const bd = await bondService.enrich(selectedAsset.id);
      setBondFields({
        face_value: bd.face_value,
        coupon_rate: bd.coupon_rate * 100,
        coupon_frequency: bd.coupon_frequency,
        first_coupon_date: bd.first_coupon_date,
        maturity_date: bd.maturity_date ?? "",
        issue_date: bd.issue_date ?? "",
      });
    } catch {
      setEnrichError("Dati non trovati su Borsa Italiana. Inserisci manualmente.");
    } finally {
      setEnriching(false);
    }
  };

  const { mutate, isPending } = useMutation({
    mutationFn: async (data: FormData) => {
      if (!selectedAsset) throw new Error("Seleziona un asset");
      const tx = await transactionService.create({
        ...data,
        asset_id: selectedAsset.id,
        price_currency: priceCurrency,
        fee_currency: "EUR",
      });
      // Salva bond_detail se la sezione è aperta e i campi sono validi
      if (isBuyBond && showBondSection && bondFields.coupon_rate > 0 && bondFields.first_coupon_date) {
        await bondService.upsert(selectedAsset.id, {
          ...bondFields,
          coupon_rate: bondFields.coupon_rate / 100, // riporta in decimale
          maturity_date: bondFields.maturity_date || null,
          issue_date: bondFields.issue_date || null,
        });
      }
      return tx;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["upcoming-coupons"] });
      reset();
      setSelectedAsset(null);
      setPriceCurrency("EUR");
      setBondFields({ face_value: 100, coupon_rate: 0, coupon_frequency: "SEMI_ANNUAL", first_coupon_date: "", maturity_date: "", issue_date: "" });
      setShowBondSection(false);
      onSuccess?.();
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-4">
      {/* Asset */}
      <div>
        <label className="text-sm font-medium text-gray-700 block mb-1">{t("common.asset")}</label>
        <AssetAutocomplete onSelect={(asset) => setSelectedAsset(asset)} />
      </div>

      {/* Conto + Tipo */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">{t("common.account")}</label>
          <select
            {...register("account_id")}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">{t("transactionForm.selectType")}</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {errors.account_id && <p className="text-xs text-red-600 mt-1">{errors.account_id.message}</p>}
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">{t("common.type")}</label>
          <select
            {...register("type")}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {TX_TYPES_LIST.map((type) => (
              <option key={type} value={type}>{t(`transactions.types.${type}`)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Data */}
      <Input label={t("common.date")} type="date" error={errors.date?.message} {...register("date")} />

      {/* Quantità + Prezzo con valuta + Commissioni */}
      <div className="grid grid-cols-3 gap-3">
        <Input
          label={t("common.quantity")}
          type="number"
          inputMode="decimal"
          step="any"
          error={errors.quantity?.message}
          {...register("quantity")}
        />

        {/* Prezzo + selettore valuta inline */}
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">{t("common.price")}</label>
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
          label={t("transactionForm.fees")}
          type="number"
          inputMode="decimal"
          step="any"
          error={errors.fee?.message}
          {...register("fee")}
        />
      </div>

      {/* Tasso di cambio */}
      {needsFx && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-amber-800">
              {t("transactionForm.fxRate", { currency: priceCurrency })}
            </label>
            <button
              type="button"
              onClick={fetchRate}
              disabled={loadingRate || !date}
              title={t("transactionForm.fxUpdate")}
              className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-900 disabled:opacity-40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingRate ? "animate-spin" : ""}`} />
              {loadingRate ? t("transactionForm.loadingRate") : t("transactionForm.fxLabel")}
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
            {date
              ? t("transactionForm.fxDateNote", { currency: priceCurrency, rate: exchangeRate.toFixed(6), date })
              : t("transactionForm.fxNoteSimple", { currency: priceCurrency, rate: exchangeRate.toFixed(6) })}
          </p>
        </div>
      )}

      {/* Riepilogo controvalore */}
      {qty > 0 && price > 0 && (
        <div className="bg-gray-50 rounded-xl px-4 py-3 space-y-1 text-sm">
          {needsFx && (
            <div className="flex justify-between text-gray-500">
              <span>{t("transactionForm.countervalue", { currency: priceCurrency })}</span>
              <span>{totalAssetCurrency.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 })} {priceCurrency}</span>
            </div>
          )}
          {fee > 0 && (
            <div className="flex justify-between text-gray-500">
              <span>{t("transactionForm.commissions")}</span>
              <span className={feeSign > 0 ? "text-red-500" : "text-gray-500"}>
                {feeSign > 0 ? "+" : "−"} € {fee.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
          <div className="flex justify-between font-semibold text-gray-900 pt-1 border-t border-gray-200">
            <span>{txType === "BUY" ? t("transactionForm.totalCost") : t("transactionForm.totalNet")}</span>
            <span>€ {totalEur.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2 })}</span>
          </div>
          {(txType === "COUPON" || txType === "DIVIDEND") && (
            <p className="text-xs text-gray-400 pt-0.5">
              {t("transactionForm.taxNote")}
            </p>
          )}
        </div>
      )}

      <Input label={t("transactionForm.notes")} {...register("notes")} />

      {/* Dettagli cedola — visibile solo per BUY su BOND */}
      {isBuyBond && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 overflow-hidden">
          <button
            type="button"
            onClick={() => setShowBondSection((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-amber-800 hover:bg-amber-100 transition-colors"
          >
            <span>📅 {t("bonds.couponDetails")}</span>
            <ChevronDown className={`w-4 h-4 text-amber-500 transition-transform ${showBondSection ? "rotate-180" : ""}`} />
          </button>

          {showBondSection && (
            <div className="px-4 pb-4 space-y-3 border-t border-amber-200">
              {/* Enrichment automatico */}
              <div className="flex items-center gap-2 pt-3">
                <button
                  type="button"
                  onClick={handleEnrich}
                  disabled={enriching || !selectedAsset?.isin}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 px-3 py-1.5 text-xs font-medium text-white transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {enriching ? "Carico…" : t("bonds.autoEnrich")}
                </button>
                <span className="text-xs text-amber-700">{t("bonds.autoEnrichDesc")}</span>
              </div>
              {enrichError && <p className="text-xs text-red-600">{enrichError}</p>}

              {/* Campi cedola */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">{t("bonds.couponRate")} (%)</label>
                  <input
                    type="number" step="0.001" min="0" max="100"
                    value={bondFields.coupon_rate}
                    onChange={(e) => setBondFields((p) => ({ ...p, coupon_rate: Number(e.target.value) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="es. 1.65"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">{t("bonds.frequency")}</label>
                  <select
                    value={bondFields.coupon_frequency}
                    onChange={(e) => setBondFields((p) => ({ ...p, coupon_frequency: e.target.value as CouponFrequency }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    {(Object.keys(FREQUENCY_LABELS) as CouponFrequency[]).map((k) => (
                      <option key={k} value={k}>{t(`bonds.freq${k.charAt(0) + k.slice(1).toLowerCase().replace(/_([a-z])/g, (_, c) => c.toUpperCase())}`)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">{t("bonds.firstCouponDate")}</label>
                  <input
                    type="date"
                    value={bondFields.first_coupon_date}
                    onChange={(e) => setBondFields((p) => ({ ...p, first_coupon_date: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">{t("bonds.maturityDate")}</label>
                  <input
                    type="date"
                    value={bondFields.maturity_date ?? ""}
                    onChange={(e) => setBondFields((p) => ({ ...p, maturity_date: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>
              {bondFields.coupon_rate > 0 && (
                <p className="text-xs text-amber-700">
                  {t("bonds.couponPerUnit")}: <strong>€ {((100 * bondFields.coupon_rate / 100) / (bondFields.coupon_frequency === "SEMI_ANNUAL" ? 2 : bondFields.coupon_frequency === "QUARTERLY" ? 4 : bondFields.coupon_frequency === "MONTHLY" ? 12 : 1)).toFixed(3)}</strong> / unità
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <Button type="submit" loading={isPending} disabled={!selectedAsset} className="w-full">
        {t("transactionForm.submit")}
      </Button>
    </form>
  );
}
