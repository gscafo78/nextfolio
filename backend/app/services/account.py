from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.account import AccountCreate


async def get_accounts(db: AsyncSession, user_id: int) -> list[Account]:
    result = await db.execute(select(Account).where(Account.user_id == user_id).order_by(Account.id))
    return list(result.scalars())


async def get_account(db: AsyncSession, account_id: int, user_id: int) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_account(db: AsyncSession, user_id: int, data: AccountCreate) -> Account:
    account = Account(user_id=user_id, **data.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    await db.delete(account)
    await db.commit()
