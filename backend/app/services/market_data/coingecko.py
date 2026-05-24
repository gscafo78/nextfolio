"""
Prezzi crypto da CoinGecko (free tier, no API key richiesta per uso base).
Rate limit free tier: ~30 req/min.
"""

import httpx

_BASE = "https://api.coingecko.com/api/v3"
_TIMEOUT = 10.0

# Mappa symbol → CoinGecko ID (i più comuni)
SYMBOL_TO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "USDC": "usd-coin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "ATOM": "cosmos",
}


def _resolve_id(symbol: str) -> str:
    """Converte ticker symbol in CoinGecko ID."""
    return SYMBOL_TO_ID.get(symbol.upper(), symbol.lower())


async def get_crypto_price(symbol: str, vs_currency: str = "eur") -> dict | None:
    coin_id = _resolve_id(symbol)
    url = f"{_BASE}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if coin_id not in data:
                return None
            d = data[coin_id]
            price = d.get(vs_currency)
            change = d.get(f"{vs_currency}_24h_change")
            return {
                "price": float(price) if price is not None else None,
                "change_pct": round(float(change), 4) if change is not None else 0.0,
                "currency": vs_currency.upper(),
            }
        except Exception:
            return None


async def get_bulk_crypto_prices(symbols: list[str], vs_currency: str = "eur") -> dict[str, dict | None]:
    ids = [_resolve_id(s) for s in symbols]
    url = f"{_BASE}/simple/price"
    params = {
        "ids": ",".join(ids),
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return {s: None for s in symbols}

    result: dict[str, dict | None] = {}
    for symbol, coin_id in zip(symbols, ids):
        d = data.get(coin_id)
        if d:
            result[symbol] = {
                "price": float(d.get(vs_currency, 0)),
                "change_pct": round(float(d.get(f"{vs_currency}_24h_change", 0)), 4),
                "currency": vs_currency.upper(),
            }
        else:
            result[symbol] = None
    return result


async def get_crypto_history(symbol: str, days: int = 365, vs_currency: str = "eur") -> list[dict]:
    coin_id = _resolve_id(symbol)
    url = f"{_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days, "interval": "daily"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            prices = data.get("prices", [])
            return [
                {"date": __import__("datetime").date.fromtimestamp(ts / 1000).isoformat(), "close": round(p, 8)}
                for ts, p in prices
            ]
        except Exception:
            return []
