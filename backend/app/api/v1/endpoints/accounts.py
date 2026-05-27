from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.account import (
    count_transactions,
    create_account,
    delete_account,
    get_account,
    get_accounts,
    update_account,
)
from app.services.audit import DELETE_ACCOUNT, log_action

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountOutWithStats(AccountOut):
    transaction_count: int


@router.get("", response_model=list[AccountOutWithStats])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = await get_accounts(db, current_user.id)
    result = []
    for acc in accounts:
        count = await count_transactions(db, acc.id)
        result.append(AccountOutWithStats(
            **AccountOut.model_validate(acc).model_dump(),
            transaction_count=count,
        ))
    return result


@router.post("", response_model=AccountOut, status_code=201)
async def create(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_account(db, current_user.id, body)


@router.patch("/{account_id}", response_model=AccountOut)
async def update(
    account_id: int,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await get_account(db, account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")
    return await update_account(db, account, body)


@router.delete("/{account_id}", status_code=204)
async def delete(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await get_account(db, account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")
    tx_count = await count_transactions(db, account_id)
    if tx_count > 0:
        raise HTTPException(
            409,
            f"Il conto ha {tx_count} transazioni. Elimina prima le transazioni o spostale."
        )
    await log_action(
        db,
        user_id=current_user.id,
        action=DELETE_ACCOUNT,
        entity_type="account",
        entity_id=account_id,
        detail={"name": account.name, "broker": account.broker},
    )
    await delete_account(db, account)
