from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class McpAccessToken(Base):
    """Token di accesso per il server MCP (lettura, scrittura opzionale, cancellazione opzionale).

    Il token in chiaro viene mostrato una sola volta alla creazione; nel DB
    si salva solo lo SHA-256 e un prefisso per riconoscerlo nella UI.
    """

    __tablename__ = "mcp_access_tokens"

    id:              Mapped[int]             = mapped_column(Integer, primary_key=True)
    user_id:         Mapped[int]             = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name:            Mapped[str]             = mapped_column(String(100), nullable=False)
    token_hash:      Mapped[str]             = mapped_column(String(64), nullable=False, unique=True)
    token_prefix:    Mapped[str]             = mapped_column(String(16), nullable=False)
    can_read_values: Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    # Scrittura: crea/modifica transazioni, asset, watchlist e alert
    can_write:       Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    # Cancellazione: elimina transazioni, voci di watchlist e alert (richiede can_write)
    can_delete:      Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    created_at:      Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
