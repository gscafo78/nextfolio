"""
Snapshot del portafoglio: posizioni aperte, prezzi correnti, liquidità e
allocazione, con filtri opzionali per conto e tipo di asset.

Condiviso dal report AI/MCP (``services/ai/context.py``) e dalla pagina
Pianifica (simulazioni, versamento, fisco).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.portfolio import AllocationOut
from app.services.cash import latest_balances
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.classification import build_asset_info
from app.services.portfolio.positions import calculate_positions, realized_and_income
from app.services.transaction import get_transactions

_ALL = 10_000


def _enum(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


@dataclass
class Holding:
    asset: Asset
    quantity: float
    pmc_eur: float
    invested_eur: float
    realized_pnl_eur: float
    price: float | None
    price_eur: float | None
    value_eur: float | None
    unrealized_eur: float | None
    unrealized_pct: float | None
    change_pct: float | None
    weight_pct: float | None = None


@dataclass
class Snapshot:
    transactions: list[Transaction]
    holdings: list[Holding]
    accounts: list[Account]
    account_values: dict[str, float]
    allocation: AllocationOut
    realized_pnl_eur: float
    total_value_eur: float
    total_invested_eur: float
    income_eur: float = 0.0          # proventi netti (cedole, dividendi, interessi − costi)
    net_contributed_eur: float = 0.0  # acquisti − vendite (capitale netto versato)
    cash: list = field(default_factory=list)   # list[CashBalance]
    # Dati grezzi per ricalcoli (simulazioni)
    positions: dict = field(default_factory=dict)    # {asset_id: PositionCalc}
    asset_info: dict = field(default_factory=dict)   # {asset_id: build_asset_info}
    price_eur: dict = field(default_factory=dict)    # {asset_id: prezzo EUR}
    filters: dict = field(default_factory=dict)


async def load_snapshot(
    db: AsyncSession,
    user: User,
    *,
    account_id: int | None = None,
    asset_type: str | None = None,
) -> Snapshot:
    """Calcola posizioni aperte, prezzi correnti e allocazione (filtrabili)."""
    # Import locale: evita import circolare endpoint ↔ servizi
    from app.api.v1.endpoints.portfolio import _fetch_prices_parallel

    txs = await get_transactions(db, user.id, account_id=account_id, limit=_ALL)
    if asset_type:
        txs = [t for t in txs if _enum(t.asset.type) == asset_type]

    positions = calculate_positions(txs)
    realized, income = realized_and_income(txs)
    net_contributed = sum(
        (t.quantity * t.price * t.exchange_rate + t.fee) if t.type == TransactionType.BUY
        else -(t.quantity * t.price * t.exchange_rate - t.fee)
        for t in txs if t.type in (TransactionType.BUY, TransactionType.SELL)
    )

    res = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    asset_map = {a.id: a for a in res.scalars()}
    price_map = await _fetch_prices_parallel(db, asset_map) if asset_map else {}

    holdings: list[Holding] = []
    price_eur: dict[int, float] = {}
    for aid, pos in positions.items():
        asset = asset_map.get(aid)
        if not asset:
            continue
        data = price_map.get(aid) or {}
        price = data.get("price")
        fx = data.get("exchange_rate", 1.0)
        peur = price * fx if price is not None else None
        if peur is not None:
            price_eur[aid] = peur
        value = pos.quantity * peur if peur is not None else None
        cost = pos.quantity * pos.pmc_eur
        unreal = value - cost if value is not None else None
        holdings.append(Holding(
            asset=asset,
            quantity=pos.quantity,
            pmc_eur=pos.pmc_eur,
            invested_eur=cost,
            realized_pnl_eur=pos.realized_pnl_eur,
            price=price,
            price_eur=peur,
            value_eur=value,
            unrealized_eur=unreal,
            unrealized_pct=(unreal / cost * 100) if unreal is not None and cost > 0 else None,
            change_pct=data.get("change_pct"),
        ))

    total_value = sum(h.value_eur or 0 for h in holdings)
    for h in holdings:
        h.weight_pct = (h.value_eur / total_value * 100) if h.value_eur and total_value > 0 else None
    holdings.sort(key=lambda h: h.value_eur or 0, reverse=True)

    acc_res = await db.execute(select(Account).where(Account.user_id == user.id).order_by(Account.name))
    accounts = list(acc_res.scalars())
    account_values: dict[str, float] = {}
    for acc in accounts:
        acc_pos = calculate_positions([t for t in txs if t.account_id == acc.id])
        v = sum(p.quantity * price_eur[a] for a, p in acc_pos.items() if a in price_eur)
        if v > 0:
            account_values[acc.name] = v

    asset_info = {a.id: build_asset_info(a) for a in asset_map.values()}
    # Liquidità: solo senza filtro per tipo di asset (non è uno strumento)
    cash = [] if asset_type else await latest_balances(db, user.id, account_id=account_id)
    allocation = calculate_allocation(positions, asset_info, price_eur, account_values, cash=cash)

    return Snapshot(
        cash=cash,
        positions=positions,
        asset_info=asset_info,
        price_eur=price_eur,
        transactions=txs,
        holdings=holdings,
        accounts=accounts,
        account_values=account_values,
        allocation=allocation,
        realized_pnl_eur=realized,
        total_value_eur=total_value,
        total_invested_eur=sum(h.invested_eur for h in holdings),
        income_eur=income,
        net_contributed_eur=net_contributed,
        filters={"account_id": account_id, "asset_type": asset_type},
    )
