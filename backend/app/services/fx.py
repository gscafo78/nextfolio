"""
Tasso di cambio storico via Frankfurter API (https://www.frankfurter.app).
Dati ufficiali BCE, gratuiti, senza chiave API.

exchange_rate restituito = EUR per 1 unità di `from_currency`.
Esempio: from_currency=USD → 0.9259 significa "1 USD = 0.9259 EUR"
"""

from datetime import date, timedelta

import httpx

_BASE = "https://api.frankfurter.dev/v1"
_TIMEOUT = 5.0


async def get_exchange_rate(from_currency: str, to_currency: str = "EUR", on_date: date | None = None) -> float:
    """
    Restituisce il tasso `to_currency` per 1 `from_currency` alla data indicata.
    Se from_currency == to_currency ritorna 1.0 senza chiamate HTTP.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return 1.0

    # Frankfurter non ha dati nei weekend → usa il venerdì precedente
    target = on_date or date.today()
    if target.weekday() == 5:  # sabato
        target -= timedelta(days=1)
    elif target.weekday() == 6:  # domenica
        target -= timedelta(days=2)

    url = f"{_BASE}/{target.isoformat()}"
    params = {"from": from_currency, "to": to_currency}

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rate = data["rates"].get(to_currency)
    if rate is None:
        raise ValueError(f"Tasso {from_currency}/{to_currency} non disponibile per {target}")
    return float(rate)


async def get_exchange_rate_series(
    from_currency: str, to_currency: str, start_date: date, end_date: date
) -> dict[date, float]:
    """
    Serie storica di tassi di cambio tra start_date e end_date (un'unica chiamata,
    invece di una richiesta per ogni giorno). Le date senza quotazione BCE
    (weekend/festivi) non compaiono nel risultato.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return {}

    url = f"{_BASE}/{start_date.isoformat()}..{end_date.isoformat()}"
    params = {"from": from_currency, "to": to_currency}

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    return {
        date.fromisoformat(d): float(rates[to_currency])
        for d, rates in data.get("rates", {}).items()
        if to_currency in rates
    }


async def get_supported_currencies() -> list[str]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(f"{_BASE}/currencies")
        resp.raise_for_status()
        currencies = list(resp.json().keys())
    currencies.append("EUR")
    return sorted(currencies)
