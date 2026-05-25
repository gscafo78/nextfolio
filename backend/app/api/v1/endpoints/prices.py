from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.asset import get_asset_by_id
from sqlalchemy import select

from app.models.asset import AssetType, PriceHistory
from app.services.market_data.updater import (
    fetch_asset_history,
    get_cached_price,
    refresh_asset_price,
)

router = APIRouter(prefix="/assets", tags=["prices"])


class PriceOut(BaseModel):
    asset_id: int
    symbol: str
    price: float
    prev_close: float | None = None
    change_pct: float
    currency: str


class OHLCVOut(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None


@router.get("/{asset_id}/price", response_model=PriceOut)
async def get_price(
    asset_id: int,
    refresh: bool = Query(False, description="Forza aggiornamento ignorando la cache"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")

    if not refresh:
        cached = await get_cached_price(asset_id)
        if cached:
            return PriceOut(asset_id=asset_id, symbol=asset.symbol, **cached)

    data = await refresh_asset_price(db, asset)
    if not data:
        # Fallback: ultimo record in price_history
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset_id)
            .order_by(PriceHistory.date.desc())
            .limit(2)
        )
        rows = list(result.scalars())
        if rows:
            last, prev = rows[0], rows[1] if len(rows) >= 2 else rows[0]
            change_pct = round((last.close - prev.close) / prev.close * 100, 4) if prev.close else 0.0
            return PriceOut(
                asset_id=asset_id,
                symbol=asset.yahoo_ticker or asset.symbol,
                price=last.close,
                prev_close=prev.close,
                change_pct=change_pct,
                currency=asset.currency,
            )
        raise HTTPException(503, f"Prezzo non disponibile per {asset.symbol}")

    return PriceOut(asset_id=asset_id, symbol=asset.yahoo_ticker or asset.symbol, **data)


@router.get("/{asset_id}/history", response_model=list[OHLCVOut])
async def get_history(
    asset_id: int,
    period: str = Query("1y", pattern="^(1w|1mo|3mo|6mo|1y|3y|5y|max)$"),
    source: str = Query("db", pattern="^(db|live)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    source=db  → usa price_history nel DB (più veloce, aggiornato dall'EOD task)
    source=live → scarica direttamente da Yahoo/CoinGecko (più fresco, più lento)
    """
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")

    if source == "live":
        # Usa la fonte migliore: BI per italiani con ISIN, Yahoo/CoinGecko altrimenti
        records = await fetch_asset_history(asset, period=period)
        return [OHLCVOut(**r) for r in records]

    # source=db: legge dal price_history
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id)
        .order_by(PriceHistory.date.asc())
    )
    rows = list(result.scalars())
    return [
        OHLCVOut(
            date=r.date.isoformat(),
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in rows
    ]


@router.post("/{asset_id}/backfill", status_code=202)
async def backfill(
    asset_id: int,
    period: str = Query("1y", pattern="^(1w|1mo|3mo|6mo|1y|3y|5y|max)$"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Avvia il backfill dello storico in background (Celery)."""
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    from app.tasks.prices import backfill_asset_history
    backfill_asset_history.delay(asset_id, period)
    return {"detail": f"Backfill avviato per {asset.symbol} ({period})"}
