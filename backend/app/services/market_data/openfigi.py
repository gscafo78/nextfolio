"""
Client OpenFIGI per la risoluzione ISIN → ticker Yahoo Finance.

Documentazione: https://www.openfigi.com/api
Limit: 25 richieste/min senza auth, 250/min con API key.
"""

import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openfigi.com/v3/mapping"

# Mappa exchCode OpenFIGI → suffisso Yahoo Finance
# Ordine di preferenza: London > XETRA > Milan > Paris > Amsterdam > altri
_EXCH_SUFFIX: dict[str, str] = {
    "LN": ".L",    # London Stock Exchange
    "GR": ".DE",   # XETRA
    "GF": ".F",    # Frankfurt Börse
    "IM": ".MI",   # Borsa Italiana (Milan)
    "FP": ".PA",   # Euronext Paris
    "NA": ".AS",   # Euronext Amsterdam
    "BB": ".BR",   # Euronext Brussels
    "SS": ".ST",   # Stockholm
    "HM": ".HE",   # Helsinki
    "DC": ".CO",   # Copenhagen
    "OL": ".OL",   # Oslo
    "VX": ".SW",   # SIX Swiss Exchange
    "SM": ".MC",   # Madrid
    "PW": ".WA",   # Warsaw
    "BU": ".BD",   # Budapest
}

# Preferenze per ETF/fondi (liquidità di solito su London o XETRA)
_PREFERRED_ETF: list[str] = ["LN", "GR", "FP", "NA", "IM"]
# Preferenze per obbligazioni
_PREFERRED_BOND: list[str] = ["GR", "LN", "FP", "IM"]
# Preferenze per azioni italiane
_PREFERRED_STOCK_IT: list[str] = ["IM", "LN", "GR"]


def _headers() -> dict:
    key = settings.OPENFIGI_APY_KEY
    h = {"Content-Type": "application/json"}
    if key:
        h["X-OPENFIGI-APIKEY"] = key
    return h


def _pick_best(results: list[dict], preferred_codes: list[str]) -> dict | None:
    """Sceglie il risultato con il codice borsa più preferito."""
    if not results:
        return None
    by_code = {r["exchCode"]: r for r in results}
    for code in preferred_codes:
        if code in by_code:
            return by_code[code]
    return results[0]


def _to_yf_symbol(record: dict) -> str | None:
    """Converte un record OpenFIGI in ticker Yahoo Finance."""
    ticker = record.get("ticker", "")
    exch_code = record.get("exchCode", "")
    if not ticker:
        return None
    suffix = _EXCH_SUFFIX.get(exch_code, "")
    return f"{ticker}{suffix}"


async def resolve_isin(
    isin: str,
    preferred_exchange: str | None = None,
    security_type: str = "etf",
) -> str | None:
    """
    Risolve un ISIN al ticker Yahoo Finance via OpenFIGI.

    Args:
        isin: codice ISIN (12 caratteri)
        preferred_exchange: exchCode specifico da preferire (es. "LN")
        security_type: "etf", "bond", "stock"

    Returns:
        Ticker Yahoo Finance (es. "SWDA.L") o None se non trovato.
    """
    preferred_codes = (
        [preferred_exchange] + _PREFERRED_ETF if preferred_exchange
        else _PREFERRED_ETF if security_type in ("etf",)
        else _PREFERRED_BOND if security_type == "bond"
        else _PREFERRED_STOCK_IT
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _BASE_URL,
                headers=_headers(),
                json=[{"idType": "ID_ISIN", "idValue": isin}],
            )
            resp.raise_for_status()
            data = resp.json()

        if not data or not data[0].get("data"):
            logger.debug(f"[OpenFIGI] {isin}: nessun risultato")
            return None

        results = data[0]["data"]
        record = _pick_best(results, preferred_codes)
        if record is None:
            return None

        yf_sym = _to_yf_symbol(record)
        logger.info(f"[OpenFIGI] {isin} → {yf_sym} (exch={record.get('exchCode')})")
        return yf_sym

    except Exception as e:
        logger.warning(f"[OpenFIGI] errore per {isin}: {e}")
        return None


async def resolve_isins_bulk(
    isins: list[str],
    security_type: str = "etf",
) -> dict[str, str | None]:
    """
    Risolve più ISIN in una sola chiamata HTTP (limite: 100 per request).
    Restituisce {isin: yf_ticker | None}.
    """
    if not isins:
        return {}

    # OpenFIGI limita a 100 per request
    chunks = [isins[i:i + 100] for i in range(0, len(isins), 100)]
    result: dict[str, str | None] = {}

    preferred_codes = (
        _PREFERRED_ETF if security_type in ("etf",)
        else _PREFERRED_BOND if security_type == "bond"
        else _PREFERRED_STOCK_IT
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in chunks:
                payload = [{"idType": "ID_ISIN", "idValue": isin} for isin in chunk]
                resp = await client.post(
                    _BASE_URL,
                    headers=_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                for isin, item in zip(chunk, data):
                    records = item.get("data") or []
                    record = _pick_best(records, preferred_codes)
                    result[isin] = _to_yf_symbol(record) if record else None
                    if result[isin]:
                        logger.debug(f"[OpenFIGI bulk] {isin} → {result[isin]}")

                if len(chunks) > 1:
                    await asyncio.sleep(0.25)  # rate limit gentile

    except Exception as e:
        logger.warning(f"[OpenFIGI bulk] errore: {e}")
        for isin in isins:
            result.setdefault(isin, None)

    return result
