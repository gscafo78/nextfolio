"""
Client per l'API non ufficiale di Borsa Italiana (grafici.borsaitaliana.it).

Funziona per tutti i mercati italiani via ISIN:
  - XMIL  → Mercato Azionario (azioni, ETC, ETF)
  - ETLX  → EuroTLX (obbligazioni corporate, ETF)
  - MOTX  → MOT (BTP, BOT, CCT, obbligazioni gov.)
  - HIMTF → Hi-MTF

Approccio (ripreso da ghostfolio-feeder):
  1. GET dell'iframe dei grafici → estrae il JWT anonimo
  2. Chiama l'API /history con il JWT → storico OHLC completo
  3. Chiama l'API /price con il JWT → prezzo corrente

Non richiede API key né login.
"""

import random
import re
from datetime import date, datetime, timedelta

import httpx

from app.models.asset import Exchange

# Mappa Exchange enum → codice mercato Borsa Italiana
_EXCHANGE_TO_MIC: dict[Exchange, str] = {
    Exchange.MIL: "XMIL",
    Exchange.EUROTLX: "ETLX",
    Exchange.MOT: "MOTX",
}

_GRAFICI_BASE = "https://grafici.borsaitaliana.it"
_TIMEOUT = 10.0

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


def _ua() -> str:
    return random.choice(_USER_AGENTS)


def _base_headers(referer: str = "https://www.borsaitaliana.it/") -> dict:
    return {
        "User-Agent": _ua(),
        "Referer": referer,
        "Accept": "application/json",
    }


async def _get_jwt(isin: str, mic: str) -> str:
    """
    Recupera il JWT anonimo dall'iframe del grafico.
    Nessun login richiesto — il token è incorporato nel markup della pagina.
    """
    url = f"{_GRAFICI_BASE}/summary-chart/{isin}-{mic}"
    async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
        resp = await client.get(url, headers=_base_headers())
        resp.raise_for_status()

    match = re.search(r'token="([^"]+)"', resp.text)
    if not match:
        raise ValueError(f"JWT non trovato per {isin}-{mic}")
    return match.group(1)


def _mic_from_exchange(exchange: Exchange) -> str:
    mic = _EXCHANGE_TO_MIC.get(exchange)
    if not mic:
        raise ValueError(f"Exchange {exchange} non supportato da Borsa Italiana")
    return mic


def _parse_dt(dt_str: str) -> date:
    """'20240315' → date(2024, 3, 15)"""
    return datetime.strptime(dt_str, "%Y%m%d").date()


def _fill_missing_dates(records: list[dict], start: date | None, end: date | None) -> list[dict]:
    """
    Propaga il prezzo di chiusura ai giorni mancanti (weekend, festivi).
    Equivalente a utils.fill_missing_dates del ghostfolio-feeder.
    """
    if not records:
        return records

    records = sorted(records, key=lambda r: r["date"])

    # Aggiungi start/end se richiesti
    if start and start.isoformat() < records[0]["date"]:
        records.insert(0, {**records[0], "date": start.isoformat()})
    target_end = (end or date.today()).isoformat()
    if target_end > records[-1]["date"]:
        records.append({**records[-1], "date": target_end})

    filled: list[dict] = []
    for i, rec in enumerate(records):
        if i > 0:
            prev_date = date.fromisoformat(filled[-1]["date"])
            curr_date = date.fromisoformat(rec["date"])
            gap = curr_date - prev_date
            for d in range(1, gap.days):
                filled.append({**filled[-1], "date": (prev_date + timedelta(days=d)).isoformat()})
        filled.append(rec)

    # Filtra per range richiesto
    if start:
        filled = [r for r in filled if r["date"] >= start.isoformat()]
    if end:
        filled = [r for r in filled if r["date"] <= end.isoformat()]

    return filled


# ── API pubblica ────────────────────────────────────────────────────────────


async def get_history(
    isin: str,
    exchange: Exchange,
    start_date: date | None = None,
    end_date: date | None = None,
    fill_gaps: bool = True,
) -> list[dict]:
    """
    Storico prezzi di chiusura per un ISIN su Borsa Italiana.

    Restituisce lista di dict nel formato standard di Nextfolio:
      {"date": "yyyy-mm-dd", "close": float, "open": ..., "high": ..., "low": ..., "volume": ...}
    """
    mic = _mic_from_exchange(exchange)
    token = await _get_jwt(isin, mic)

    url = f"{_GRAFICI_BASE}/api/instruments/{isin},{mic},ISIN/history/period"
    params = {"period": "MAX", "adjustment": "true", "add-last-price": "true"}
    headers = {**_base_headers(_GRAFICI_BASE + "/"), "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()

    raw: list[dict] = resp.json()["history"]["historyDt"]

    records = []
    for item in raw:
        records.append({
            "date": _parse_dt(item["dt"]).isoformat(),
            "close": float(item["closePx"]),
            "open": float(item["openPx"]) if item.get("openPx") else None,
            "high": float(item["highPx"]) if item.get("highPx") else None,
            "low": float(item["lowPx"]) if item.get("lowPx") else None,
            "volume": float(item["tradedQty"]) if item.get("tradedQty") else None,
        })

    if fill_gaps:
        records = _fill_missing_dates(records, start_date, end_date)
    elif start_date or end_date:
        if start_date:
            records = [r for r in records if r["date"] >= start_date.isoformat()]
        if end_date:
            records = [r for r in records if r["date"] <= end_date.isoformat()]

    return records


async def get_current_price(isin: str, exchange: Exchange) -> dict | None:
    """
    Prezzo corrente / ultimo disponibile per un ISIN.

    Restituisce:
      {"price": float, "prev_close": float|None, "change_pct": float, "currency": "EUR"}
    """
    mic = _mic_from_exchange(exchange)
    try:
        token = await _get_jwt(isin, mic)
    except Exception:
        return None

    url = f"{_GRAFICI_BASE}/api/instruments/{isin},{mic},ISIN/price"
    headers = {**_base_headers(_GRAFICI_BASE + "/"), "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # Fallback: usa l'ultimo prezzo dallo storico
            try:
                history = await get_history(isin, exchange, fill_gaps=False)
                if not history:
                    return None
                last = history[-1]
                prev = history[-2] if len(history) >= 2 else last
                price = last["close"]
                prev_close = prev["close"]
                return {
                    "price": price,
                    "prev_close": prev_close,
                    "change_pct": round((price - prev_close) / prev_close * 100, 4) if prev_close else 0.0,
                    "currency": "EUR",
                }
            except Exception:
                return None

    # Struttura risposta API /price
    price = data.get("lastPrice") or data.get("price")
    prev_close = data.get("refPrice") or data.get("previousClose")
    if price is None:
        return None

    price = float(price)
    prev_close = float(prev_close) if prev_close is not None else None
    change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else 0.0

    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "currency": "EUR",
    }


def supports_exchange(exchange: Exchange) -> bool:
    """True se l'exchange è gestito da Borsa Italiana."""
    return exchange in _EXCHANGE_TO_MIC
