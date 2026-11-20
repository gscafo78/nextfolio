"""
Task Celery: controllo giornaliero della convenienza a vendere le obbligazioni monitorate.

Eseguito ogni giorno lavorativo alle 10:00 Europe/Rome. Per ogni monitor attivo valuta
«vendi ora» contro «tieni a scadenza» (``services/bonds/monitor.py``) e invia **una** email
quando vendere diventa conveniente; si riarma solo se la condizione rientra e si ripresenta.
Se la posizione è chiusa o il titolo è scaduto il monitor viene disattivato.
"""
import asyncio
import datetime
from datetime import timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import celery_db_session
from app.models.asset import Asset
from app.models.bond_monitor import BondMonitor
from app.services.bonds.monitor import evaluate_for_user, next_notification_state
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_DISABLE_REASONS = ("Nessuna posizione aperta", "Il titolo è scaduto")


async def process_bond_monitors(db, send_signal=None, today: datetime.date | None = None) -> dict:
    """Valuta tutti i monitor abilitati; restituisce {checked, notified, disabled, missing}."""
    if send_signal is None:
        from app.services.email import send_bond_sell_signal as send_signal   # noqa: PLC0415
    stats = {"checked": 0, "notified": 0, "disabled": 0, "missing": 0}
    monitors = (await db.execute(
        select(BondMonitor).where(BondMonitor.enabled == True)  # noqa: E712
    )).scalars().all()

    now = datetime.datetime.now(timezone.utc)
    for m in monitors:
        try:
            ev = await evaluate_for_user(db, m.user_id, m.asset_id, today=today)
            stats["checked"] += 1
            m.last_checked_at = now
            m.last_result = ev.to_dict()

            if ev.status != "ok":
                stats["missing"] += 1
                m.active = False
                if ev.reason and ev.reason.startswith(_DISABLE_REASONS):
                    m.enabled = False
                    stats["disabled"] += 1
                    logger.info("Monitor %s disattivato: %s", m.id, ev.reason)
                continue

            send, m.active = next_notification_state(ev.should_sell, m.active)
            if not send:
                continue
            from app.models.user import User   # noqa: PLC0415
            user = await db.get(User, m.user_id)
            asset = await db.get(Asset, m.asset_id)
            if not settings.email_configured or not user or not user.email:
                logger.warning("Monitor %s: condizione vera ma email non inviabile (SMTP/utente)", m.id)
                m.active = False          # riproverà al prossimo controllo
                continue
            try:
                await send_signal(to=user.email, asset_name=asset.name, isin=asset.isin, asset_id=asset.id, ev=ev.to_dict())
                m.last_notified_at = now
                stats["notified"] += 1
                logger.info("Monitor %s: email inviata (%s, vantaggio %.2f €)", m.id, asset.name, ev.advantage_eur)
            except Exception as mail_exc:  # invio fallito: si riprova al prossimo giorno lavorativo
                m.active = False
                logger.warning("Monitor %s: invio email fallito: %s", m.id, mail_exc)
        except Exception as exc:  # un titolo problematico non blocca gli altri
            logger.error("Monitor %s: errore di valutazione: %s", m.id, exc)
    await db.commit()
    return stats


@celery_app.task(name="app.tasks.bond_monitor.check_bond_monitors", bind=True, max_retries=2)
def check_bond_monitors(self):
    """Controlla la convenienza a vendere per ogni obbligazione monitorata."""
    async def _inner():
        async with celery_db_session() as db:
            return await process_bond_monitors(db)

    try:
        stats = _run(_inner())
        logger.info("check_bond_monitors: %s", stats)
        return stats
    except Exception as exc:
        logger.error("check_bond_monitors errore: %s", exc)
        raise self.retry(exc=exc, countdown=300)
