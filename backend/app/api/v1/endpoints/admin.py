from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_superadmin
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserAdminOut, UserAdminUpdate, UserCreate
from app.services.user import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)

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
    _: User = Depends(require_superadmin),
):
    if await get_user_by_email(db, body.email):
        raise HTTPException(400, "Email già registrata")
    return await create_user(db, body.email, hash_password(body.password), body.name, role=body.role)


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

    return await update_user(db, user, **fields)


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
    await delete_user(db, user)
