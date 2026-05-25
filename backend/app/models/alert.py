from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AlertType(str, Enum):
    PRICE_ABOVE = "PRICE_ABOVE"       # prezzo sale sopra la soglia
    PRICE_BELOW = "PRICE_BELOW"       # prezzo scende sotto la soglia
    CHANGE_PCT_UP = "CHANGE_PCT_UP"   # variazione giornaliera positiva > soglia%
    CHANGE_PCT_DOWN = "CHANGE_PCT_DOWN"  # variazione giornaliera negativa > soglia%


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    alert_type: Mapped[AlertType] = mapped_column(String(20), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]
    asset: Mapped["Asset"] = relationship()  # type: ignore[name-defined]
