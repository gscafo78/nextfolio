import datetime

from pydantic import BaseModel


class TaxEventOut(BaseModel):
    date: datetime.date
    asset_id: int
    asset_name: str
    asset_type: str
    tx_type: str
    quantity: float | None
    proceeds_eur: float
    cost_eur: float | None
    gain_loss_eur: float
    tax_bracket: str
    tax_rate: float


class CarryForwardEntryOut(BaseModel):
    year: int
    amount: float
    expires_year: int


class AnnualTaxReportOut(BaseModel):
    year: int

    gains_standard: float
    losses_standard: float
    carryforward_applied_standard: float
    net_taxable_standard: float
    tax_standard: float

    gains_govt: float
    losses_govt: float
    carryforward_applied_govt: float
    net_taxable_govt: float
    tax_govt: float

    dividends_eur: float
    coupons_govt_eur: float
    coupons_standard_eur: float
    interests_eur: float

    total_tax_due: float

    new_carryforward_standard: float
    new_carryforward_govt: float

    prior_carryforward_standard: list[CarryForwardEntryOut]
    prior_carryforward_govt: list[CarryForwardEntryOut]

    events: list[TaxEventOut]


class SimulateSellOut(BaseModel):
    asset_name: str
    asset_type: str
    quantity: float
    current_price_eur: float
    proceeds_eur: float
    cost_basis_eur: float
    gain_loss_eur: float
    tax_bracket: str
    tax_rate: float
    estimated_tax_eur: float
    net_proceeds_eur: float
