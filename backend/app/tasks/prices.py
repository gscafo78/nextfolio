"""
Task Celery per l'aggiornamento prezzi.
Usano una sessione DB sincrona (Celery è sincrono per default).
"""

import asyncio
from datetime import date, timedelta

from celery.utils.log import get_task_logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import celery_db_session
from app.models.account import Account
from app.models.asset import Asset, AssetType, PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.services.market_data.enricher import enrich_asset
from app.services.market_data.updater import (
    fetch_asset_history,
    invalidate_perf_cache,
    refresh_all_crypto_prices,
    refresh_all_stock_prices,
    upsert_price_history,
)
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """
    Esegue una coroutine nel contesto sincrono di Celery (pool=solo, no fork).
    Loop persistente per processo: asyncpg può riutilizzare connessioni in modo
    stabile senza 'Future attached to a different loop'.
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.prices.update_stock_prices", bind=True, max_retries=3)
def update_stock_prices(self):
    """Aggiorna i prezzi correnti di azioni/ETF (Yahoo Finance)."""
    async def _inner():
        async with celery_db_session() as db:
            count = await refresh_all_stock_prices(db)
            logger.info(f"update_stock_prices: aggiornati {count} asset")
            return count
    try:
        return _run(_inner())
    except Exception as exc:
        logger.error(f"update_stock_prices fallito: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.tasks.prices.update_crypto_prices", bind=True, max_retries=3)
def update_crypto_prices(self):
    """Aggiorna i prezzi crypto (CoinGecko)."""
    async def _inner():
        async with celery_db_session() as db:
            count = await refresh_all_crypto_prices(db)
            logger.info(f"update_crypto_prices: aggiornati {count} crypto")
            return count
    try:
        return _run(_inner())
    except Exception as exc:
        logger.error(f"update_crypto_prices fallito: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.prices.update_prices_eod", bind=True, max_retries=2)
def update_prices_eod(self):
    """
    Scarica e salva i prezzi di chiusura giornalieri nel price_history.
    Recupera gli ultimi 5 giorni per coprire eventuali gap.
    """
    async def _inner():
        async with celery_db_session() as db:
            result = await db.execute(
                select(Asset).where(
                    Asset.type.in_([AssetType.STOCK, AssetType.ETF, AssetType.BOND, AssetType.REIT])
                )
            )
            assets = list(result.scalars())
            total = 0
            for asset in assets:
                # fetch_asset_history sceglie Borsa Italiana per asset italiani con ISIN,
                # Yahoo Finance come fallback per tutti gli altri
                records = await fetch_asset_history(asset, period="1mo")
                written = await upsert_price_history(db, asset.id, records)
                total += written
                src = "BI" if asset.isin else "YF"
                logger.info(f"EOD [{src}] {asset.symbol}: {written} righe scritte")

            # Invalida cache performance per tutti gli utenti con transazioni
            user_rows = await db.execute(select(Account.user_id).distinct())
            user_ids = [r for (r,) in user_rows.all()]
            for uid in user_ids:
                await invalidate_perf_cache(uid)
            logger.info(f"Invalidata cache perf per {len(user_ids)} utenti")
            return total
    try:
        return _run(_inner())
    except Exception as exc:
        logger.error(f"update_prices_eod fallito: {exc}")
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.tasks.prices.cleanup_old_prices")
def cleanup_old_prices():
    """Elimina i dati price_history più vecchi di 5 anni."""
    async def _inner():
        cutoff = date.today() - timedelta(days=5 * 365)
        async with celery_db_session() as db:
            result = await db.execute(
                delete(PriceHistory).where(PriceHistory.date < cutoff)
            )
            await db.commit()
            deleted = result.rowcount
            logger.info(f"cleanup_old_prices: eliminate {deleted} righe prima di {cutoff}")
            return deleted
    return _run(_inner())


@celery_app.task(name="app.tasks.prices.backfill_portfolio_history", bind=True, max_retries=1)
def backfill_portfolio_history(self, user_id: int):
    """
    Per ogni asset detenuto (quantità netta > 0) dall'utente:
    scarica i prezzi di chiusura giornalieri dalla data del primo acquisto a oggi
    e li salva in price_history.
    """
    async def _inner():
        async with celery_db_session() as db:
            # Prendi tutte le transazioni dell'utente
            res = await db.execute(
                select(Transaction)
                .join(Transaction.account)
                .where(Transaction.account.has(user_id=user_id))
            )
            txs = list(res.scalars())

            # Calcola quantità netta e prima data acquisto per asset
            net_qty: dict[int, float] = {}
            first_buy: dict[int, date] = {}
            for tx in txs:
                if tx.type == TransactionType.BUY:
                    net_qty[tx.asset_id] = net_qty.get(tx.asset_id, 0) + tx.quantity
                    if tx.asset_id not in first_buy or tx.date < first_buy[tx.asset_id]:
                        first_buy[tx.asset_id] = tx.date
                elif tx.type == TransactionType.SELL:
                    net_qty[tx.asset_id] = net_qty.get(tx.asset_id, 0) - tx.quantity

            held_ids = [aid for aid, qty in net_qty.items() if qty > 0.000001]
            if not held_ids:
                return 0

            total = 0
            today = date.today()
            for asset_id in held_ids:
                res2 = await db.execute(select(Asset).where(Asset.id == asset_id))
                asset = res2.scalar_one_or_none()
                if not asset:
                    continue
                start = first_buy.get(asset_id, today)
                records = await fetch_asset_history(asset, start_date=start, end_date=today)
                written = await upsert_price_history(db, asset.id, records)
                total += written
                logger.info(f"backfill_portfolio [{asset.symbol}] from {start}: {written} righe")
            return total

    try:
        return _run(_inner())
    except Exception as exc:
        logger.error(f"backfill_portfolio_history fallito: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.tasks.prices.backfill_asset_history")
def backfill_asset_history(asset_id: int, period: str = "5y"):
    """Backfill manuale dello storico di un singolo asset (on-demand)."""
    async def _inner():
        async with celery_db_session() as db:
            result = await db.execute(select(Asset).where(Asset.id == asset_id))
            asset = result.scalar_one_or_none()
            if not asset:
                logger.warning(f"backfill: asset {asset_id} non trovato")
                return 0
            records = await fetch_asset_history(asset, period=period)
            written = await upsert_price_history(db, asset.id, records)
            logger.info(f"backfill {asset.symbol} ({period}): {written} righe")
            return written
    return _run(_inner())


@celery_app.task(name="app.tasks.prices.enrich_all_assets", bind=True, max_retries=1)
def enrich_all_assets(self):
    """Enrichment bulk di tutti gli asset con dati settoriali/geografici/holdings."""
    async def _inner():
        async with celery_db_session() as db:
            result = await db.execute(
                select(Asset).where(
                    Asset.type.in_([
                        AssetType.STOCK, AssetType.ETF, AssetType.BOND, AssetType.REIT
                    ])
                )
            )
            assets = list(result.scalars())
            enriched = 0
            for asset in assets:
                try:
                    ok = await enrich_asset(db, asset)
                    if ok:
                        enriched += 1
                except Exception as e:
                    logger.warning(f"enrich_all: {asset.symbol} fallito: {e}")
            logger.info(f"enrich_all_assets: {enriched}/{len(assets)} asset arricchiti")
            return enriched
    try:
        return _run(_inner())
    except Exception as exc:
        logger.error(f"enrich_all_assets fallito: {exc}")
        raise self.retry(exc=exc, countdown=120)
