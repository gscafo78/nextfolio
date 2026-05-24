"""
Task Celery per l'aggiornamento prezzi.
Usano una sessione DB sincrona (Celery è sincrono per default).
"""

import asyncio
from datetime import date, timedelta

from celery.utils.log import get_task_logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.asset import Asset, AssetType, PriceHistory
from app.services.market_data.updater import (
    fetch_asset_history,
    refresh_all_crypto_prices,
    refresh_all_stock_prices,
    upsert_price_history,
)
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


def _run(coro):
    """Esegue una coroutine dal contesto sincrono di Celery."""
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.tasks.prices.update_stock_prices", bind=True, max_retries=3)
def update_stock_prices(self):
    """Aggiorna i prezzi correnti di azioni/ETF (Yahoo Finance)."""
    async def _inner():
        async with AsyncSessionLocal() as db:
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
        async with AsyncSessionLocal() as db:
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
        async with AsyncSessionLocal() as db:
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
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(PriceHistory).where(PriceHistory.date < cutoff)
            )
            await db.commit()
            deleted = result.rowcount
            logger.info(f"cleanup_old_prices: eliminate {deleted} righe prima di {cutoff}")
            return deleted
    return _run(_inner())


@celery_app.task(name="app.tasks.prices.backfill_asset_history")
def backfill_asset_history(asset_id: int, period: str = "5y"):
    """Backfill manuale dello storico di un singolo asset (on-demand)."""
    async def _inner():
        async with AsyncSessionLocal() as db:
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
