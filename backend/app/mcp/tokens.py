"""Generazione e verifica dei token di accesso MCP."""
import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_token import McpAccessToken
from app.models.user import User

TOKEN_PREFIX = "nfmcp_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


async def resolve_token(db: AsyncSession, token: str | None) -> tuple[User, McpAccessToken] | None:
    """Restituisce (utente, token) se il token è valido, non revocato e l'utente è attivo."""
    if not token or not token.startswith(TOKEN_PREFIX):
        return None
    res = await db.execute(
        select(McpAccessToken, User)
        .join(User, User.id == McpAccessToken.user_id)
        .where(McpAccessToken.token_hash == hash_token(token))
        .where(McpAccessToken.revoked_at.is_(None))
    )
    row = res.first()
    if not row:
        return None
    access, user = row
    if not user.is_active:
        return None
    access.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return user, access
