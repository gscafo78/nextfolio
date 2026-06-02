from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),)

    id:           Mapped[int]            = mapped_column(Integer, primary_key=True)
    user_id:      Mapped[int]            = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id:     Mapped[int]            = mapped_column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    note:         Mapped[str | None]     = mapped_column(Text, nullable=True)
    target_price: Mapped[float | None]   = mapped_column(Float, nullable=True)
    added_at:     Mapped[datetime]       = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    asset = relationship("Asset", lazy="joined")
