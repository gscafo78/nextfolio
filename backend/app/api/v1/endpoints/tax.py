from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset
from app.models.user import User
from app.schemas.tax import AnnualTaxReportOut, SimulateSellOut, TaxEventOut, CarryForwardEntryOut
from app.services.market_data.updater import get_cached_price, refresh_asset_price
from app.services.portfolio.positions import calculate_positions
from app.services.tax.calculator import (
    AnnualTaxReport,
    build_annual_reports,
    compute_tax_events,
    simulate_sell,
)
from app.services.transaction import get_transactions

router = APIRouter(prefix="/tax", tags=["tax"])

_ALL = 10_000


def _report_to_out(r: AnnualTaxReport) -> AnnualTaxReportOut:
    return AnnualTaxReportOut(
        year=r.year,
        gains_standard=r.gains_standard,
        losses_standard=r.losses_standard,
        carryforward_applied_standard=r.carryforward_applied_standard,
        net_taxable_standard=r.net_taxable_standard,
        tax_standard=r.tax_standard,
        gains_govt=r.gains_govt,
        losses_govt=r.losses_govt,
        carryforward_applied_govt=r.carryforward_applied_govt,
        net_taxable_govt=r.net_taxable_govt,
        tax_govt=r.tax_govt,
        dividends_eur=r.dividends_eur,
        coupons_govt_eur=r.coupons_govt_eur,
        coupons_standard_eur=r.coupons_standard_eur,
        interests_eur=r.interests_eur,
        total_tax_due=r.total_tax_due,
        new_carryforward_standard=r.new_carryforward_standard,
        new_carryforward_govt=r.new_carryforward_govt,
        prior_carryforward_standard=[
            CarryForwardEntryOut(year=e.year, amount=e.amount, expires_year=e.expires_year)
            for e in r.prior_carryforward_standard
        ],
        prior_carryforward_govt=[
            CarryForwardEntryOut(year=e.year, amount=e.amount, expires_year=e.expires_year)
            for e in r.prior_carryforward_govt
        ],
        events=[
            TaxEventOut(
                date=e.date,
                asset_id=e.asset_id,
                asset_name=e.asset_name,
                asset_type=e.asset_type,
                tx_type=e.tx_type,
                quantity=e.quantity,
                proceeds_eur=e.proceeds_eur,
                cost_eur=e.cost_eur,
                gain_loss_eur=e.gain_loss_eur,
                tax_bracket=e.tax_bracket,
                tax_rate=e.tax_rate,
            )
            for e in r.events
        ],
    )


@router.get("/report", response_model=AnnualTaxReportOut)
async def get_tax_report(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report fiscale per l'anno richiesto, con zainetto fiscale cumulativo."""
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    events = compute_tax_events(transactions)
    reports = build_annual_reports(events)

    for r in reports:
        if r.year == year:
            return _report_to_out(r)

    # Anno senza eventi fiscali
    return AnnualTaxReportOut(
        year=year,
        gains_standard=0, losses_standard=0,
        carryforward_applied_standard=0, net_taxable_standard=0, tax_standard=0,
        gains_govt=0, losses_govt=0,
        carryforward_applied_govt=0, net_taxable_govt=0, tax_govt=0,
        dividends_eur=0, coupons_govt_eur=0, coupons_standard_eur=0, interests_eur=0,
        total_tax_due=0,
        new_carryforward_standard=0, new_carryforward_govt=0,
        prior_carryforward_standard=[], prior_carryforward_govt=[],
        events=[],
    )


@router.get("/years", response_model=list[int])
async def get_tax_years(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista degli anni con eventi fiscali (vendite, dividendi, cedole)."""
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    events = compute_tax_events(transactions)
    years = sorted({e.date.year for e in events}, reverse=True)
    return years


@router.get("/simulate", response_model=SimulateSellOut)
async def simulate_sell_endpoint(
    asset_id: int = Query(...),
    quantity: float = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stima l'impatto fiscale di una vendita ipotetica (usa i lotti FIFO aperti)."""
    result = await db.get(Asset, asset_id)
    if not result:
        raise HTTPException(404, "Asset non trovato")
    asset: Asset = result

    # Prezzo corrente in EUR
    cached = await get_cached_price(asset_id)
    if cached is None:
        try:
            cached = await refresh_asset_price(db, asset)
        except Exception:
            pass
    if cached is None:
        raise HTTPException(503, "Prezzo non disponibile")

    price_eur = cached.get("price", 0.0) * cached.get("exchange_rate", 1.0)

    # Lotti FIFO dell'utente per questo asset
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    positions = calculate_positions(transactions)
    pos = positions.get(asset_id)
    if pos is None or pos.quantity < quantity:
        raise HTTPException(400, "Quantità disponibile insufficiente")

    result_data = simulate_sell(asset, quantity, price_eur, pos.lots)
    return SimulateSellOut(**result_data)
