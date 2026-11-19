import datetime

from pydantic import BaseModel, Field

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    type: AccountType = AccountType.BROKERAGE
    broker: str | None = None
    url: str | None = None
    currency: str = "EUR"
    is_sostituto_imposta: bool = False
    is_foreign: bool = False
    coupon_auto_register: bool = False


class AccountUpdate(BaseModel):
    name: str | None = None
    type: AccountType | None = None
    broker: str | None = None
    url: str | None = None
    currency: str | None = None
    is_sostituto_imposta: bool | None = None
    is_foreign: bool | None = None
    coupon_auto_register: bool | None = None


class AccountOut(BaseModel):
    id: int
    name: str
    type: AccountType
    broker: str | None
    url: str | None
    currency: str
    is_sostituto_imposta: bool
    is_foreign: bool
    coupon_auto_register: bool

    model_config = {"from_attributes": True}


class AccountBalanceIn(BaseModel):
    balance: float = Field(description="Saldo di cassa nella valuta del conto")
    date: datetime.date | None = Field(None, description="Data del saldo (default: oggi)")


class AccountBalanceOut(BaseModel):
    id: int
    account_id: int
    date: datetime.date
    balance: float

    model_config = {"from_attributes": True}
