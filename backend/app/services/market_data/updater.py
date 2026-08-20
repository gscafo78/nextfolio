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

import datetime as _dt
import json
import logging
import math
from datetime import date

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.asset import Asset, AssetType, Exchange, PriceHistory
from app.services.market_data import borsa_italiana as bi
from app.services.market_data.coingecko import get_bulk_crypto_prices, get_crypto_price
from app.services.market_data.yahoo import get_current_price_async as yf_price
from app.services.market_data.yahoo import get_price_history_async as yf_history
from app.services.market_data.yahoo import resolve_ticker_by_isin, _is_isin, _is_isin_like

logger = logging.getLogger(__name__)

_CACHE_TTL_STOCK = 5 * 60        # 5 min during market hours
_CACHE_TTL_STOCK_EOD = 4 * 3600  # 4 h after market close / weekends
_CACHE_TTL_CRYPTO = 60           # 1 min (crypto always live)


def _stock_ttl() -> int:
    """5 min during Borsa Italiana trading hours, 4 h otherwise."""
    now = _dt.datetime.now(_dt.timezone.utc).astimezone(
        _dt.timezone(_dt.timedelta(hours=2))  # CET/CEST approx
    )
    if now.weekday() < 5 and _dt.time(9, 0) <= now.time() <= _dt.time(17, 30):
        return _CACHE_TTL_STOCK
    return _CACHE_TTL_STOCK_EOD


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


async def get_cached_prices_bulk(asset_ids: list[int]) -> list[dict | None]:
    """Single MGET round-trip for multiple assets."""
    if not asset_ids:
        return []
    async with _redis() as r:
        values = await r.mget(*[f"price:{aid}" for aid in asset_ids])
    return [json.loads(v) if v else None for v in values]


# ── Cache performance ────────────────────────────────────────────────────────

_CACHE_TTL_PERF = 5 * 60  # 5 min — si aggiorna con i prezzi EOD


def _perf_key(user_id: int, period: str, account_id: int | None) -> str:
    return f"perf:{user_id}:{period}:{account_id or 'all'}"


async def get_cached_perf(user_id: int, period: str, account_id: int | None) -> dict | None:
    async with _redis() as r:
        raw = await r.get(_perf_key(user_id, period, account_id))
        return json.loads(raw) if raw else None


async def set_cached_perf(user_id: int, period: str, account_id: int | None, data: dict) -> None:
    async with _redis() as r:
        await r.setex(_perf_key(user_id, period, account_id), _CACHE_TTL_PERF, json.dumps(data))


async def invalidate_perf_cache(user_id: int) -> None:
    """Elimina tutte le chiavi perf:{user_id}:* — chiamato dopo update_prices_eod."""
    async with _redis() as r:
        keys = await r.keys(f"perf:{user_id}:*")
        if keys:
            await r.delete(*keys)


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
    # yahoo_ticker sovrascrive il symbol se impostato dall'utente.
    # Se yahoo_ticker è esplicito, è già un ticker completo → Exchange.OTHER (nessun suffisso).
    yf_symbol = asset.yahoo_ticker or asset.symbol

    # Se il symbol è un ISIN (e non c'è un yahoo_ticker esplicito), cerca subito il
    # ticker corretto via Yahoo Search — evita il tentativo ISIN+suffisso che genera
    # warning "possibly delisted" prima del fallback.
    if not asset.yahoo_ticker and _is_isin(yf_symbol):
        isin_to_search = asset.isin or yf_symbol
        found_ticker = await resolve_ticker_by_isin(isin_to_search)
        # Scarta ticker ISIN-like (es. IE00BTJRMP35.DE) — non funzionano con yfinance
        if found_ticker and not _is_isin_like(found_ticker):
            logger.info(f"[YF-SEARCH] {isin_to_search} → {found_ticker}")
            data = await yf_price(found_ticker, Exchange.OTHER)
            if data:
                return data
        elif found_ticker:
            logger.debug(f"[YF-SEARCH] {isin_to_search} → {found_ticker} (ISIN-like, skipped)")
        return None

    yf_exchange = Exchange.OTHER if asset.yahoo_ticker else asset.exchange
    data = await yf_price(yf_symbol, yf_exchange)
    if data:
        logger.debug(f"[YF] {yf_symbol}: {data['price']}")
        return data

    return None


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

    yf_symbol = asset.yahoo_ticker or asset.symbol

    # Se ISIN senza yahoo_ticker esplicito, risolvi prima il ticker corretto
    if not asset.yahoo_ticker and _is_isin(yf_symbol):
        isin_to_search = asset.isin or yf_symbol
        found_ticker = await resolve_ticker_by_isin(isin_to_search)
        if found_ticker and not _is_isin_like(found_ticker):
            logger.info(f"[YF-SEARCH history] {isin_to_search} → {found_ticker}")
            return await yf_history(found_ticker, Exchange.OTHER, period=period, start_date=start_date, end_date=end_date)
        elif found_ticker:
            logger.debug(f"[YF-SEARCH history] {isin_to_search} → {found_ticker} (ISIN-like, skipped)")
        return []

    yf_exchange = Exchange.OTHER if asset.yahoo_ticker else asset.exchange
    records = await yf_history(yf_symbol, yf_exchange, period=period, start_date=start_date, end_date=end_date)
    if records:
        return records

    return []


# ── Aggiornamento singolo asset ─────────────────────────────────────────────


async def refresh_asset_price(db: AsyncSession, asset: Asset) -> dict | None:
    data = await _fetch_current_price(asset)
    if not data or data.get("price") is None:
        return None

    ttl = _CACHE_TTL_CRYPTO if asset.type == AssetType.CRYPTO else _stock_ttl()
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
        if close is None or (isinstance(close, float) and math.isnan(close)):
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
    return await _fetch_history(asset, period=period, start_date=start_date, end_date=end_date)
