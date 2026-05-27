"""Task Celery per la pulizia degli utenti non verificati."""
import asyncio
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.tasks.registration.cleanup_unverified_users")
def cleanup_unverified_users():
    asyncio.run(_cleanup())


async def _cleanup():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(User).where(
                User.email_verified == False,  # noqa: E712
                User.email_verification_expires < now,
            )
        )
        users = result.scalars().all()
        for user in users:
            await db.delete(user)
        if users:
            await db.commit()
            logger.info(f"Eliminati {len(users)} utenti non verificati")
