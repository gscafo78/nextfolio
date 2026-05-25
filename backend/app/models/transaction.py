from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    COUPON = "COUPON"
    FEE = "FEE"
    INTEREST = "INTEREST"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(String(20), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Prezzo nella valuta di negoziazione dell'asset (es. USD per ETF su NASDAQ)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Quante EUR per 1 unità di price_currency al momento dell'acquisto.
    # Es.: se price_currency=USD e EURUSD=1.08 → exchange_rate = 1/1.08 ≈ 0.9259
    # Se price_currency=EUR → exchange_rate = 1.0 sempre.
    exchange_rate: Mapped[float] = mapped_column(Float, default=1.0)

    fee: Mapped[float] = mapped_column(Float, default=0.0)
    # Le commissioni sono sempre nella valuta del conto (EUR di default)
    fee_currency: Mapped[str] = mapped_column(String(3), default="EUR")

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    account: Mapped["Account"] = relationship(backref="transactions")  # type: ignore[name-defined]
    asset: Mapped["Asset"] = relationship(back_populates="transactions")  # type: ignore[name-defined]

    @property
    def total_account_currency(self) -> float:
        """Controvalore in valuta del conto (EUR), commissioni incluse."""
        return self.quantity * self.price * self.exchange_rate + self.fee
