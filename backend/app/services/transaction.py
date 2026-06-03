from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionUpdate


async def get_transactions(
    db: AsyncSession,
    user_id: int,
    account_id: int | None = None,
    asset_id: int | None = None,
    type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .join(Transaction.account)
        .where(Transaction.account.has(user_id=user_id))
        .options(selectinload(Transaction.asset), selectinload(Transaction.account))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if asset_id:
        stmt = stmt.where(Transaction.asset_id == asset_id)
    if type:
        stmt = stmt.where(Transaction.type == type)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)

    result = await db.execute(stmt)
    return list(result.scalars())


async def get_transaction(db: AsyncSession, tx_id: int, user_id: int) -> Transaction | None:
    result = await db.execute(
        select(Transaction)
        .join(Transaction.account)
        .where(Transaction.id == tx_id, Transaction.account.has(user_id=user_id))
        .options(selectinload(Transaction.asset))
    )
    return result.scalar_one_or_none()


async def create_transaction(db: AsyncSession, data: TransactionCreate) -> Transaction:
    tx = Transaction(**data.model_dump())
    db.add(tx)
    await db.commit()
    await db.refresh(tx, ["asset"])
    return tx


async def update_transaction(db: AsyncSession, tx: Transaction, data: TransactionUpdate) -> Transaction:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tx, field, value)
    await db.commit()
    await db.refresh(tx, ["asset"])
    return tx


async def delete_transaction(db: AsyncSession, tx: Transaction) -> None:
    await db.delete(tx)
    await db.commit()
