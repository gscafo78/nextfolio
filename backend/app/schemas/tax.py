import datetime

from pydantic import BaseModel


class IVAFEPositionOut(BaseModel):
    asset_id: int
    asset_name: str
    asset_type: str
    quantity: float
    price_eur: float
    market_value_eur: float
    ivafe_eur: float
    price_date: datetime.date | None


class IVAFEReportOut(BaseModel):
    year: int
    total_market_value_eur: float = 0.0
    ivafe_eur: float = 0.0
    positions: list[IVAFEPositionOut] = []
    rate: float = 0.002
    has_foreign_accounts: bool = False


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
    is_sostituto_imposta: bool
    calculation_method: str = "PMC"


class CarryForwardEntryOut(BaseModel):
    year: int
    amount: float
    expires_year: int


class AnnualTaxReportOut(BaseModel):
    year: int

    # Redditi diversi al 26% — importi reali
    gains_standard: float
    losses_standard: float
    # Titoli di Stato — importi reali, nello zainetto al 48,08% (govt_weight)
    gains_govt: float
    losses_govt: float
    govt_weight: float
    # ETF/OICR: minus nello zainetto, plus tassate a parte (redditi di capitale)
    losses_funds: float = 0.0
    gains_funds: float = 0.0
    tax_funds: float = 0.0

    # Zainetto unico 26% (importi ponderati)
    taxable_gains_standard: float
    taxable_losses_standard: float
    carryforward_applied_standard: float
    net_taxable_standard: float
    tax_standard: float
    new_carryforward_standard: float
    prior_carryforward_standard: list[CarryForwardEntryOut]

    # Cripto-attività
    gains_crypto: float = 0.0
    losses_crypto: float = 0.0
    crypto_rate: float = 0.26
    carryforward_applied_crypto: float = 0.0
    net_taxable_crypto: float = 0.0
    tax_crypto: float = 0.0
    new_carryforward_crypto: float = 0.0
    prior_carryforward_crypto: list[CarryForwardEntryOut] = []

    dividends_eur: float
    coupons_govt_eur: float
    coupons_standard_eur: float
    interests_eur: float
    income_tax_eur: float = 0.0
    administered_income_tax: float = 0.0
    declaratory_income_tax: float = 0.0

    total_tax_due: float

    events: list[TaxEventOut]

    # Breakdown per regime
    administered_gains_standard: float = 0.0
    administered_losses_standard: float = 0.0
    administered_gains_govt: float = 0.0
    administered_losses_govt: float = 0.0
    administered_gains_funds: float = 0.0
    administered_losses_funds: float = 0.0
    administered_gains_crypto: float = 0.0
    administered_losses_crypto: float = 0.0
    administered_taxable_gains: float = 0.0
    administered_taxable_losses: float = 0.0
    administered_tax_standard: float = 0.0
    administered_tax_funds: float = 0.0
    administered_tax_crypto: float = 0.0
    administered_dividends_eur: float = 0.0
    administered_total_tax: float = 0.0

    declaratory_gains_standard: float = 0.0
    declaratory_losses_standard: float = 0.0
    declaratory_gains_govt: float = 0.0
    declaratory_losses_govt: float = 0.0
    declaratory_gains_funds: float = 0.0
    declaratory_losses_funds: float = 0.0
    declaratory_gains_crypto: float = 0.0
    declaratory_losses_crypto: float = 0.0
    declaratory_taxable_gains: float = 0.0
    declaratory_taxable_losses: float = 0.0
    declaratory_tax_standard: float = 0.0
    declaratory_tax_funds: float = 0.0
    declaratory_tax_crypto: float = 0.0
    declaratory_dividends_eur: float = 0.0
    declaratory_total_tax: float = 0.0

    has_declaratory_accounts: bool = False

    ivafe: IVAFEReportOut = IVAFEReportOut(year=0)


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
