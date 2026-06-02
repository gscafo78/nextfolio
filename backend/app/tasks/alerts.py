"""
Task Celery per il controllo degli alert di prezzo.

Ogni 5 minuti legge tutti gli alert attivi, confronta il prezzo corrente
(da cache Redis) con la soglia e segna quelli scattati.
Cooldown di 4 ore per non riattivare lo stesso alert ripetutamente.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import celery_db_session
from app.models.alert import AlertType, PriceAlert
from app.models.user import User
from app.services.market_data.updater import get_cached_price
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)

_COOLDOWN_HOURS = 4  # non riattiva lo stesso alert entro N ore


_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


def _is_triggered(alert_type: AlertType, threshold: float, price: float, change_pct: float) -> bool:
    if alert_type == AlertType.PRICE_ABOVE:
        return price > threshold
    if alert_type == AlertType.PRICE_BELOW:
        return price < threshold
    if alert_type == AlertType.CHANGE_PCT_UP:
        return change_pct > threshold
    if alert_type == AlertType.CHANGE_PCT_DOWN:
        return change_pct < -threshold
    return False


@celery_app.task(name="app.tasks.alerts.check_price_alerts", bind=True, max_retries=2)
def check_price_alerts(self):
    """Controlla tutti gli alert attivi e marca quelli scattati."""
    async def _inner():
        triggered = 0
        async with celery_db_session() as db:
            result = await db.execute(
                select(PriceAlert)
                .where(PriceAlert.is_active == True)  # noqa: E712
                .options(selectinload(PriceAlert.asset), selectinload(PriceAlert.user))
            )
            alerts = result.scalars().all()

            now = datetime.now(timezone.utc)
            cooldown_cutoff = now - timedelta(hours=_COOLDOWN_HOURS)

            for alert in alerts:
                # Salta se in cooldown
                if alert.last_triggered_at and alert.last_triggered_at > cooldown_cutoff:
                    continue

                cached = await get_cached_price(alert.asset_id)
                if cached is None:
                    continue

                price = cached.get("price", 0.0)
                change_pct = cached.get("change_pct", 0.0) or 0.0

                if _is_triggered(alert.alert_type, alert.threshold, price, change_pct):
                    alert.last_triggered_at = now
                    triggered += 1
                    logger.info(
                        f"Alert {alert.id} scattato: {alert.alert_type} "
                        f"soglia={alert.threshold} prezzo={price:.4f} "
                        f"asset={alert.asset.symbol}"
                    )
                    if settings.email_configured and alert.user and alert.user.email:
                        is_pct = alert.alert_type in (
                            AlertType.CHANGE_PCT_UP, AlertType.CHANGE_PCT_DOWN
                        )
                        current_val = change_pct if is_pct else price
                        try:
                            from app.services.email import send_price_alert
                            await send_price_alert(
                                to=alert.user.email,
                                asset_name=alert.asset.name,
                                asset_symbol=alert.asset.symbol,
                                alert_type=alert.alert_type.value,
                                threshold=float(alert.threshold),
                                current_value=current_val,
                                is_pct=is_pct,
                            )
                        except Exception as mail_exc:
                            logger.warning(f"Invio email alert {alert.id} fallito: {mail_exc}")

            if triggered:
                await db.commit()

        return triggered

    try:
        count = _run(_inner())
        logger.info(f"check_price_alerts: {count} alert scattati")
        return count
    except Exception as exc:
        logger.error(f"check_price_alerts errore: {exc}")
        raise self.retry(exc=exc, countdown=60)
