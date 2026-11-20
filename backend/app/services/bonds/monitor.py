"""
Monitoraggio della convenienza a vendere un'obbligazione prima della scadenza.

Confronta, **al netto delle imposte**, due strade per la posizione attuale:

  vendi ora        = Q·(P + rateo)  − imposta sulla plusvalenza di capitale
                                     − imposta sul rateo
  tieni a scadenza = Q·F (rimborso) − imposta sull'eventuale guadagno a scadenza
                     + cedole future nette

Le cedole già incassate (nette) contano uguale nei due casi e sono mostrate nel
guadagno totale. ``advantage = vendi − tieni``: se positivo, vendere ora rende
più che tenere il titolo fino a scadenza. ``break_even_price`` è il prezzo al
quale le due strade coincidono.

Convenzioni: Q = quote, F = nominale per quota (di solito 100), P = corso secco per quota; imposta = ``tax_rate`` (12,5% titoli di
Stato, 26% altre obbligazioni) solo su guadagni positivi; nessuna attualizzazione,
nessuna commissione di vendita, nessuna compensazione con minusvalenze.
"""
from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field

from dateutil.relativedelta import relativedelta


@dataclass
class BondEvaluation:
    status: str = "ok"                    # "ok" | "missing_data"
    reason: str | None = None             # motivo se missing_data
    should_sell: bool = False
    advantage_eur: float = 0.0            # netto vendi ora − netto tieni a scadenza
    break_even_price: float | None = None
    # input
    quantity: float = 0.0
    avg_cost: float = 0.0                 # PMC per quota
    price: float = 0.0                    # corso secco per quota
    face_value: float = 100.0
    accrued_per_unit: float = 0.0
    tax_rate: float = 0.0
    maturity_date: datetime.date | None = None
    future_coupons: int = 0
    # componenti (totali sulla posizione)
    cost_eur: float = 0.0
    collected_coupons_gross_eur: float = 0.0
    collected_coupons_net_eur: float = 0.0
    sell_gross_eur: float = 0.0           # Q·(P + rateo)
    sell_tax_eur: float = 0.0
    sell_net_eur: float = 0.0
    hold_redemption_eur: float = 0.0      # Q·F
    hold_future_coupons_gross_eur: float = 0.0
    hold_tax_eur: float = 0.0             # imposta su guadagno a scadenza + su cedole future
    hold_net_eur: float = 0.0
    # guadagno totale = netto incassato + cedole già incassate − costo
    total_gain_sell_eur: float = 0.0
    total_gain_hold_eur: float = 0.0
    total_gain_sell_gross_eur: float = 0.0
    total_gain_hold_gross_eur: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["maturity_date"] = self.maturity_date.isoformat() if self.maturity_date else None
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def missing(reason: str) -> BondEvaluation:
    return BondEvaluation(status="missing_data", reason=reason)


def accrued_per_unit(coupon_per_unit: float, prev_coupon: datetime.date, next_coupon: datetime.date,
                     today: datetime.date) -> float:
    """Rateo maturato (actual/actual sul periodo di cedola in corso)."""
    period = (next_coupon - prev_coupon).days
    if period <= 0:
        return 0.0
    days = min(max((today - prev_coupon).days, 0), period)
    return coupon_per_unit * days / period


def break_even_price(quantity: float, avg_cost: float, accrued: float, tax_rate: float, hold_net: float) -> float:
    """Prezzo (corso secco) per cui vendere ora equivale a tenere a scadenza."""
    t, c = tax_rate, avg_cost
    h = hold_net / quantity
    with_gain = (h - t * c - (1 - t) * accrued) / (1 - t)      # prezzo > costo: la plusvalenza è tassata
    if with_gain > c:
        return with_gain
    return h - (1 - t) * accrued                                # prezzo ≤ costo: nessuna imposta di capitale


def evaluate_bond(
    *,
    quantity: float,
    avg_cost: float,
    price: float,
    face_value: float,
    coupon_per_unit: float,
    future_coupon_dates: list[datetime.date],
    prev_coupon_date: datetime.date | None,
    collected_coupons_gross: float,
    tax_rate: float,
    maturity_date: datetime.date | None,
    today: datetime.date | None = None,
) -> BondEvaluation:
    today = today or datetime.date.today()
    if quantity <= 1e-9:
        return missing("Nessuna posizione aperta su questo titolo.")
    if maturity_date is None:
        return missing("Scadenza del titolo non configurata.")
    if maturity_date <= today:
        return missing("Il titolo è scaduto.")
    if coupon_per_unit <= 0:
        return missing("Cedole non configurate per questo titolo.")
    if not price or price <= 0:
        return missing("Prezzo corrente non disponibile.")

    q, c, p, f, t = quantity, avg_cost, price, face_value, tax_rate
    next_coupon = future_coupon_dates[0] if future_coupon_dates else None
    accr = (accrued_per_unit(coupon_per_unit, prev_coupon_date, next_coupon, today)
            if next_coupon and prev_coupon_date else 0.0)

    cost = q * c
    coll_net = collected_coupons_gross * (1 - t)

    sell_gross = q * (p + accr)
    sell_tax = t * max(0.0, q * (p - c)) + t * q * accr
    sell_net = sell_gross - sell_tax

    n = len(future_coupon_dates)
    future_gross = q * coupon_per_unit * n
    hold_tax = t * max(0.0, q * (f - c)) + t * future_gross
    hold_net = q * f + future_gross - hold_tax

    advantage = sell_net - hold_net
    return BondEvaluation(
        status="ok", should_sell=advantage > 0, advantage_eur=advantage,
        break_even_price=break_even_price(q, c, accr, t, hold_net),
        quantity=q, avg_cost=c, price=p, face_value=f, accrued_per_unit=accr, tax_rate=t,
        maturity_date=maturity_date, future_coupons=n,
        cost_eur=cost, collected_coupons_gross_eur=collected_coupons_gross, collected_coupons_net_eur=coll_net,
        sell_gross_eur=sell_gross, sell_tax_eur=sell_tax, sell_net_eur=sell_net,
        hold_redemption_eur=q * f, hold_future_coupons_gross_eur=future_gross, hold_tax_eur=hold_tax,
        hold_net_eur=hold_net,
        total_gain_sell_eur=sell_net + coll_net - cost, total_gain_hold_eur=hold_net + coll_net - cost,
        total_gain_sell_gross_eur=sell_gross + collected_coupons_gross - cost,
        total_gain_hold_gross_eur=q * f + future_gross + collected_coupons_gross - cost,
    )


# ── Caricamento dei dati dell'utente ─────────────────────────────────────────

async def _current_price(db, asset) -> float | None:
    """Prezzo in EUR: cache Redis, altrimenti ultima chiusura in price_history."""
    import math

    from sqlalchemy import select

    from app.models.asset import PriceHistory
    from app.services.market_data.updater import get_cached_price

    try:
        cached = await get_cached_price(asset.id)
    except Exception:
        cached = None
    if cached and cached.get("price"):
        return float(cached["price"]) * float(cached.get("exchange_rate", 1.0))
    rows = (await db.execute(
        select(PriceHistory.close).where(PriceHistory.asset_id == asset.id).order_by(PriceHistory.date.desc()).limit(5)
    )).scalars().all()
    return next((float(c) for c in rows if c and not math.isnan(c)), None)


async def evaluate_for_user(db, user_id: int, asset_id: int, today: datetime.date | None = None) -> BondEvaluation:
    """Valuta la posizione dell'utente su un'obbligazione (tutte le fonti già lette da DB e cache)."""
    from sqlalchemy import select

    from app.models.asset import Asset
    from app.models.bond_detail import BondDetail, CouponFrequency
    from app.models.transaction import TransactionType
    from app.services.bonds.coupon_schedule import generate_coupon_dates
    from app.services.portfolio.positions import calculate_positions
    from app.services.tax.calculator import CATEGORY_GOVT, RATE_GOVT, RATE_STANDARD, tax_category
    from app.services.transaction import get_transactions

    today = today or datetime.date.today()
    asset = await db.get(Asset, asset_id)
    if not asset:
        return missing("Titolo non trovato.")
    if (asset.type if isinstance(asset.type, str) else asset.type.value) != "BOND":
        return missing("Il monitoraggio è disponibile solo per le obbligazioni.")

    txs = [t for t in await get_transactions(db, user_id, limit=10_000) if t.asset_id == asset_id]
    pos = calculate_positions(txs).get(asset_id)
    bond = (await db.execute(select(BondDetail).where(BondDetail.asset_id == asset_id))).scalar_one_or_none()
    if bond is None:
        return missing("Cedole non configurate per questo titolo.")

    collected = sum(t.quantity * t.price * t.exchange_rate - t.fee for t in txs if t.type == TransactionType.COUPON)
    future = generate_coupon_dates(bond, today + datetime.timedelta(days=1), bond.maturity_date) if bond.maturity_date else []
    prev = (future[0] - relativedelta(months=CouponFrequency(bond.coupon_frequency).months_between)) if future else None
    rate = RATE_GOVT if tax_category(asset) == CATEGORY_GOVT else RATE_STANDARD
    price = await _current_price(db, asset)

    return evaluate_bond(
        quantity=pos.quantity if pos else 0.0, avg_cost=pos.pmc_eur if pos else 0.0, price=price or 0.0,
        face_value=bond.face_value, coupon_per_unit=bond.coupon_per_unit, future_coupon_dates=future,
        prev_coupon_date=prev, collected_coupons_gross=collected, tax_rate=rate,
        maturity_date=bond.maturity_date, today=today,
    )


# ── Macchina a stati dell'avviso email ───────────────────────────────────────

def next_notification_state(should_sell: bool, active: bool) -> tuple[bool, bool]:
    """(invia_email, nuovo_active).

    Una sola email quando vendere diventa conveniente; si riarma solo se la
    condizione smette di valere (controllo giornaliero) e poi si ripresenta.
    """
    if should_sell and not active:
        return True, True
    if should_sell and active:
        return False, True
    return False, False
