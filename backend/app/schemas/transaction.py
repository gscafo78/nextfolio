from datetime import date

from pydantic import BaseModel, field_validator

from app.models.transaction import TransactionType
from app.schemas.asset import AssetOut


class TransactionCreate(BaseModel):
    account_id: int
    asset_id: int
    type: TransactionType
    date: date
    quantity: float
    price: float
    fee: float = 0.0
    currency: str = "EUR"
    notes: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La quantità deve essere positiva")
        return v

    @field_validator("price")
    @classmethod
    def price_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Il prezzo non può essere negativo")
        return v

    @field_validator("fee")
    @classmethod
    def fee_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("La commissione non può essere negativa")
        return v


class TransactionUpdate(BaseModel):
    type: TransactionType | None = None
    date: date | None = None
    quantity: float | None = None
    price: float | None = None
    fee: float | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: int
    account_id: int
    asset_id: int
    type: TransactionType
    date: date
    quantity: float
    price: float
    fee: float
    currency: str
    notes: str | None
    asset: AssetOut

    model_config = {"from_attributes": True}
