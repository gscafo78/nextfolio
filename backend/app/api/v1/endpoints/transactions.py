from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.account import get_account
from app.services.asset import get_or_create_asset
from app.services.csv_import import BrokerFormat, parse_csv
from app.services.transaction import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transactions,
    update_transaction,
)
from app.schemas.asset import AssetCreate
from app.models.asset import AssetType, Exchange

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    account_id: int | None = Query(None),
    asset_id: int | None = Query(None),
    type: TransactionType | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_transactions(db, current_user.id, account_id, asset_id, type, date_from, date_to, limit, offset)


@router.post("", response_model=TransactionOut, status_code=201)
async def create(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await get_account(db, body.account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")
    return await create_transaction(db, body)


@router.put("/{tx_id}", response_model=TransactionOut)
async def update(
    tx_id: int,
    body: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = await get_transaction(db, tx_id, current_user.id)
    if not tx:
        raise HTTPException(404, "Transazione non trovata")
    return await update_transaction(db, tx, body)


@router.delete("/{tx_id}", status_code=204)
async def delete(
    tx_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = await get_transaction(db, tx_id, current_user.id)
    if not tx:
        raise HTTPException(404, "Transazione non trovata")
    await delete_transaction(db, tx)


@router.post("/import-csv", response_model=list[TransactionOut], status_code=201)
async def import_csv(
    account_id: int = Form(...),
    broker: BrokerFormat = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await get_account(db, account_id, current_user.id)
    if not account:
        raise HTTPException(404, "Conto non trovato")

    content = (await file.read()).decode("utf-8-sig")  # gestisce BOM di Excel
    try:
        rows = parse_csv(content, broker)
    except Exception as e:
        raise HTTPException(400, f"Errore parsing CSV: {e}")

    created = []
    for row in rows:
        asset_data = AssetCreate(
            isin=row.get("isin"),
            symbol=row.get("symbol") or row.get("isin") or "UNKNOWN",
            name=row.get("symbol") or row.get("isin") or "Sconosciuto",
            type=AssetType.STOCK,
            exchange=Exchange.OTHER,
            currency=row.get("currency", "EUR"),
        )
        asset = await get_or_create_asset(db, asset_data)

        tx_data = TransactionCreate(
            account_id=account_id,
            asset_id=asset.id,
            type=row["type"],
            date=row["date"],
            quantity=row["quantity"],
            price=row["price"],
            fee=row.get("fee", 0.0),
            currency=row.get("currency", "EUR"),
            notes=row.get("notes"),
        )
        tx = await create_transaction(db, tx_data)
        created.append(tx)

    return created
