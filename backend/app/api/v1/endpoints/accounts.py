from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut
from app.services.account import create_account, delete_account, get_account, get_accounts

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_accounts(db, current_user.id)


@router.post("", response_model=AccountOut, status_code=201)
async def create(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_account(db, current_user.id, body)


@router.delete("/{account_id}", status_code=204)
async def delete(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await get_account(db, account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")
    await delete_account(db, account)
