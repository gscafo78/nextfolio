"""
Asset enrichment via Yahoo Finance.

- Stock / REIT: sector, country from yf.Ticker.info
- ETF / BOND:   sector_weightings + top 10 holdings from yf.Ticker.get_funds_data()
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType, Exchange

logger = logging.getLogger(__name__)

# ── Mappatura settori Yahoo → etichette uniformi ─────────────────────────────

_SECTOR_MAP = {
    "technology": "Technology",
    "financial_services": "Financial Services",
    "financials": "Financial Services",
    "healthcare": "Healthcare",
    "consumer_cyclical": "Consumer Cyclical",
    "consumer_defensive": "Consumer Defensive",
    "industrials": "Industrials",
    "basic_materials": "Basic Materials",
    "communication_services": "Communication Services",
    "energy": "Energy",
    "utilities": "Utilities",
    "realestate": "Real Estate",
    "real_estate": "Real Estate",
    "Technology": "Technology",
    "Financial Services": "Financial Services",
    "Healthcare": "Healthcare",
    "Consumer Cyclical": "Consumer Cyclical",
    "Consumer Defensive": "Consumer Defensive",
    "Industrials": "Industrials",
    "Basic Materials": "Basic Materials",
    "Communication Services": "Communication Services",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
}


def _normalize_sector(raw: str) -> str:
    return _SECTOR_MAP.get(raw, raw)


def _get_yf_symbol_sync(asset: Asset) -> str | None:
    """
    Restituisce il ticker Yahoo per l'enrichment.
    Se il symbol è un ISIN, usa resolve_ticker_by_isin via asyncio.
    """
    if asset.yahoo_ticker:
        return asset.yahoo_ticker
    from app.services.market_data.yahoo import _is_isin, _ticker
    if _is_isin(asset.symbol):
        # ISIN come symbol: lo risolviamo nel chiamante async
        return None  # segnale: usare resolve_ticker_by_isin
    return _ticker(asset.symbol, asset.exchange)


async def _resolve_yf_symbol(asset: Asset) -> str | None:
    """
    Determina il ticker Yahoo Finance per l'enrichment.
    Priorità: yahoo_ticker > OpenFIGI > Yahoo search.
    """
    sym = _get_yf_symbol_sync(asset)
    if sym is not None:
        return sym

    from app.services.market_data.yahoo import resolve_ticker_by_isin, _is_isin, _is_isin_like
    isin = asset.isin or (asset.symbol if _is_isin(asset.symbol) else None)
    if not isin:
        return None

    # 1. OpenFIGI — resolver affidabile e strutturato
    from app.services.market_data.openfigi import resolve_isin
    sec_type = (
        "etf" if asset.type in (AssetType.ETF,)
        else "bond" if asset.type in (AssetType.BOND,)
        else "stock"
    )
    ticker = await resolve_isin(isin, security_type=sec_type)
    if ticker:
        return ticker

    # 2. Fallback Yahoo search
    result = await resolve_ticker_by_isin(isin)
    # Scarta ticker ISIN-like — non funzionano con yfinance
    if result and _is_isin_like(result):
        return None
    return result


def _enrich_sync(symbol: str, asset_type: AssetType) -> dict:
    """
    Chiamata bloccante a Yahoo Finance — va eseguita in run_in_executor.
    Restituisce un dict con sectors, countries, holdings (tutti opzionali).
    """
    import yfinance as yf
    from app.services.market_data.yahoo import _maybe_suppress

    result: dict = {}

    try:
        with _maybe_suppress(symbol):
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}

            if asset_type in (AssetType.STOCK, AssetType.REIT):
                sector = info.get("sector")
                country = info.get("country")
                if sector:
                    result["sectors"] = [{"name": _normalize_sector(sector), "weight": 1.0}]
                if country:
                    result["countries"] = [{"code": country, "name": country, "weight": 1.0}]

            elif asset_type in (AssetType.ETF, AssetType.BOND):
                try:
                    fd = ticker.get_funds_data()
                    if fd is not None:
                        sw = fd.sector_weightings or {}
                        if sw:
                            sectors = [
                                {"name": _normalize_sector(k), "weight": round(float(v), 6)}
                                for k, v in sw.items()
                                if v and float(v) > 0
                            ]
                            sectors.sort(key=lambda x: x["weight"], reverse=True)
                            result["sectors"] = sectors

                        th = fd.top_holdings
                        if th is not None and not th.empty:
                            holdings = []
                            for sym, row in th.head(10).iterrows():
                                holdings.append({
                                    "symbol": str(sym),
                                    "name": str(row.get("Name", sym)),
                                    "weight": round(float(row.get("Holding Percent", 0)), 6),
                                })
                            result["holdings"] = holdings
                except Exception as e:
                    logger.debug(f"[enricher] get_funds_data({symbol}) failed: {e}")

    except Exception as e:
        logger.warning(f"[enricher] yfinance error for {symbol}: {e}")

    return result


# ── Async entry point ─────────────────────────────────────────────────────────


async def enrich_asset(db: AsyncSession, asset: Asset) -> bool:
    """
    Arricchisce un singolo asset con dati settoriali/geografici/holdings.
    Restituisce True se almeno un campo è stato popolato.
    """
    yf_symbol = await _resolve_yf_symbol(asset)
    if not yf_symbol:
        logger.warning(f"[enricher] {asset.symbol}: impossibile determinare il ticker Yahoo")
        return False

    # Ticker non valido (contiene spazi = nome descrittivo, non un ticker)
    if " " in yf_symbol:
        logger.info(f"[enricher] {asset.symbol}: ticker '{yf_symbol}' non valido (contiene spazi)")
        return False

    data = await asyncio.get_running_loop().run_in_executor(
        None, _enrich_sync, yf_symbol, asset.type
    )

    if not data:
        logger.info(f"[enricher] {asset.symbol}: nessun dato trovato")
        return False

    if "sectors" in data:
        asset.sectors = data["sectors"]
    if "countries" in data:
        asset.countries = data["countries"]
    if "holdings" in data:
        asset.holdings = data["holdings"]

    asset.enriched_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        f"[enricher] {asset.symbol}: "
        f"sectors={len(data.get('sectors', []))}, "
        f"countries={len(data.get('countries', []))}, "
        f"holdings={len(data.get('holdings', []))}"
    )
    return True
