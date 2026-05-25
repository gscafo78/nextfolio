import datetime

from pydantic import BaseModel, computed_field, field_validator

from app.models.transaction import TransactionType
from app.schemas.asset import AssetOut


class TransactionCreate(BaseModel):
    account_id: int
    asset_id: int
    type: TransactionType
    date: datetime.date
    quantity: float
    price: float
    price_currency: str = "EUR"
    exchange_rate: float = 1.0
    fee: float = 0.0
    fee_currency: str = "EUR"
    notes: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La quantità deve essere positiva")
        return v

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Il prezzo non può essere negativo")
        return v

    @field_validator("exchange_rate")
    @classmethod
    def rate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Il tasso di cambio deve essere > 0")
        return v

    @field_validator("fee")
    @classmethod
    def fee_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("La commissione non può essere negativa")
        return v

    @field_validator("price_currency", "fee_currency")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper()


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    type: TransactionType | None = None
    date: datetime.date | None = None
    quantity: float | None = None
    price: float | None = None
    price_currency: str | None = None
    exchange_rate: float | None = None
    fee: float | None = None
    fee_currency: str | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: int
    account_id: int
    asset_id: int
    type: TransactionType
    date: datetime.date
    quantity: float
    price: float
    price_currency: str
    exchange_rate: float
    fee: float
    fee_currency: str
    notes: str | None
    asset: AssetOut

    @computed_field
    @property
    def total_eur(self) -> float:
        """Controvalore in EUR, commissioni incluse."""
        return round(self.quantity * self.price * self.exchange_rate + self.fee, 6)

    model_config = {"from_attributes": True}
