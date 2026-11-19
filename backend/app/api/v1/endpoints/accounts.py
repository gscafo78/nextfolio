import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.account import AccountBalanceIn, AccountBalanceOut, AccountCreate, AccountOut, AccountUpdate
from app.services.account import (
    count_transactions,
    create_account,
    delete_account,
    get_account,
    get_accounts,
    update_account,
)
from app.services.audit import DELETE_ACCOUNT, log_action
from app.services.cash import balance_history, latest_balances, set_balance

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountOutWithStats(AccountOut):
    transaction_count: int
    cash_balance: float | None = None          # ultimo saldo, valuta del conto
    cash_balance_date: datetime.date | None = None
    cash_balance_eur: float | None = None


@router.get("", response_model=list[AccountOutWithStats])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = await get_accounts(db, current_user.id)
    cash = {b.account_id: b for b in await latest_balances(db, current_user.id)}
    result = []
    for acc in accounts:
        count = await count_transactions(db, acc.id)
        b = cash.get(acc.id)
        result.append(AccountOutWithStats(
            **AccountOut.model_validate(acc).model_dump(),
            transaction_count=count,
            cash_balance=b.balance if b else None,
            cash_balance_date=b.date if b else None,
            cash_balance_eur=round(b.value_eur, 2) if b else None,
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


# ── Saldo di cassa ───────────────────────────────────────────────────────────


@router.get("/{account_id}/balances", response_model=list[AccountBalanceOut])
async def list_balances(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Storico dei saldi di cassa del conto, il più recente per primo."""
    if not await get_account(db, account_id, current_user.id):
        raise HTTPException(404, "Conto non trovato")
    return await balance_history(db, account_id)


@router.post("/{account_id}/balances", response_model=AccountBalanceOut, status_code=201)
async def upsert_balance(
    account_id: int,
    body: AccountBalanceIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Imposta il saldo di cassa a una data (sostituisce quello della stessa data)."""
    account = await get_account(db, account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")
    try:
        return await set_balance(db, account, body.date or datetime.date.today(), body.balance)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{account_id}/balances/{balance_id}", status_code=204)
async def delete_balance(
    account_id: int,
    balance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.account_balance import AccountBalance

    if not await get_account(db, account_id, current_user.id):
        raise HTTPException(404, "Conto non trovato")
    row = await db.get(AccountBalance, balance_id)
    if not row or row.account_id != account_id:
        raise HTTPException(404, "Saldo non trovato")
    await db.delete(row)
    await db.commit()
