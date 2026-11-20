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


class BatchError(ValueError):
    """Errori di validazione di un inserimento in blocco (nessuna riga scritta)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _same_tx(tx: Transaction, row: TransactionCreate) -> bool:
    kind = tx.type.value if hasattr(tx.type, "value") else str(tx.type)
    row_kind = row.type.value if hasattr(row.type, "value") else str(row.type)
    return (
        tx.account_id == row.account_id and tx.asset_id == row.asset_id and kind == row_kind
        and tx.date == row.date and abs(tx.quantity - row.quantity) < 1e-9 and abs(tx.price - row.price) < 1e-9
        and abs((tx.fee or 0) - (row.fee or 0)) < 1e-9
    )


async def create_transactions_batch(
    db: AsyncSession,
    user_id: int,
    rows: list[TransactionCreate],
) -> tuple[list[Transaction], list[int]]:
    """Inserisce più transazioni: tutto o niente, saltando i doppioni.

    Verifica che i conti siano dell'utente, che gli asset esistano e che le date
    non siano future; in caso di errori solleva ``BatchError`` senza scrivere
    nulla. Una riga identica a una transazione esistente (conto, asset, tipo,
    data, quantità, prezzo, commissione) viene saltata. Fa ``flush`` ma non
    ``commit``: il chiamante chiude la transazione (es. insieme all'audit).

    Restituisce (transazioni create, numeri di riga saltati, 1-based).
    """
    from datetime import date as _date

    from app.models.account import Account
    from app.models.asset import Asset

    errors: list[str] = []
    account_ids = {r.account_id for r in rows}
    asset_ids = {r.asset_id for r in rows}
    owned = set((await db.execute(
        select(Account.id).where(Account.id.in_(account_ids), Account.user_id == user_id)
    )).scalars())
    existing_assets = set((await db.execute(select(Asset.id).where(Asset.id.in_(asset_ids)))).scalars())
    for i, r in enumerate(rows, 1):
        if r.account_id not in owned:
            errors.append(f"riga {i}: conto {r.account_id} non trovato")
        if r.asset_id not in existing_assets:
            errors.append(f"riga {i}: asset {r.asset_id} non trovato")
        if r.date > _date.today():
            errors.append(f"riga {i}: data futura {r.date}")
    if errors:
        raise BatchError(errors)

    existing = list((await db.execute(select(Transaction).where(Transaction.account_id.in_(owned)))).scalars())
    created: list[Transaction] = []
    skipped: list[int] = []
    for i, r in enumerate(rows, 1):
        if any(_same_tx(t, r) for t in existing):
            skipped.append(i)
            continue
        tx = Transaction(**r.model_dump())
        db.add(tx)
        created.append(tx)
    await db.flush()
    return created, skipped
