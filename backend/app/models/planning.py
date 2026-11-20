"""Pagina Pianifica: scenari di acquisto salvati."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlanningScenario(Base):
    __tablename__ = "planning_scenarios"

    id:          Mapped[int]             = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]             = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str]             = mapped_column(String(100), nullable=False)
    notes:       Mapped[str | None]      = mapped_column(Text, nullable=True)
    use_cash:    Mapped[bool]            = mapped_column(default=False)
    status:      Mapped[str]             = mapped_column(String(20), default="draft")   # draft | executed
    created_at:  Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:  Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["PlanningScenarioItem"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", order_by="PlanningScenarioItem.id", lazy="selectin",
    )


class PlanningScenarioItem(Base):
    """Acquisto ipotetico. ``asset_id`` per titoli in Nextfolio, ``symbol`` (Yahoo) per gli altri."""

    __tablename__ = "planning_scenario_items"

    id:          Mapped[int]          = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int]          = mapped_column(Integer, ForeignKey("planning_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id:    Mapped[int | None]   = mapped_column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    symbol:      Mapped[str | None]   = mapped_column(String(50), nullable=True)
    isin:        Mapped[str | None]   = mapped_column(String(12), nullable=True)
    name:        Mapped[str]          = mapped_column(String(200), nullable=False)
    type:        Mapped[str]          = mapped_column(String(20), nullable=False)
    currency:    Mapped[str | None]   = mapped_column(String(3), nullable=True)
    exchange:    Mapped[str | None]   = mapped_column(String(20), nullable=True)
    amount_eur:  Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity:    Mapped[float | None] = mapped_column(Float, nullable=True)
    price_eur:   Mapped[float | None] = mapped_column(Float, nullable=True)
    fee_eur:     Mapped[float]        = mapped_column(Float, default=0.0)
    account_id:  Mapped[int | None]   = mapped_column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    scenario: Mapped[PlanningScenario] = relationship(back_populates="items")
