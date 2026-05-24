from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AssetType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    BOND = "BOND"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"
    REIT = "REIT"


class Exchange(str, Enum):
    MIL = "MIL"
    EUROTLX = "EuroTLX"
    MOT = "MOT"
    XETRA = "XETRA"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    CRYPTO = "CRYPTO"
    OTHER = "OTHER"


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("isin", name="uq_assets_isin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[AssetType] = mapped_column(nullable=False)
    exchange: Mapped[Exchange] = mapped_column(default=Exchange.OTHER)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    sector: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="asset")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_price_history_asset_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)

    asset: Mapped["Asset"] = relationship(back_populates="price_history")
