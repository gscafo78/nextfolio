from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.importer.ghostfolio import execute, preview

router = APIRouter(prefix="/import/ghostfolio", tags=["import"])


class PreviewRequest(BaseModel):
    raw: dict


class AccountResolution(BaseModel):
    ghostfolio_id: str
    action: str  # "create" | "use_existing"
    existing_id: int | None = None
    name: str | None = None
    broker: str | None = None
    currency: str = "EUR"


class AssetResolution(BaseModel):
    ghostfolio_symbol: str
    action: str  # "create" | "use_existing" | "skip"
    existing_id: int | None = None
    name: str | None = None
    symbol: str | None = None
    type: str | None = None
    exchange: str | None = None
    currency: str = "EUR"
    isin: str | None = None
    wkn: str | None = None
    import_price_history: bool = True


class ExecuteRequest(BaseModel):
    raw: dict
    accounts: list[AccountResolution]
    assets: list[AssetResolution]


@router.post("/preview")
async def ghostfolio_preview(
    body: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analizza un export Ghostfolio e restituisce gli elementi da risolvere."""
    try:
        return await preview(body.raw, db, current_user.id)
    except Exception as e:
        raise HTTPException(400, f"File non valido: {e}")


@router.post("/execute")
async def ghostfolio_execute(
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Esegue l'import con le risoluzioni scelte dall'utente."""
    resolutions = {
        "accounts": [a.model_dump() for a in body.accounts],
        "assets": [a.model_dump() for a in body.assets],
    }
    try:
        return await execute(body.raw, resolutions, db, current_user.id)
    except Exception as e:
        raise HTTPException(500, f"Errore durante l'import: {e}")
