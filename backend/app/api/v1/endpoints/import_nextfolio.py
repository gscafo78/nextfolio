from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.account import Account
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/import/nextfolio", tags=["import"])


class NextfolioImportRequest(BaseModel):
    raw: dict


@router.post("")
async def import_nextfolio(
    body: NextfolioImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Importa un backup Nextfolio JSON.
    - Account: ricercato per nome, creato se non esiste.
    - Asset: ricercato per ISIN (poi per simbolo), creato se non esiste.
    - Transazione: skippata se già presente (stessa data/conto/asset/tipo/qtà/prezzo).
    Restituisce il conteggio degli elementi creati.
    """
    data = body.raw

    if data.get("meta", {}).get("app") != "nextfolio":
        raise HTTPException(400, "File non valido: non è un backup Nextfolio")

    version = data.get("meta", {}).get("version", "1")
    if version != "1":
        raise HTTPException(400, f"Versione formato non supportata: {version}")

    accounts_data: list[dict] = data.get("accounts", [])
    assets_data: list[dict] = data.get("assets", [])
    transactions_data: list[dict] = data.get("transactions", [])

    # Mappa id-file → id-DB
    account_id_map: dict[int, int] = {}
    asset_id_map: dict[int, int] = {}
    accounts_created = 0
    assets_created = 0
    tx_created = 0
    tx_skipped = 0

    # ── Account ───────────────────────────────────────────────────────────────
    for acc in accounts_data:
        res = await db.execute(
            select(Account).where(
                Account.user_id == current_user.id,
                Account.name == acc["name"],
            )
        )
        existing = res.scalar_one_or_none()

        if existing:
            account_id_map[acc["id"]] = existing.id
        else:
            new_acc = Account(
                user_id=current_user.id,
                name=acc["name"],
                type=acc.get("type") or "BROKERAGE",
                broker=acc.get("broker") or None,
                currency=acc.get("currency") or "EUR",
                url=acc.get("url") or None,
            )
            db.add(new_acc)
            await db.flush()
            account_id_map[acc["id"]] = new_acc.id
            accounts_created += 1

    # ── Asset ─────────────────────────────────────────────────────────────────
    for ast in assets_data:
        existing = None

        # Preferenza: ISIN (univoco a livello globale)
        if ast.get("isin"):
            res = await db.execute(select(Asset).where(Asset.isin == ast["isin"]))
            existing = res.scalar_one_or_none()

        # Fallback: simbolo
        if not existing and ast.get("symbol"):
            res = await db.execute(select(Asset).where(Asset.symbol == ast["symbol"]))
            existing = res.scalar_one_or_none()

        if existing:
            asset_id_map[ast["id"]] = existing.id
        else:
            new_asset = Asset(
                symbol=ast["symbol"],
                name=ast["name"],
                isin=ast.get("isin") or None,
                type=ast.get("type") or "STOCK",
                exchange=ast.get("exchange") or "OTHER",
                currency=ast.get("currency") or "EUR",
                sector=ast.get("sector") or None,
            )
            db.add(new_asset)
            await db.flush()
            asset_id_map[ast["id"]] = new_asset.id
            assets_created += 1

    # ── Transazioni ───────────────────────────────────────────────────────────
    for tx in transactions_data:
        acc_db_id = account_id_map.get(tx["account_id"])
        asset_db_id = asset_id_map.get(tx["asset_id"])

        if not acc_db_id or not asset_db_id:
            tx_skipped += 1
            continue

        tx_date = date.fromisoformat(tx["date"])

        # Deduplication: stessa data/conto/asset/tipo/qtà/prezzo
        dup = await db.execute(
            select(Transaction).where(
                Transaction.account_id == acc_db_id,
                Transaction.asset_id == asset_db_id,
                Transaction.type == tx["type"],
                Transaction.date == tx_date,
                Transaction.quantity == float(tx["quantity"]),
                Transaction.price == float(tx["price"]),
            )
        )
        if dup.scalar_one_or_none():
            tx_skipped += 1
            continue

        db.add(Transaction(
            account_id=acc_db_id,
            asset_id=asset_db_id,
            type=tx["type"],
            date=tx_date,
            quantity=float(tx["quantity"]),
            price=float(tx["price"]),
            fee=float(tx.get("fee", 0.0)),
            price_currency=tx.get("price_currency") or "EUR",
            exchange_rate=float(tx.get("exchange_rate", 1.0)),
            fee_currency=tx.get("fee_currency") or "EUR",
            notes=tx.get("notes") or None,
        ))
        tx_created += 1

    await db.commit()

    return {
        "accounts_created": accounts_created,
        "assets_created": assets_created,
        "transactions_imported": tx_created,
        "transactions_skipped": tx_skipped,
    }
