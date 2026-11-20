"""
Dati di mercato per titoli NON ancora presenti in Nextfolio (Yahoo Finance).

Usato dalla pagina Pianifica: ricerca, scheda titolo, simulazioni, confronto.
Tutto è in cache Redis per non martellare Yahoo:
  - ricerca          24 h   ext:search:{q}
  - prezzo corrente  15 min ext:quote:{symbol}
  - storico          12 h   ext:hist:{symbol}:{period}
  - profilo          7 gg   ext:profile:{symbol}
Prezzi e storico sono convertiti in EUR come per gli asset in portafoglio.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from app.models.asset import AssetType, Exchange

logger = logging.getLogger(__name__)

try:  # nel container la home non è scrivibile: cache di yfinance in /tmp
    import yfinance as _yf
    _yf.set_tz_cache_location("/tmp/py-yfinance")
except Exception:  # pragma: no cover
    pass

_TTL_SEARCH = 24 * 3600
_TTL_QUOTE = 15 * 60
_TTL_HISTORY = 12 * 3600
_TTL_PROFILE = 7 * 24 * 3600

# quoteType Yahoo → AssetType (gli altri tipi, es. INDEX/FUTURE/OPTION, non sono acquistabili)
_QUOTE_TYPES = {
    "EQUITY": AssetType.STOCK,
    "ETF": AssetType.ETF,
    "MUTUALFUND": AssetType.ETF,
    "CRYPTOCURRENCY": AssetType.CRYPTO,
}
# exchange Yahoo → Exchange (gli altri restano OTHER con yahoo_ticker esplicito)
_EXCHANGES = {
    "MIL": Exchange.MIL, "GER": Exchange.XETRA, "XETRA": Exchange.XETRA, "NYQ": Exchange.NYSE,
    "NMS": Exchange.NASDAQ, "NGM": Exchange.NASDAQ, "NCM": Exchange.NASDAQ, "CCC": Exchange.CRYPTO,
}


def _currency_of(raw: str | None) -> tuple[str, float]:
    """Valuta ISO e fattore: Yahoo quota alcuni titoli londinesi in pence ("GBp") e sudafricani in "ZAc"."""
    raw = raw or "EUR"
    if raw in ("GBp", "GBX"):
        return "GBP", 0.01
    if raw in ("ZAc", "ZAC"):
        return "ZAR", 0.01
    if raw == "ILA":
        return "ILS", 0.01
    return raw.upper(), 1.0


async def _cache_get(key: str):
    try:
        from app.services.market_data.updater import _redis
        async with _redis() as r:
            raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:  # Redis non disponibile: si procede senza cache
        logger.debug("cache get %s: %s", key, e)
        return None


async def _cache_set(key: str, value, ttl: int) -> None:
    try:
        from app.services.market_data.updater import _redis
        async with _redis() as r:
            await r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.debug("cache set %s: %s", key, e)


def _yf_search_sync(q: str, limit: int) -> list[dict]:
    import yfinance as yf
    return yf.Search(q, max_results=limit, news_count=0).quotes or []


def map_yahoo_quote(q: dict) -> dict | None:
    """Converte un risultato di yf.Search nel formato dei risultati di ricerca."""
    t = _QUOTE_TYPES.get((q.get("quoteType") or "").upper())
    symbol = q.get("symbol")
    if t is None or not symbol:
        return None
    return {
        "source": "yahoo",
        "asset_id": None,
        "symbol": symbol,
        "ticker": symbol.split(".")[0],
        "name": q.get("longname") or q.get("shortname") or symbol,
        "isin": None,
        "type": t.value,
        "exchange": _EXCHANGES.get((q.get("exchange") or "").upper(), Exchange.OTHER).value,
        "exchange_label": q.get("exchDisp") or q.get("exchange"),
        "currency": None,
    }


async def search_yahoo(q: str, limit: int = 10, search_fn: Callable[[str, int], list[dict]] | None = None) -> list[dict]:
    key = f"ext:search:{q.strip().lower()}"
    cached = await _cache_get(key)
    if cached is not None:
        return cached
    fn = search_fn or _yf_search_sync
    try:
        quotes = await asyncio.get_running_loop().run_in_executor(None, fn, q, limit)
    except Exception as e:
        logger.warning("Ricerca Yahoo '%s' non riuscita: %s", q, e)
        return []
    out = [m for m in (map_yahoo_quote(x) for x in quotes) if m]
    await _cache_set(key, out, _TTL_SEARCH)
    return out


async def quote_eur(symbol: str) -> dict | None:
    """{price, price_eur, currency, change_pct} o None."""
    key = f"ext:quote:{symbol}"
    cached = await _cache_get(key)
    if cached is not None:
        return cached
    from app.services.market_data.updater import _cached_eur_rate
    from app.services.market_data.yahoo import get_current_price_async

    data = await get_current_price_async(symbol, Exchange.OTHER)
    if not data:
        return None
    currency, factor = _currency_of(data.get("currency"))
    data["price"] *= factor
    try:
        rate = await _cached_eur_rate(currency)
    except Exception:
        rate = None
    if rate is None:
        return None
    out = {"price": data["price"], "price_eur": data["price"] * rate, "currency": currency,
           "change_pct": data.get("change_pct")}
    await _cache_set(key, out, _TTL_QUOTE)
    return out


async def history_eur(symbol: str, period: str = "1y") -> list[dict]:
    """Storico giornaliero [{date, close}] in EUR."""
    key = f"ext:hist:{symbol}:{period}"
    cached = await _cache_get(key)
    if cached is not None:
        return cached
    from app.services.market_data.updater import _convert_history_to_eur
    from app.services.market_data.yahoo import get_current_price_async, get_price_history_async

    records = await get_price_history_async(symbol, Exchange.OTHER, period=period)
    if not records:
        return []
    info = await get_current_price_async(symbol, Exchange.OTHER) or {}
    currency, factor = _currency_of(info.get("currency"))
    if factor != 1:
        records = [{**r, "close": r["close"] * factor if r.get("close") else r.get("close")} for r in records]
    records = await _convert_history_to_eur(records, currency)
    out = [{"date": r["date"], "close": r["close"]} for r in records if r.get("close")]
    await _cache_set(key, out, _TTL_HISTORY)
    return out


async def profile(symbol: str, asset_type: str) -> dict:
    """Settori, paesi e top holdings (look-through) senza salvare nulla."""
    key = f"ext:profile:{symbol}"
    cached = await _cache_get(key)
    if cached is not None:
        return cached
    from app.services.market_data.enricher import _enrich_sync

    try:
        data = await asyncio.get_running_loop().run_in_executor(None, _enrich_sync, symbol, AssetType(asset_type))
    except Exception as e:
        logger.warning("Profilo Yahoo %s non disponibile: %s", symbol, e)
        data = {}
    await _cache_set(key, data, _TTL_PROFILE)
    return data
