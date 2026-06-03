import datetime

from pydantic import BaseModel, field_validator

from app.models.bond_detail import CouponFrequency


class BondDetailCreate(BaseModel):
    face_value: float = 100.0
    coupon_rate: float                   # tasso annuo decimale (es. 0.0165 per 1,65%)
    coupon_frequency: CouponFrequency
    first_coupon_date: datetime.date
    maturity_date: datetime.date | None = None
    issue_date: datetime.date | None = None

    @field_validator("coupon_rate")
    @classmethod
    def rate_in_range(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError("coupon_rate deve essere in formato decimale (es. 0.0165 per 1,65%)")
        return v


class BondDetailOut(BaseModel):
    id: int
    asset_id: int
    face_value: float
    coupon_rate: float
    coupon_frequency: CouponFrequency
    first_coupon_date: datetime.date
    maturity_date: datetime.date | None
    issue_date: datetime.date | None
    coupon_per_unit: float
    enriched_from_bi: bool

    model_config = {"from_attributes": True}


class CouponScheduleEntry(BaseModel):
    date: datetime.date
    coupon_per_unit: float
    total_coupon_eur: float              # qty × coupon_per_unit (se passata)
    days_until: int                      # giorni a oggi (negativo = già passata)
    already_recorded: bool = False       # True se esiste transazione COUPON per questa data


class UpcomingCouponEntry(BaseModel):
    asset_id: int
    asset_name: str
    isin: str | None
    date: datetime.date
    coupon_per_unit: float
    quantity: float
    total_coupon_eur: float
    days_until: int
    already_recorded: bool


class BondEnrichmentResult(BaseModel):
    asset_id: int
    bond_detail: BondDetailOut
    source: str = "borsa_italiana"
