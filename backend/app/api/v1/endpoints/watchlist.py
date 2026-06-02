from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset
from app.models.user import User
from app.models.watchlist import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ── Schemi ────────────────────────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    asset_id: int
    note: str | None = None
    target_price: float | None = None


class WatchlistUpdate(BaseModel):
    note: str | None = None
    target_price: float | None = None


class WatchlistOut(BaseModel):
    id: int
    asset_id: int
    symbol: str
    name: str
    asset_type: str
    currency: str
    note: str | None
    target_price: float | None
    current_price: float | None = None
    current_price_eur: float | None = None
    change_pct: float | None = None
    added_at: str

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enrich_with_price(item: WatchlistItem, db: AsyncSession) -> WatchlistOut:
    from app.services.market_data.updater import get_cached_price
    from app.api.v1.endpoints.portfolio import _price_from_db

    asset = item.asset
    data = await get_cached_price(asset.id)
    if data is None:
        data = await _price_from_db(db, asset) or {}

    price     = data.get("price")
    fx        = data.get("exchange_rate", 1.0)
    change    = data.get("change_pct")
    price_eur = price * fx if price is not None else None

    return WatchlistOut(
        id=item.id,
        asset_id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        asset_type=asset.type if isinstance(asset.type, str) else asset.type.value,
        currency=asset.currency,
        note=item.note,
        target_price=item.target_price,
        current_price=round(price, 4) if price else None,
        current_price_eur=round(price_eur, 4) if price_eur else None,
        change_pct=round(change, 2) if change is not None else None,
        added_at=item.added_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WatchlistOut])
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.added_at.desc())
    )
    items = result.scalars().all()
    return [await _enrich_with_price(i, db) for i in items]


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verifica che l'asset esista
    asset = await db.get(Asset, body.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset non trovato")

    # Controlla duplicato
    existing = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == current_user.id)
        .where(WatchlistItem.asset_id == body.asset_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Asset già in watchlist")

    item = WatchlistItem(
        user_id=current_user.id,
        asset_id=body.asset_id,
        note=body.note,
        target_price=body.target_price,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return await _enrich_with_price(item, db)


@router.patch("/{item_id}", response_model=WatchlistOut)
async def update_watchlist_item(
    item_id: int,
    body: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await db.get(WatchlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Elemento non trovato")
    if body.note is not None:
        item.note = body.note
    if body.target_price is not None:
        item.target_price = body.target_price
    elif "target_price" in body.model_fields_set:
        item.target_price = None
    await db.commit()
    await db.refresh(item)
    return await _enrich_with_price(item, db)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await db.get(WatchlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Elemento non trovato")
    await db.delete(item)
    await db.commit()
