from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog

# ── Costanti azioni ────────────────────────────────────────────────────────────

DELETE_TRANSACTION = "DELETE_TRANSACTION"
DELETE_ACCOUNT = "DELETE_ACCOUNT"
CREATE_USER = "CREATE_USER"
UPDATE_USER = "UPDATE_USER"
DELETE_USER = "DELETE_USER"
BULK_ENRICH = "BULK_ENRICH_ASSETS"
PATCH_ASSET_PROFILE = "PATCH_ASSET_PROFILE"


async def log_action(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)
    # Flush immediately so the log is committed with the surrounding transaction.
    await db.flush()


async def get_audit_logs(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    user_id: int | None = None,
) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
