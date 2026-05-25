import datetime

from pydantic import BaseModel, field_validator

from app.models.alert import AlertType


class AlertCreate(BaseModel):
    asset_id: int
    alert_type: AlertType
    threshold: float

    @field_validator("threshold")
    @classmethod
    def threshold_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La soglia deve essere positiva")
        return v


class AlertUpdate(BaseModel):
    is_active: bool | None = None
    threshold: float | None = None


class AlertOut(BaseModel):
    id: int
    asset_id: int
    asset_name: str
    asset_symbol: str
    alert_type: str
    threshold: float
    is_active: bool
    last_triggered_at: datetime.datetime | None
    created_at: datetime.datetime
