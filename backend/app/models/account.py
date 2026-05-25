from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AccountType(str, Enum):
    BROKERAGE = "BROKERAGE"
    BANK = "BANK"
    CRYPTO = "CRYPTO"
    PENSION = "PENSION"
    OTHER = "OTHER"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[AccountType] = mapped_column(String(20), default=AccountType.BROKERAGE)
    broker: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", backref="accounts")
