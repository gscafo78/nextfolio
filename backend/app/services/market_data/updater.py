"""
Aggiorna i prezzi nel DB e pubblica su Redis per WebSocket.

Logica di selezione della fonte dati:
  1. Asset italiano con ISIN (MIL / EuroTLX / MOT)
       → Borsa Italiana API (fonte ufficiale, via ISIN)
       → fallback: Yahoo Finance (.MI)
  2. Azioni / ETF su mercati esteri (NYSE, NASDAQ, XETRA)
       → Yahoo Finance
  3. Crypto
       → CoinGecko
"""

import json
import logging
from datetime import date

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.asset import Asset, AssetType, Exchange, PriceHistory
from app.services.market_data import borsa_italiana as bi
from app.services.market_data.coingecko import get_bulk_crypto_prices, get_crypto_price
from app.services.market_data.yahoo import get_current_price as yf_price
from app.services.market_data.yahoo import get_price_history as yf_history

logger = logging.getLogger(__name__)

_CACHE_TTL_STOCK = 5 * 60   # 5 minuti
_CACHE_TTL_CRYPTO = 60       # 1 minuto


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ── Cache ───────────────────────────────────────────────────────────────────


async def cache_price(asset_id: int, data: dict, ttl: int) -> None:
    async with _redis() as r:
        await r.setex(f"price:{asset_id}", ttl, json.dumps(data))


async def get_cached_price(asset_id: int) -> dict | None:
    async with _redis() as r:
        raw = await r.get(f"price:{asset_id}")
        return json.loads(raw) if raw else None


async def publish_price_update(asset_id: int, data: dict) -> None:
    async with _redis() as r:
        await r.publish("prices", json.dumps({"asset_id": asset_id, **data}))


# ── Selezione fonte ─────────────────────────────────────────────────────────


def _is_italian_market(exchange: Exchange) -> bool:
    return bi.supports_exchange(exchange)


async def _fetch_current_price(asset: Asset) -> dict | None:
    """
    Recupera il prezzo corrente scegliendo la fonte migliore.
    Borsa Italiana → Yahoo Finance → CoinGecko (solo crypto).
    """
    if asset.type == AssetType.CRYPTO:
        return await get_crypto_price(asset.symbol)

    # Asset italiani con ISIN: fonte primaria = Borsa Italiana
    if asset.isin and _is_italian_market(asset.exchange):
        try:
            data = await bi.get_current_price(asset.isin, asset.exchange)
            if data and data.get("price") is not None:
                logger.debug(f"[BI] {asset.symbol} ({asset.isin}): {data['price']}")
                return data
        except Exception as e:
            logger.warning(f"[BI] {asset.symbol} fallito ({e}), fallback Yahoo")

    # Fallback / asset esteri: Yahoo Finance
    data = yf_price(asset.symbol, asset.exchange)
    if data:
        logger.debug(f"[YF] {asset.symbol}: {data['price']}")
    return data


async def _fetch_history(
    asset: Asset,
    period: str = "1y",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """
    Scarica storico OHLCV scegliendo la fonte migliore.
    """
    if asset.type == AssetType.CRYPTO:
        from app.services.market_data.coingecko import get_crypto_history
        period_days = {"1w": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "3y": 1095, "5y": 1825, "max": 2000}
        return await get_crypto_history(asset.symbol, days=period_days.get(period, 365))

    if asset.isin and _is_italian_market(asset.exchange):
        try:
            records = await bi.get_history(
                asset.isin, asset.exchange,
                start_date=start_date, end_date=end_date,
                fill_gaps=True,
            )
            if records:
                logger.info(f"[BI] storico {asset.symbol}: {len(records)} record")
                return records
        except Exception as e:
            logger.warning(f"[BI] storico {asset.symbol} fallito ({e}), fallback Yahoo")

    return yf_history(asset.symbol, asset.exchange, period=period)


# ── Aggiornamento singolo asset ─────────────────────────────────────────────


async def refresh_asset_price(db: AsyncSession, asset: Asset) -> dict | None:
    data = await _fetch_current_price(asset)
    if not data or data.get("price") is None:
        return None

    ttl = _CACHE_TTL_CRYPTO if asset.type == AssetType.CRYPTO else _CACHE_TTL_STOCK
    await cache_price(asset.id, data, ttl)
    await publish_price_update(asset.id, data)
    return data


async def upsert_price_history(db: AsyncSession, asset_id: int, records: list[dict]) -> int:
    if not records:
        return 0

    written = 0
    for r in records:
        d = date.fromisoformat(r["date"])
        result = await db.execute(
            select(PriceHistory).where(
                PriceHistory.asset_id == asset_id,
                PriceHistory.date == d,
            )
        )
        row = result.scalar_one_or_none()
        close = r.get("close") or r.get("marketPrice")
        if close is None:
            continue

        if row:
            row.close = close
            if r.get("open"):
                row.open = r["open"]
            if r.get("high"):
                row.high = r["high"]
            if r.get("low"):
                row.low = r["low"]
            if r.get("volume"):
                row.volume = r["volume"]
        else:
            db.add(PriceHistory(
                asset_id=asset_id,
                date=d,
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=close,
                volume=r.get("volume"),
            ))
        written += 1

    await db.commit()
    return written


# ── Aggiornamento bulk ──────────────────────────────────────────────────────


async def refresh_all_stock_prices(db: AsyncSession) -> int:
    result = await db.execute(
        select(Asset).where(
            Asset.type.in_([AssetType.STOCK, AssetType.ETF, AssetType.BOND, AssetType.REIT])
        )
    )
    assets = list(result.scalars())
    count = 0
    for asset in assets:
        data = await refresh_asset_price(db, asset)
        if data:
            count += 1
    return count


async def refresh_all_crypto_prices(db: AsyncSession) -> int:
    result = await db.execute(select(Asset).where(Asset.type == AssetType.CRYPTO))
    assets = list(result.scalars())
    if not assets:
        return 0

    prices = await get_bulk_crypto_prices([a.symbol for a in assets])
    count = 0
    for asset in assets:
        data = prices.get(asset.symbol)
        if data and data.get("price") is not None:
            await cache_price(asset.id, data, _CACHE_TTL_CRYPTO)
            await publish_price_update(asset.id, data)
            count += 1
    return count


async def fetch_asset_history(
    asset: Asset,
    period: str = "1y",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Entry point pubblico per scaricare lo storico di un asset."""
    return await _fetch_history(asset, period, start_date, end_date)
