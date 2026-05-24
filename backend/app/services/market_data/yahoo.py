"""
Prezzi da Yahoo Finance via yfinance.

Logica ticker italiani:
- Azioni Borsa Italiana: suffisso .MI  (es. ENI → ENI.MI)
- ETF su Borsa IT:       suffisso .MI  (es. VWCE → VWCE.MI)
- ETF su EuroTLX:        suffisso .MI  (stessa borsa Yahoo)
- Obbligazioni (MOT):    suffisso .MI
- Azioni NYSE/NASDAQ:    nessun suffisso
"""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

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


def _ticker(symbol: str, exchange: Exchange) -> str:
    suffix = _EXCHANGE_SUFFIX.get(exchange, "")
    if symbol.endswith(suffix):
        return symbol
    return f"{symbol}{suffix}"


def get_current_price(symbol: str, exchange: Exchange) -> dict | None:
    """Restituisce prezzo corrente, variazione % e volume."""
    t = yf.Ticker(_ticker(symbol, exchange))
    try:
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
) -> list[dict]:
    """
    Restituisce storico OHLCV.
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
    yf_period = period_map.get(period, "1y")
    t = yf.Ticker(_ticker(symbol, exchange))
    try:
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
                "close": round(float(row["Close"]), 6),
                "volume": float(row["Volume"]) if pd.notna(row["Volume"]) else None,
            })
        return records
    except Exception:
        return []


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
