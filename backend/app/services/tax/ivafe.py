"""
IVAFE — Imposta sul Valore delle Attività Finanziarie Estere

Aliquota: 0,2% sul valore di mercato al 31 dicembre dell'anno di imposta.
Si applica alle attività detenute presso intermediari esteri
(conti con is_foreign=True).

Semplificazioni MVP:
- Il prezzo usato è il close più recente in price_history ≤ 31/12
- Il tasso di cambio è quello dell'ultima transazione BUY/SELL prima del 31/12
  (approssimazione ragionevole per valori annuali)
- IVAFE non si applica a conti amministrati italiani
"""
import datetime
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import PriceHistory
from app.models.transaction import Transaction, TransactionType

IVAFE_RATE = 0.002  # 0,2%


@dataclass
class IVAFEPosition:
    asset_id: int
    asset_name: str
    asset_type: str
    quantity: float
    price_eur: float
    market_value_eur: float
    ivafe_eur: float
    price_date: datetime.date | None


@dataclass
class IVAFEReport:
    year: int
    total_market_value_eur: float = 0.0
    ivafe_eur: float = 0.0
    positions: list[IVAFEPosition] = field(default_factory=list)
    rate: float = IVAFE_RATE
    has_foreign_accounts: bool = False


async def compute_ivafe(
    db: AsyncSession,
    transactions: list[Transaction],
    year: int,
) -> IVAFEReport:
    """
    Calcola l'IVAFE per l'anno dato considerando solo i conti con is_foreign=True.
    """
    year_end = datetime.date(year, 12, 31)

    # Accumula quantità nette e tasso di cambio per (account_id, asset_id)
    # struttura: {asset_id: {qty, last_exchange_rate, asset}}
    # Aggrega per asset (somma di tutti i conti esteri)
    asset_data: dict[int, dict] = {}
    has_foreign = False

    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        if tx.date > year_end:
            continue
        if not getattr(tx.account, "is_foreign", False):
            continue

        has_foreign = True
        aid = tx.asset_id

        if aid not in asset_data:
            asset_data[aid] = {
                "qty": 0.0,
                "last_exchange_rate": 1.0,
                "asset": tx.asset,
            }

        d = asset_data[aid]
        if tx.type == TransactionType.BUY:
            d["qty"] += tx.quantity
            d["last_exchange_rate"] = tx.exchange_rate
        elif tx.type == TransactionType.SELL:
            d["qty"] -= tx.quantity
            d["last_exchange_rate"] = tx.exchange_rate

    report = IVAFEReport(year=year, has_foreign_accounts=has_foreign)

    open_positions = {aid: d for aid, d in asset_data.items() if d["qty"] > 1e-10}
    if not open_positions:
        return report

    for asset_id, data in open_positions.items():
        asset = data["asset"]
        qty = data["qty"]
        exchange_rate = data["last_exchange_rate"]

        row = (await db.execute(
            select(PriceHistory.close, PriceHistory.date)
            .where(
                PriceHistory.asset_id == asset_id,
                PriceHistory.date <= year_end,
            )
            .order_by(PriceHistory.date.desc())
            .limit(1)
        )).first()

        if row is None:
            continue

        close_price, price_date = row
        price_eur = close_price * exchange_rate
        market_value_eur = round(qty * price_eur, 2)
        ivafe_eur = round(market_value_eur * IVAFE_RATE, 2)

        report.positions.append(IVAFEPosition(
            asset_id=asset_id,
            asset_name=asset.name,
            asset_type=asset.type if isinstance(asset.type, str) else asset.type.value,
            quantity=qty,
            price_eur=round(price_eur, 4),
            market_value_eur=market_value_eur,
            ivafe_eur=ivafe_eur,
            price_date=price_date,
        ))
        report.total_market_value_eur += market_value_eur
        report.ivafe_eur += ivafe_eur

    report.total_market_value_eur = round(report.total_market_value_eur, 2)
    report.ivafe_eur = round(report.ivafe_eur, 2)
    return report
