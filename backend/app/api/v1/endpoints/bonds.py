"""
Endpoint per la gestione delle cedole obbligazionarie.

Routes:
  GET    /assets/{id}/bond-detail          — dettagli cedola per l'asset
  POST   /assets/{id}/bond-detail          — crea/aggiorna (upsert)
  GET    /assets/{id}/bond-detail/enrich   — enrichment automatico da Borsa Italiana
  GET    /assets/{id}/coupon-schedule      — calendario cedole future
  GET    /portfolio/upcoming-coupons       — cedole in arrivo per tutto il portafoglio
  POST   /bonds/backfill-coupons           — inserisce le cedole storiche mancanti
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset, AssetType
from app.models.bond_detail import BondDetail, CouponFrequency
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.bond import (
    BondDetailCreate, BondDetailOut, BondEnrichmentResult,
    CouponScheduleEntry, UpcomingCouponEntry,
)
from app.services.bonds.bi_enrichment import fetch_bond_details
from app.services.bonds.coupon_schedule import generate_coupon_dates, coupon_per_unit
from app.services.portfolio.positions import calculate_positions
from app.services.transaction import get_transactions

router = APIRouter(tags=["bonds"])

_ALL = 10_000


async def _get_asset_for_user(db: AsyncSession, asset_id: int, user_id: int) -> Asset:
    """Verifica che l'asset esista e che l'utente abbia almeno una transazione su di esso."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    return asset


async def _get_bond_detail(db: AsyncSession, asset_id: int) -> BondDetail | None:
    result = await db.execute(
        select(BondDetail).where(BondDetail.asset_id == asset_id)
    )
    return result.scalar_one_or_none()


# ── GET bond-detail ───────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/bond-detail", response_model=BondDetailOut)
async def get_bond_detail(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bd = await _get_bond_detail(db, asset_id)
    if not bd:
        raise HTTPException(404, "Dettagli cedola non trovati per questo asset")
    return bd


# ── POST bond-detail (upsert) ─────────────────────────────────────────────────

@router.post("/assets/{asset_id}/bond-detail", response_model=BondDetailOut)
async def upsert_bond_detail(
    asset_id: int,
    data: BondDetailCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    if asset.type != AssetType.BOND:
        raise HTTPException(400, "I dettagli cedola sono disponibili solo per asset di tipo BOND")

    bd = await _get_bond_detail(db, asset_id)
    if bd is None:
        bd = BondDetail(asset_id=asset_id)
        db.add(bd)

    bd.face_value = data.face_value
    bd.coupon_rate = data.coupon_rate
    bd.coupon_frequency = data.coupon_frequency
    bd.first_coupon_date = data.first_coupon_date
    bd.maturity_date = data.maturity_date
    bd.issue_date = data.issue_date
    bd.enriched_from_bi = False

    await db.commit()
    await db.refresh(bd)
    return bd


# ── Enrichment automatico da Borsa Italiana ───────────────────────────────────

@router.get("/assets/{asset_id}/bond-detail/enrich", response_model=BondEnrichmentResult)
async def enrich_bond_detail(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset non trovato")
    if asset.type != AssetType.BOND:
        raise HTTPException(400, "Enrichment disponibile solo per asset di tipo BOND")
    if not asset.isin:
        raise HTTPException(400, "L'asset non ha un ISIN — enrichment non possibile")

    result = await fetch_bond_details(asset.isin)
    if not result:
        raise HTTPException(
            503,
            "Impossibile recuperare i dati da Borsa Italiana. "
            "Verifica che l'ISIN sia un BTP/BOT/CCT quotato su MOT, o inserisci i dati manualmente."
        )

    bd = await _get_bond_detail(db, asset_id)
    if bd is None:
        bd = BondDetail(asset_id=asset_id)
        db.add(bd)

    bd.face_value = result.face_value
    bd.coupon_rate = result.coupon_rate
    bd.coupon_frequency = result.coupon_frequency
    bd.first_coupon_date = result.first_coupon_date
    bd.maturity_date = result.maturity_date
    bd.issue_date = result.issue_date
    bd.enriched_from_bi = True

    await db.commit()
    await db.refresh(bd)

    return BondEnrichmentResult(asset_id=asset_id, bond_detail=BondDetailOut.model_validate(bd))


# ── Calendario cedole ─────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/coupon-schedule", response_model=list[CouponScheduleEntry])
async def get_coupon_schedule(
    asset_id: int,
    from_date: date = Query(default_factory=date.today),
    to_date: date | None = Query(None),
    quantity: float = Query(1.0, gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bd = await _get_bond_detail(db, asset_id)
    if not bd:
        raise HTTPException(404, "Dettagli cedola non trovati")

    end = to_date or (bd.maturity_date or from_date + timedelta(days=365 * 10))
    dates = generate_coupon_dates(bd, from_date, end)
    cpu = coupon_per_unit(bd)
    today = date.today()

    # Trova le date già registrate come COUPON
    tx_result = await db.execute(
        select(Transaction.date)
        .join(Transaction.account)
        .where(
            Transaction.account.has(user_id=current_user.id),
            Transaction.asset_id == asset_id,
            Transaction.type == TransactionType.COUPON,
        )
    )
    recorded = {r[0] for r in tx_result.all()}

    return [
        CouponScheduleEntry(
            date=d,
            coupon_per_unit=cpu,
            total_coupon_eur=round(quantity * cpu, 2),
            days_until=(d - today).days,
            already_recorded=any(abs((d - r).days) <= 5 for r in recorded),
        )
        for d in dates
    ]


# ── Cedole in arrivo per tutto il portafoglio ─────────────────────────────────

@router.get("/portfolio/upcoming-coupons", response_model=list[UpcomingCouponEntry])
async def get_upcoming_coupons(
    days: int = Query(365, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restituisce tutte le cedole in arrivo (entro `days` giorni) per i BTP/obbligazioni
    dell'utente che hanno bond_details configurati.
    """
    today = date.today()
    to_date = today + timedelta(days=days)

    # Tutte le transazioni utente (con asset e bond_detail)
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    positions = calculate_positions(transactions)

    # Asset IDs con posizioni aperte
    open_asset_ids = {aid for aid, pos in positions.items() if pos.quantity > 1e-10}

    # Carica asset con bond_detail per le posizioni aperte
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.bond_detail))
        .where(
            Asset.id.in_(open_asset_ids),
            Asset.type == AssetType.BOND,
        )
    )
    bond_assets = [a for a in result.scalars() if a.bond_detail is not None]

    # Transazioni COUPON già registrate per l'utente
    coupon_result = await db.execute(
        select(Transaction.asset_id, Transaction.date)
        .join(Transaction.account)
        .where(
            Transaction.account.has(user_id=current_user.id),
            Transaction.type == TransactionType.COUPON,
        )
    )
    recorded_by_asset: dict[int, set[date]] = {}
    for asset_id, tx_date in coupon_result.all():
        recorded_by_asset.setdefault(asset_id, set()).add(tx_date)

    entries: list[UpcomingCouponEntry] = []

    for asset in bond_assets:
        bd = asset.bond_detail
        pos = positions.get(asset.id)
        if not pos:
            continue

        qty = pos.quantity
        cpu = bd.coupon_per_unit
        dates = generate_coupon_dates(bd, today - timedelta(days=5), to_date)
        recorded = recorded_by_asset.get(asset.id, set())

        for d in dates:
            already = any(abs((d - r).days) <= 5 for r in recorded)
            entries.append(UpcomingCouponEntry(
                asset_id=asset.id,
                asset_name=asset.name,
                isin=asset.isin,
                date=d,
                coupon_per_unit=cpu,
                quantity=qty,
                total_coupon_eur=round(qty * cpu, 2),
                days_until=(d - today).days,
                already_recorded=already,
            ))

    entries.sort(key=lambda e: e.date)
    return entries


# ── Backfill cedole storiche ──────────────────────────────────────────────────

from pydantic import BaseModel

class BackfillResult(BaseModel):
    asset_id: int
    asset_name: str
    isin: str | None
    coupon_date: date
    quantity: float
    amount_eur: float
    account_id: int
    created: bool
    skipped_reason: str | None = None

class BackfillSummary(BaseModel):
    created_count: int
    skipped_count: int
    total_amount_eur: float
    details: list[BackfillResult]


def _qty_at_date(transactions: list[Transaction], asset_id: int, as_of: date) -> float:
    """Quantità netta detenuta per asset_id alla data as_of (BUY - SELL)."""
    qty = 0.0
    for tx in transactions:
        if tx.asset_id != asset_id or tx.date > as_of:
            continue
        if tx.type == TransactionType.BUY:
            qty += tx.quantity
        elif tx.type == TransactionType.SELL:
            qty -= tx.quantity
    return max(0.0, qty)


def _account_at_date(transactions: list[Transaction], asset_id: int, as_of: date) -> int | None:
    """Conto dell'ultimo acquisto per asset_id fino ad as_of."""
    last = None
    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        if tx.asset_id == asset_id and tx.type == TransactionType.BUY and tx.date <= as_of:
            last = tx.account_id
    return last


@router.post("/bonds/backfill-coupons", response_model=BackfillSummary)
async def backfill_coupons(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Inserisce le transazioni COUPON mancanti dal passato fino a oggi
    per tutti i BTP/obbligazioni con bond_detail configurato.

    Per ogni cedola storica:
    - Calcola la quantità detenuta ALLA DATA della cedola (non quella attuale)
    - Usa il conto dell'ultimo acquisto prima di quella data
    - Salta se la transazione COUPON esiste già (confronto ±5 giorni)
    """
    today = date.today()
    transactions = await get_transactions(db, current_user.id, limit=_ALL)

    # Asset BOND con bond_detail
    open_asset_ids = {tx.asset_id for tx in transactions}
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.bond_detail))
        .where(
            Asset.id.in_(open_asset_ids),
            Asset.type == AssetType.BOND,
        )
    )
    bond_assets = [a for a in result.scalars() if a.bond_detail is not None]

    # Transazioni COUPON già esistenti per l'utente
    coupon_result = await db.execute(
        select(Transaction.asset_id, Transaction.date)
        .join(Transaction.account)
        .where(
            Transaction.account.has(user_id=current_user.id),
            Transaction.type == TransactionType.COUPON,
        )
    )
    existing_coupons: dict[int, list[date]] = {}
    for aid, cdate in coupon_result.all():
        existing_coupons.setdefault(aid, []).append(cdate)

    details: list[BackfillResult] = []

    for asset in bond_assets:
        bd = asset.bond_detail
        # Genera tutte le date cedola dal primo coupon a oggi
        past_dates = generate_coupon_dates(bd, bd.first_coupon_date, today)

        for cdate in past_dates:
            # Quantità detenuta a quella data
            qty = _qty_at_date(transactions, asset.id, cdate)
            if qty < 1e-10:
                details.append(BackfillResult(
                    asset_id=asset.id, asset_name=asset.name, isin=asset.isin,
                    coupon_date=cdate, quantity=0, amount_eur=0, account_id=0,
                    created=False, skipped_reason="Nessuna posizione aperta a quella data",
                ))
                continue

            # Conto dell'ultimo BUY prima della cedola
            acc_id = _account_at_date(transactions, asset.id, cdate)
            if acc_id is None:
                details.append(BackfillResult(
                    asset_id=asset.id, asset_name=asset.name, isin=asset.isin,
                    coupon_date=cdate, quantity=qty, amount_eur=0, account_id=0,
                    created=False, skipped_reason="Nessun conto trovato",
                ))
                continue

            # Controlla se esiste già (±5 giorni)
            existing = existing_coupons.get(asset.id, [])
            already = any(abs((cdate - ex).days) <= 5 for ex in existing)
            cpu = bd.coupon_per_unit
            amount = round(qty * cpu, 2)

            if already:
                details.append(BackfillResult(
                    asset_id=asset.id, asset_name=asset.name, isin=asset.isin,
                    coupon_date=cdate, quantity=qty, amount_eur=amount, account_id=acc_id,
                    created=False, skipped_reason="Già registrata",
                ))
                continue

            # Crea la transazione COUPON
            tx = Transaction(
                account_id=acc_id,
                asset_id=asset.id,
                type=TransactionType.COUPON,
                date=cdate,
                quantity=qty,
                price=cpu,
                exchange_rate=1.0,
                fee=0.0,
                price_currency="EUR",
                fee_currency="EUR",
            )
            db.add(tx)
            existing_coupons.setdefault(asset.id, []).append(cdate)  # idempotenza in-memory

            details.append(BackfillResult(
                asset_id=asset.id, asset_name=asset.name, isin=asset.isin,
                coupon_date=cdate, quantity=qty, amount_eur=amount, account_id=acc_id,
                created=True,
            ))

    await db.commit()

    created = [d for d in details if d.created]
    skipped = [d for d in details if not d.created]
    return BackfillSummary(
        created_count=len(created),
        skipped_count=len(skipped),
        total_amount_eur=round(sum(d.amount_eur for d in created), 2),
        details=details,
    )
