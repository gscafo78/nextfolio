"""
Funzioni AI:
- GET  /ai/prompt            → testo da incollare in un chatbot (dati + istruzioni di analisi)
- GET  /ai/mcp-tokens        → token di accesso al server MCP dell'utente
- POST /ai/mcp-tokens        → crea un token (restituito in chiaro una sola volta)
- DELETE /ai/mcp-tokens/{id} → revoca un token
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.mcp.server import MCP_PATH
from app.mcp.tokens import generate_token, hash_token
from app.models.account import Account
from app.models.mcp_token import McpAccessToken
from app.models.user import User
from app.services.ai.context import SUPPORTED_LANGUAGES, build_prompt
from app.services.audit import CREATE_MCP_TOKEN, REVOKE_MCP_TOKEN, log_action

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_TOKENS_PER_USER = 20


# ── Prompt ───────────────────────────────────────────────────────────────────


class PromptOut(BaseModel):
    prompt: str


@router.get("/prompt", response_model=PromptOut)
async def get_prompt(
    mode: Literal["analysis", "portfolio"] = Query("analysis"),
    lang: str = Query("it", pattern=r"^(it|en|fr|de)$"),
    include_values: bool = Query(True),
    account_id: int | None = Query(None),
    asset_type: Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"] | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if account_id is not None:
        acc = await db.get(Account, account_id)
        if not acc or acc.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conto non trovato")
    prompt = await build_prompt(
        db, current_user,
        mode=mode,
        language=lang if lang in SUPPORTED_LANGUAGES else "en",
        with_values=include_values,
        account_id=account_id,
        asset_type=asset_type,
    )
    return PromptOut(prompt=prompt)


# ── Token MCP ────────────────────────────────────────────────────────────────


class McpTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    can_read_values: bool = False


class McpTokenOut(BaseModel):
    id: int
    name: str
    token_prefix: str
    can_read_values: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class McpTokenCreated(McpTokenOut):
    token: str


class McpInfoOut(BaseModel):
    enabled: bool
    path: str
    tokens: list[McpTokenOut]


@router.get("/mcp-tokens", response_model=McpInfoOut)
async def list_mcp_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(McpAccessToken)
        .where(McpAccessToken.user_id == current_user.id, McpAccessToken.revoked_at.is_(None))
        .order_by(McpAccessToken.created_at.desc())
    )
    return McpInfoOut(
        enabled=settings.ENABLE_MCP,
        path=MCP_PATH,
        tokens=[McpTokenOut.model_validate(t) for t in res.scalars()],
    )


@router.post("/mcp-tokens", response_model=McpTokenCreated, status_code=201)
async def create_mcp_token(
    body: McpTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(McpAccessToken.id)
        .where(McpAccessToken.user_id == current_user.id, McpAccessToken.revoked_at.is_(None))
    )
    if len(res.all()) >= MAX_TOKENS_PER_USER:
        raise HTTPException(status_code=400, detail=f"Massimo {MAX_TOKENS_PER_USER} token attivi")

    token = generate_token()
    row = McpAccessToken(
        user_id=current_user.id,
        name=body.name.strip(),
        token_hash=hash_token(token),
        token_prefix=token[:12],
        can_read_values=body.can_read_values,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    await log_action(
        db, user_id=current_user.id, action=CREATE_MCP_TOKEN, entity_type="mcp_token", entity_id=row.id,
        detail={"name": row.name, "can_read_values": row.can_read_values},
    )
    await db.commit()
    await db.refresh(row)
    return McpTokenCreated(**McpTokenOut.model_validate(row).model_dump(), token=token)


@router.delete("/mcp-tokens/{token_id}", status_code=204)
async def revoke_mcp_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await db.get(McpAccessToken, token_id)
    if not row or row.user_id != current_user.id or row.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Token non trovato")
    row.revoked_at = datetime.now(timezone.utc)
    await log_action(
        db, user_id=current_user.id, action=REVOKE_MCP_TOKEN, entity_type="mcp_token", entity_id=row.id,
        detail={"name": row.name},
    )
    await db.commit()
