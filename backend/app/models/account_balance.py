from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountBalance(Base):
    """Saldo di cassa di un conto a una data, nella valuta del conto.

    Un solo saldo per conto e data: un nuovo inserimento nella stessa data lo
    sostituisce. Il saldo più recente è quello corrente.
    """

    __tablename__ = "account_balances"
    __table_args__ = (UniqueConstraint("account_id", "date", name="uq_account_balances_account_date"),)

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int]      = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    date:       Mapped[date]     = mapped_column(Date, nullable=False)
    balance:    Mapped[float]    = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
