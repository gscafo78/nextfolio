from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetOut, AssetSearch, AssetUpdate
from app.services.asset import create_asset, get_asset_by_id, search_assets, update_asset

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/search", response_model=list[AssetSearch])
async def search(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await search_assets(db, q)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    return asset


@router.patch("/{asset_id}", response_model=AssetOut)
async def patch_asset(
    asset_id: int,
    body: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    return await update_asset(db, asset, body)


@router.post("", response_model=AssetOut, status_code=201)
async def create(
    body: AssetCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await create_asset(db, body)
