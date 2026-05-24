from pydantic import BaseModel

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    type: AccountType = AccountType.BROKERAGE
    broker: str | None = None
    currency: str = "EUR"


class AccountOut(BaseModel):
    id: int
    name: str
    type: AccountType
    broker: str | None
    currency: str

    model_config = {"from_attributes": True}
