from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.schemas.asset import AssetCreate


async def search_assets(db: AsyncSession, q: str, limit: int = 20) -> list[Asset]:
    q = f"%{q.upper()}%"
    result = await db.execute(
        select(Asset)
        .where(or_(Asset.symbol.ilike(q), Asset.isin.ilike(q), Asset.name.ilike(q)))
        .limit(limit)
    )
    return list(result.scalars())


async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Asset | None:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalar_one_or_none()


async def get_asset_by_isin(db: AsyncSession, isin: str) -> Asset | None:
    result = await db.execute(select(Asset).where(Asset.isin == isin))
    return result.scalar_one_or_none()


async def create_asset(db: AsyncSession, data: AssetCreate) -> Asset:
    asset = Asset(**data.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def get_or_create_asset(db: AsyncSession, data: AssetCreate) -> Asset:
    if data.isin:
        existing = await get_asset_by_isin(db, data.isin)
        if existing:
            return existing
    return await create_asset(db, data)
