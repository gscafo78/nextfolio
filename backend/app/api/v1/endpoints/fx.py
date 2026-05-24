from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.services.fx import get_exchange_rate, get_supported_currencies

router = APIRouter(prefix="/fx", tags=["forex"])


class ExchangeRateOut(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    date: date


@router.get("/rate", response_model=ExchangeRateOut)
async def exchange_rate(
    from_currency: str = Query(..., min_length=3, max_length=3),
    to_currency: str = Query("EUR", min_length=3, max_length=3),
    on_date: date | None = Query(None),
    _: User = Depends(get_current_user),
):
    """
    Restituisce il tasso storico (dati BCE via Frankfurter).
    `rate` = unità di `to_currency` per 1 `from_currency`.
    """
    try:
        rate = await get_exchange_rate(from_currency, to_currency, on_date)
    except Exception as e:
        raise HTTPException(502, f"Impossibile recuperare il tasso: {e}")

    return ExchangeRateOut(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        rate=rate,
        date=on_date or __import__("datetime").date.today(),
    )


@router.get("/currencies", response_model=list[str])
async def currencies(_: User = Depends(get_current_user)):
    """Lista valute supportate."""
    try:
        return await get_supported_currencies()
    except Exception:
        # Fallback con le valute più comuni se l'API non risponde
        return ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK"]
