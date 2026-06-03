from datetime import date
from enum import Enum

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CouponFrequency(str, Enum):
    ANNUAL      = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY   = "QUARTERLY"
    MONTHLY     = "MONTHLY"

    @property
    def divisor(self) -> int:
        return {"ANNUAL": 1, "SEMI_ANNUAL": 2, "QUARTERLY": 4, "MONTHLY": 12}[self.value]

    @property
    def months_between(self) -> int:
        return 12 // self.divisor


class BondDetail(Base):
    __tablename__ = "bond_details"
    __table_args__ = (UniqueConstraint("asset_id", name="uq_bond_details_asset"),)

    id: Mapped[int]  = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    face_value: Mapped[float] = mapped_column(Float, default=100.0)
    coupon_rate: Mapped[float] = mapped_column(Float, nullable=False)          # tasso annuo (es. 0.0165)
    coupon_frequency: Mapped[CouponFrequency] = mapped_column(String(20), nullable=False)
    first_coupon_date: Mapped[date] = mapped_column(Date, nullable=False)      # ancora calendario cedole
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enriched_from_bi: Mapped[bool] = mapped_column(Boolean, default=False)    # True se da Borsa Italiana

    asset = relationship("Asset", back_populates="bond_detail")

    @property
    def coupon_per_unit(self) -> float:
        freq = CouponFrequency(self.coupon_frequency)
        return round(self.face_value * self.coupon_rate / freq.divisor, 5)
