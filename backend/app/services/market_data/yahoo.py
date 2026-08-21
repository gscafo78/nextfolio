"""
Prezzi da Yahoo Finance via yfinance.

Logica ticker italiani:
- Azioni Borsa Italiana: suffisso .MI  (es. ENI → ENI.MI)
- ETF su Borsa IT:       suffisso .MI  (es. VWCE → VWCE.MI)
- ETF su EuroTLX:        suffisso .MI  (stessa borsa Yahoo)
- Obbligazioni (MOT):    suffisso .MI
- Azioni NYSE/NASDAQ:    nessun suffisso
"""

import asyncio
import logging
import re
from contextlib import contextmanager
from datetime import date, timedelta

import httpx
import pandas as pd
import yfinance as yf

_yf_logger = logging.getLogger("yfinance")


@contextmanager
def _suppress_yf_warnings():
    """Silenzia temporaneamente i log yfinance fino a CRITICAL (yfinance usa ERROR)."""
    prev = _yf_logger.level
    _yf_logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        _yf_logger.setLevel(prev)


@contextmanager
def _noop():
    yield


def _maybe_suppress(symbol: str):
    """Sopprime i warning yfinance solo se il ticker sembra ISIN-format."""
    return _suppress_yf_warnings() if _is_isin_like(symbol) else _noop()

from app.models.asset import Exchange

_EXCHANGE_SUFFIX: dict[Exchange, str] = {
    Exchange.MIL: ".MI",
    Exchange.EUROTLX: ".MI",
    Exchange.MOT: ".MI",
    Exchange.XETRA: ".DE",
    Exchange.NYSE: "",
    Exchange.NASDAQ: "",
    Exchange.CRYPTO: "-USD",  # fallback, usare CoinGecko per crypto
    Exchange.OTHER: "",
}

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
# ISIN con eventuale suffisso exchange — questi ticker NON funzionano con yfinance
_ISIN_LIKE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}(\.[A-Z]{1,4})?$")

# Cache in-memory: ISIN → ticker Yahoo trovato via search
_isin_ticker_cache: dict[str, str | None] = {}


def _is_isin(s: str) -> bool:
    return bool(_ISIN_RE.match(s))


def _is_isin_like(s: str) -> bool:
    """True per simboli tipo ISIN o ISIN.DE — non validi come ticker yfinance."""
    return bool(_ISIN_LIKE_RE.match(s))


async def resolve_ticker_by_isin(isin: str) -> str | None:
    """
    Cerca il ticker Yahoo Finance per un ISIN tramite l'API di ricerca.
    Preferisce ticker brevi (non ISIN-format) perché yfinance non supporta
    simboli tipo IE00BTJRMP35.DE anche se restituiti dalla search API.
    Risultati memorizzati in cache per la durata del processo.
    """
    if isin in _isin_ticker_cache:
        return _isin_ticker_cache[isin]

    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": isin, "quotesCount": 10, "newsCount": 0, "listsCount": 0}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            quotes = resp.json().get("quotes", [])
    except Exception:
        _isin_ticker_cache[isin] = None
        return None

    preferred_types = {"EQUITY", "ETF", "MUTUALFUND", "BOND"}
    ticker = None

    # 1° passata: ticker breve (non ISIN-format) di tipo preferito
    for q in quotes:
        qt = (q.get("quoteType") or "").upper()
        sym = q.get("symbol", "")
        if qt in preferred_types and sym and not _is_isin_like(sym):
            ticker = sym
            break

    # 2° passata: qualsiasi tipo preferito, anche ISIN-format (ultimo tentativo)
    if not ticker:
        for q in quotes:
            qt = (q.get("quoteType") or "").upper()
            sym = q.get("symbol", "")
            if qt in preferred_types and sym:
                ticker = sym
                break

    # Fallback assoluto al primo risultato
    if not ticker and quotes:
        ticker = quotes[0].get("symbol")

    _isin_ticker_cache[isin] = ticker
    return ticker


def _ticker(symbol: str, exchange: Exchange) -> str:
    suffix = _EXCHANGE_SUFFIX.get(exchange, "")
    if symbol.endswith(suffix):
        return symbol
    return f"{symbol}{suffix}"


def get_current_price(symbol: str, exchange: Exchange) -> dict | None:
    """Restituisce prezzo corrente, variazione % e volume."""
    full_sym = _ticker(symbol, exchange)
    t = yf.Ticker(full_sym)
    try:
        with _maybe_suppress(full_sym):
            info = t.fast_info
            price = info.last_price
            prev_close = info.previous_close
        if price is None:
            return None
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        return {
            "price": float(price),
            "prev_close": float(prev_close) if prev_close else None,
            "change_pct": round(float(change_pct), 4),
            "currency": info.currency or "EUR",
        }
    except Exception:
        return None


def get_price_history(
    symbol: str,
    exchange: Exchange,
    period: str = "1y",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """
    Restituisce storico OHLCV.
    Se start_date è fornito usa range di date, altrimenti usa period.
    period: '1w' '1mo' '3mo' '6mo' '1y' '3y' '5y' 'max'
    """
    period_map = {
        "1w": "5d",
        "1mo": "1mo",
        "3mo": "3mo",
        "6mo": "6mo",
        "1y": "1y",
        "3y": "3y",
        "5y": "5y",
        "max": "max",
    }
    full_sym = _ticker(symbol, exchange)
    t = yf.Ticker(full_sym)
    try:
        with _maybe_suppress(full_sym):
            if start_date:
                today = date.today()
                df: pd.DataFrame = t.history(
                    start=start_date.isoformat(),
                    end=(end_date or today).isoformat(),
                    auto_adjust=True,
                )
            else:
                yf_period = period_map.get(period, "1y")
                df: pd.DataFrame = t.history(period=yf_period, auto_adjust=True)
        if df.empty:
            return []
        df.index = pd.to_datetime(df.index)
        records = []
        for dt, row in df.iterrows():
            records.append({
                "date": dt.date().isoformat(),
                "open": round(float(row["Open"]), 6) if pd.notna(row["Open"]) else None,
                "high": round(float(row["High"]), 6) if pd.notna(row["High"]) else None,
                "low": round(float(row["Low"]), 6) if pd.notna(row["Low"]) else None,
                "close": round(float(row["Close"]), 6) if pd.notna(row["Close"]) else None,
                "volume": float(row["Volume"]) if pd.notna(row["Volume"]) else None,
            })
        return records
    except Exception:
        return []


async def get_current_price_async(symbol: str, exchange: Exchange) -> dict | None:
    """Async wrapper: runs blocking yfinance call in thread pool."""
    return await asyncio.get_running_loop().run_in_executor(None, get_current_price, symbol, exchange)


async def get_price_history_async(
    symbol: str,
    exchange: Exchange,
    period: str = "1y",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Async wrapper: runs blocking yfinance call in thread pool."""
    return await asyncio.get_running_loop().run_in_executor(
        None, get_price_history, symbol, exchange, period, start_date, end_date
    )


def get_bulk_prices(symbols_exchanges: list[tuple[str, Exchange]]) -> dict[str, dict | None]:
    """Scarica prezzi di più ticker in una sola chiamata (più efficiente)."""
    tickers = [_ticker(sym, ex) for sym, ex in symbols_exchanges]
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period="2d", auto_adjust=True, progress=False)
        result: dict[str, dict | None] = {}
        close = data["Close"] if "Close" in data.columns else data
        for i, (sym, ex) in enumerate(symbols_exchanges):
            ticker = tickers[i]
            try:
                series = close[ticker].dropna()
                if len(series) >= 1:
                    price = float(series.iloc[-1])
                    prev = float(series.iloc[-2]) if len(series) >= 2 else price
                    result[sym] = {
                        "price": price,
                        "prev_close": prev,
                        "change_pct": round((price - prev) / prev * 100, 4) if prev else 0.0,
                    }
                else:
                    result[sym] = None
            except Exception:
                result[sym] = None
        return result
    except Exception:
        return {sym: None for sym, _ in symbols_exchanges}
