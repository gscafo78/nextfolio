from pydantic import BaseModel

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
