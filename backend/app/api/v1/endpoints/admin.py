import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_superadmin
from app.core.security import create_password_reset_token, hash_password
from app.models.asset import Asset, AssetType
from app.models.user import User
from app.schemas.user import UserAdminOut, UserAdminUpdate, UserCreate
from app.services.email import send_password_reset, send_test, send_welcome
from app.services.audit import (
    BULK_ENRICH,
    CREATE_USER,
    DELETE_USER,
    UPDATE_USER,
    get_audit_logs,
    log_action,
)
from app.services.user import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    user_email: str | None
    action: str
    entity_type: str | None
    entity_id: int | None
    detail: dict | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserAdminOut])
async def get_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    return await list_users(db)


@router.post("/users", response_model=UserAdminOut, status_code=201)
async def create_new_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    if await get_user_by_email(db, body.email):
        raise HTTPException(400, "Email già registrata")
    new_user = await create_user(db, body.email, hash_password(body.password), body.name, role=body.role)
    await log_action(
        db,
        user_id=current_admin.id,
        action=CREATE_USER,
        entity_type="user",
        entity_id=new_user.id,
        detail={"email": new_user.email, "role": new_user.role.value if hasattr(new_user.role, "value") else str(new_user.role)},
    )
    return new_user


@router.patch("/users/{user_id}", response_model=UserAdminOut)
async def update_user_admin(
    user_id: int,
    body: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")

    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.role is not None:
        fields["role"] = body.role
    if body.is_active is not None:
        if user_id == current_admin.id and not body.is_active:
            raise HTTPException(400, "Non puoi disabilitare il tuo account")
        fields["is_active"] = body.is_active
    if body.reset_2fa:
        fields["two_factor_enabled"] = False
        fields["two_factor_secret"] = None

    updated = await update_user(db, user, **fields)
    await log_action(
        db,
        user_id=current_admin.id,
        action=UPDATE_USER,
        entity_type="user",
        entity_id=user_id,
        detail={k: str(v) for k, v in fields.items()},
    )
    return updated


@router.delete("/users/{user_id}", status_code=204)
async def delete_user_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    if user_id == current_admin.id:
        raise HTTPException(400, "Non puoi eliminare il tuo account")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    await log_action(
        db,
        user_id=current_admin.id,
        action=DELETE_USER,
        entity_type="user",
        entity_id=user_id,
        detail={"email": user.email},
    )
    await delete_user(db, user)


@router.post("/enrich-assets", status_code=202)
async def enrich_assets_bulk(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    """Avvia enrichment bulk di tutti gli asset in background (admin only)."""
    from app.services.market_data.enricher import enrich_asset

    async def _bulk(asset_ids: list[int]) -> None:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            for aid in asset_ids:
                result = await session.execute(select(Asset).where(Asset.id == aid))
                asset = result.scalar_one_or_none()
                if asset:
                    try:
                        await enrich_asset(session, asset)
                    except Exception:
                        pass

    result = await db.execute(
        select(Asset).where(
            Asset.type.in_([AssetType.STOCK, AssetType.ETF, AssetType.BOND, AssetType.REIT])
        )
    )
    asset_ids = [a.id for a in result.scalars()]
    background_tasks.add_task(_bulk, asset_ids)
    await log_action(
        db,
        user_id=current_admin.id,
        action=BULK_ENRICH,
        detail={"queued": len(asset_ids)},
    )
    return {"queued": len(asset_ids)}


@router.patch("/assets/{asset_id}/profile", status_code=200)
async def patch_asset_profile(
    asset_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    """
    Override manuale di sectors, countries, holdings per un asset.
    Passa null per un campo per rimuovere l'override e usare i dati auto-enriched.

    Body example:
    {
      "sectors_override": [{"name": "Technology", "weight": 0.7}, {"name": "Finance", "weight": 0.3}],
      "countries_override": [{"code": "United States", "name": "United States", "weight": 1.0}],
      "holdings_override": [{"symbol": "AAPL", "name": "Apple Inc", "weight": 0.04}]
    }
    """
    from app.models.asset import Asset
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset non trovato")

    allowed_fields = {"sectors_override", "countries_override", "holdings_override"}
    for field, value in body.items():
        if field in allowed_fields:
            setattr(asset, field, value)

    await db.commit()
    await log_action(
        db,
        user_id=current_admin.id,
        action="PATCH_ASSET_PROFILE",
        entity_type="asset",
        entity_id=asset_id,
        detail={"fields": list(body.keys()), "symbol": asset.symbol},
    )
    return {
        "asset_id": asset_id,
        "symbol": asset.symbol,
        "sectors_override": asset.sectors_override,
        "countries_override": asset.countries_override,
        "holdings_override": asset.holdings_override,
    }


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    action: str | None = Query(None),
    user_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    logs = await get_audit_logs(db, limit=limit, offset=offset, action=action, user_id=user_id)
    return [
        AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_email=log.user.email if log.user else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            detail=log.detail,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ── Email management ──────────────────────────────────────────────────────────

class EmailConfigOut(BaseModel):
    configured: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    emails_from: str


class TestEmailBody(BaseModel):
    to: EmailStr


class WelcomeEmailBody(BaseModel):
    temp_password: str


class ResetLinkBody(BaseModel):
    pass


@router.get("/email/config", response_model=EmailConfigOut)
async def get_email_config(_: User = Depends(require_superadmin)):
    """Restituisce la configurazione SMTP corrente (senza password)."""
    return EmailConfigOut(
        configured=settings.email_configured,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_user=settings.SMTP_USER,
        emails_from=settings.EMAILS_FROM,
    )


@router.post("/email/test", status_code=202)
async def test_email(body: TestEmailBody, _: User = Depends(require_superadmin)):
    """Invia un'email di test all'indirizzo specificato."""
    try:
        await send_test(body.to)
    except Exception as exc:
        raise HTTPException(502, f"Errore SMTP: {exc}") from exc
    return {"detail": f"Email di test inviata a {body.to}"}


@router.post("/email/welcome/{user_id}", status_code=202)
async def send_welcome_email(
    user_id: int,
    body: WelcomeEmailBody,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    """Invia email di benvenuto con password temporanea all'utente."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    try:
        await send_welcome(user.email, user.name, body.temp_password)
    except Exception as exc:
        raise HTTPException(502, f"Errore SMTP: {exc}") from exc
    return {"detail": f"Email di benvenuto inviata a {user.email}"}


@router.post("/email/reset-link/{user_id}", status_code=202)
async def send_reset_link(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    """Invia all'utente un link per reimpostare la password."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    token = create_password_reset_token(str(user.id))
    try:
        await send_password_reset(user.email, token)
    except Exception as exc:
        raise HTTPException(502, f"Errore SMTP: {exc}") from exc
    return {"detail": f"Link di reset inviato a {user.email}"}
