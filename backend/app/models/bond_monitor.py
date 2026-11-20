from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BondMonitor(Base):
    """Monitoraggio giornaliero della convenienza a vendere un'obbligazione (email quando conviene).

    ``active`` = la condizione «vendere conviene» è vera e l'email è già stata inviata: si riarma
    solo quando la condizione smette di valere.
    """

    __tablename__ = "bond_monitors"
    __table_args__ = (UniqueConstraint("user_id", "asset_id", name="uq_bond_monitors_user_asset"),)

    id:               Mapped[int]             = mapped_column(Integer, primary_key=True)
    user_id:          Mapped[int]             = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id:         Mapped[int]             = mapped_column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    enabled:          Mapped[bool]            = mapped_column(Boolean, nullable=False, default=True)
    active:           Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result:      Mapped[dict | None]     = mapped_column(JSONB, nullable=True)
    created_at:       Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
