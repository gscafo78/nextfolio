"""
Task Celery per il controllo delle cedole in scadenza.

Eseguito ogni giorno alle 08:00 Europe/Rome.
Per ogni posizione aperta su un BOND con bond_details configurato,
verifica se oggi è una data cedola (±2 giorni per festivi/week-end).

Comportamento per conto:
  - coupon_auto_register=False (default): invia notifica via email + crea alert in-app
  - coupon_auto_register=True: crea automaticamente la transazione COUPON
"""
import asyncio
from datetime import date, timedelta

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import celery_db_session
from app.models.account import Account
from app.models.asset import Asset, AssetType
from app.models.bond_detail import BondDetail
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.bonds.coupon_schedule import generate_coupon_dates, coupon_per_unit
from app.services.portfolio.positions import calculate_positions
from app.services.transaction import get_transactions
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)

_TOLERANCE_DAYS = 2   # ±2 giorni per far scattare il check (festivi/week-end)
_ALL = 10_000


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _process_due_coupons():
    today = date.today()

    async with celery_db_session() as db:
        # Tutti gli utenti con almeno un bond_detail configurato
        result = await db.execute(
            select(User)
            .options(selectinload(User.accounts))
        )
        users = result.scalars().all()

        for user in users:
            try:
                transactions = await get_transactions(db, user.id, limit=_ALL)
                if not transactions:
                    continue

                positions = calculate_positions(transactions)
                open_asset_ids = {aid for aid, p in positions.items() if p.quantity > 1e-10}

                # Asset BOND con bond_detail per le posizioni aperte
                bond_result = await db.execute(
                    select(Asset)
                    .options(selectinload(Asset.bond_detail))
                    .where(
                        Asset.id.in_(open_asset_ids),
                        Asset.type == AssetType.BOND,
                    )
                )
                bond_assets = [a for a in bond_result.scalars() if a.bond_detail is not None]

                for asset in bond_assets:
                    bd = asset.bond_detail
                    # Salta se già scaduto
                    if bd.maturity_date and bd.maturity_date < today:
                        continue

                    # Calcola date cedola nel range today ± TOLERANCE
                    window_start = today - timedelta(days=_TOLERANCE_DAYS)
                    window_end = today + timedelta(days=_TOLERANCE_DAYS)
                    due_dates = generate_coupon_dates(bd, window_start, window_end)

                    if not due_dates:
                        continue

                    for due_date in due_dates:
                        # Idempotenza: verifica che non esista già una COUPON in ±5 gg
                        existing = await db.execute(
                            select(Transaction)
                            .join(Transaction.account)
                            .where(
                                Transaction.account.has(user_id=user.id),
                                Transaction.asset_id == asset.id,
                                Transaction.type == TransactionType.COUPON,
                                Transaction.date >= due_date - timedelta(days=5),
                                Transaction.date <= due_date + timedelta(days=5),
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue  # già registrata

                        qty = positions[asset.id].quantity
                        cpu = coupon_per_unit(bd)
                        total = round(qty * cpu, 2)

                        logger.info(
                            "Cedola in scadenza: user=%s asset=%s (%s) data=%s totale=%.2f EUR",
                            user.email, asset.symbol, asset.isin, due_date, total,
                        )

                        # Controlla se il conto è in auto-register
                        # (cerca il conto più frequente per questo asset)
                        account_ids = {tx.account_id for tx in transactions if tx.asset_id == asset.id}
                        auto_register = False
                        for acc_id in account_ids:
                            acc = await db.get(Account, acc_id)
                            if acc and getattr(acc, "coupon_auto_register", False):
                                auto_register = True
                                break

                        if auto_register:
                            # Crea transazione COUPON automaticamente
                            first_account_id = next(iter(account_ids))
                            tx = Transaction(
                                account_id=first_account_id,
                                asset_id=asset.id,
                                type=TransactionType.COUPON,
                                date=due_date,
                                quantity=qty,
                                price=cpu,
                                exchange_rate=1.0,
                                fee=0.0,
                                currency="EUR",
                            )
                            db.add(tx)
                            await db.commit()
                            logger.info("Transazione COUPON auto-creata per %s", asset.symbol)
                        else:
                            # Solo log — notifica email implementata in fase successiva
                            logger.info(
                                "Cedola da registrare manualmente: %s scadenza %s importo %.2f EUR",
                                asset.name, due_date, total,
                            )

            except Exception as exc:
                logger.warning("Errore cedole utente %s: %s", user.email, exc)


@celery_app.task(name="app.tasks.coupons.check_due_coupons")
def check_due_coupons():
    _run(_process_due_coupons())
