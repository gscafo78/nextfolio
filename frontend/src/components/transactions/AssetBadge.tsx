import type { AssetType, Exchange } from "@/services/transactions";

const TYPE_LABELS: Record<AssetType, string> = {
  STOCK: "Azione",
  ETF: "ETF",
  BOND: "Obbligazione",
  CRYPTO: "Crypto",
  COMMODITY: "Commodity",
  REIT: "REIT",
};

const TYPE_COLORS: Record<AssetType, string> = {
  STOCK: "bg-blue-100 text-blue-700",
  ETF: "bg-green-100 text-green-700",
  BOND: "bg-yellow-100 text-yellow-700",
  CRYPTO: "bg-purple-100 text-purple-700",
  COMMODITY: "bg-orange-100 text-orange-700",
  REIT: "bg-teal-100 text-teal-700",
};

const EXCHANGE_LABELS: Record<Exchange, string> = {
  MIL: "Borsa IT",
  EuroTLX: "EuroTLX",
  MOT: "MOT",
  XETRA: "Xetra",
  NYSE: "NYSE",
  NASDAQ: "NASDAQ",
  CRYPTO: "Crypto",
  OTHER: "",
};

interface AssetBadgeProps {
  type: AssetType;
  exchange?: Exchange;
  size?: "sm" | "md";
}

export function AssetBadge({ type, exchange, size = "sm" }: AssetBadgeProps) {
  const px = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`${px} rounded-full font-medium ${TYPE_COLORS[type]}`}>
        {TYPE_LABELS[type]}
      </span>
      {exchange && exchange !== "OTHER" && (
        <span className={`${px} rounded-full font-medium bg-gray-100 text-gray-600`}>
          {EXCHANGE_LABELS[exchange]}
        </span>
      )}
    </span>
  );
}
