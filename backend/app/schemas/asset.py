from pydantic import BaseModel, field_validator

from app.models.asset import AssetType, Exchange


def validate_isin(isin: str) -> str:
    """Valida ISIN con checksum Luhn modificato (ISO 6166)."""
    isin = isin.strip().upper()
    if len(isin) != 12:
        raise ValueError("ISIN deve essere di 12 caratteri")
    if not isin[:2].isalpha():
        raise ValueError("ISIN deve iniziare con 2 lettere (codice paese)")
    if not isin[2:].isalnum():
        raise ValueError("ISIN: caratteri non validi")

    # Converti lettere in numeri (A=10, B=11, ...) e applica Luhn
    digits = ""
    for ch in isin:
        digits += str(ord(ch) - 55) if ch.isalpha() else ch

    total = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n

    if total % 10 != 0:
        raise ValueError("ISIN non valido (checksum errato)")
    return isin


class AssetCreate(BaseModel):
    isin: str | None = None
    symbol: str
    name: str
    type: AssetType
    exchange: Exchange = Exchange.OTHER
    currency: str = "EUR"
    sector: str | None = None

    @field_validator("isin")
    @classmethod
    def check_isin(cls, v: str | None) -> str | None:
        if v:
            return validate_isin(v)
        return v

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper()


class AssetOut(BaseModel):
    id: int
    isin: str | None
    symbol: str
    name: str
    type: AssetType
    exchange: Exchange
    currency: str
    sector: str | None

    model_config = {"from_attributes": True}


class AssetSearch(BaseModel):
    id: int
    isin: str | None
    symbol: str
    name: str
    type: AssetType
    exchange: Exchange
    currency: str

    model_config = {"from_attributes": True}
