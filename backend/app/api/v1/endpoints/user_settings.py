from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserSettingsOut, UserSettingsUpdate
from app.services.user import get_or_create_settings, update_settings

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/settings", response_model=UserSettingsOut)
async def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_settings(db, current_user.id)


@router.patch("/settings", response_model=UserSettingsOut)
async def update_my_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_or_create_settings(db, current_user.id)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return settings
    return await update_settings(db, settings, **fields)
