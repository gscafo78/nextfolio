import { TrendingDown, TrendingUp } from "lucide-react";
import type { PriceOut } from "@/services/prices";
import { getIntlLocale } from "@/utils/format";
import i18n from "@/i18n";

interface PriceTickerProps {
  price: PriceOut;
  showSymbol?: boolean;
}

export function PriceTicker({ price, showSymbol = true }: PriceTickerProps) {
  const positive = price.change_pct >= 0;
  const color = positive ? "text-green-600" : "text-red-600";
  const bg = positive ? "bg-green-50" : "bg-red-50";
  const Icon = positive ? TrendingUp : TrendingDown;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${bg}`}>
      {showSymbol && (
        <span className="text-xs font-semibold text-gray-600">{price.symbol}</span>
      )}
      <span className="text-sm font-bold text-gray-900">
        {price.price.toLocaleString(getIntlLocale(i18n.language), { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {price.currency}
      </span>
      <span className={`flex items-center gap-0.5 text-xs font-semibold ${color}`}>
        <Icon className="w-3 h-3" />
        {positive ? "+" : ""}{price.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}
