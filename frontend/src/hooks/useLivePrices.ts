import { useEffect, useRef, useState } from "react";
import type { PriceOut } from "@/services/prices";

type PriceMap = Record<number, PriceOut>;

/**
 * Connette al WebSocket /ws/prices e mantiene aggiornata una mappa
 * asset_id → PriceOut con i prezzi live.
 *
 * @param assetIds  Lista di asset_id da seguire (stringa separata da virgole)
 */
export function useLivePrices(assetIds: number[]): PriceMap {
  const [prices, setPrices] = useState<PriceMap>({});
  const wsRef = useRef<WebSocket | null>(null);
  const assetIdsKey = assetIds.sort().join(",");

  useEffect(() => {
    if (assetIds.length === 0) return;

    const token = localStorage.getItem("access_token");
    if (!token) return;

    const wsBase = window.location.origin.replace(/^http/, "ws");
    const url = `${wsBase}/ws/prices?token=${token}&asset_ids=${assetIdsKey}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PriceOut & { asset_id: number };
        setPrices((prev) => ({
          ...prev,
          [data.asset_id]: data,
        }));
      } catch {
        // ignora messaggi malformati
      }
    };

    ws.onerror = () => ws.close();

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [assetIdsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return prices;
}
