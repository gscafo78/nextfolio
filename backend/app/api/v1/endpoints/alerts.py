from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.alert import PriceAlert
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertOut, AlertUpdate

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _to_out(a: PriceAlert) -> AlertOut:
    return AlertOut(
        id=a.id,
        asset_id=a.asset_id,
        asset_name=a.asset.name,
        asset_symbol=a.asset.symbol,
        alert_type=a.alert_type.value,
        threshold=a.threshold,
        is_active=a.is_active,
        last_triggered_at=a.last_triggered_at,
        created_at=a.created_at,
    )


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id)
        .options(selectinload(PriceAlert.asset))
        .order_by(PriceAlert.created_at.desc())
    )
    return [_to_out(a) for a in result.scalars()]


@router.post("", response_model=AlertOut, status_code=201)
async def create_alert(
    body: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = PriceAlert(
        user_id=current_user.id,
        asset_id=body.asset_id,
        alert_type=body.alert_type,
        threshold=body.threshold,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    # Carica relazione asset per la risposta
    result = await db.execute(
        select(PriceAlert)
        .where(PriceAlert.id == alert.id)
        .options(selectinload(PriceAlert.asset))
    )
    loaded = result.scalar_one()
    await db.commit()
    return _to_out(loaded)


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: int,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PriceAlert)
        .where(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id)
        .options(selectinload(PriceAlert.asset))
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(404, "Alert non trovato")

    if body.is_active is not None:
        alert.is_active = body.is_active
    if body.threshold is not None:
        alert.threshold = body.threshold

    await db.commit()
    await db.refresh(alert)
    return _to_out(alert)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(404, "Alert non trovato")
    await db.delete(alert)
    await db.commit()
