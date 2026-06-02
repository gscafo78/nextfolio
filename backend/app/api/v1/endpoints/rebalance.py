"""Suggerisce buy/sell per riallineare il portafoglio a un'allocazione target per asset class."""
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset
from app.models.user import User
from app.services.portfolio.allocation import TYPE_LABELS
from app.services.portfolio.positions import calculate_positions

router = APIRouter(prefix="/portfolio", tags=["rebalance"])

# Mappa label allocazione → tipi asset appartenenti a quel gruppo
_GROUP_TYPES: dict[str, list[str]] = {
    "Azioni":       ["STOCK", "ETF", "REIT"],
    "Obbligazioni": ["BOND"],
    "Crypto":       ["CRYPTO"],
    "Altro":        ["COMMODITY"],
}


class RebalanceTarget(BaseModel):
    label: str    # es. "Azioni", "Obbligazioni", "Crypto", "Altro"
    pct: float    # percentuale target 0–100


class RebalanceRequest(BaseModel):
    targets: list[RebalanceTarget]
    cash_available: float = 0.0


class RebalanceSuggestion(BaseModel):
    asset_id: int
    symbol: str
    name: str
    action: str          # "buy" | "sell"
    amount_eur: float    # importo suggerito in EUR
    current_pct: float   # allocazione attuale %
    target_pct: float    # allocazione target %
    delta_pct: float     # differenza target - current


@router.post("/rebalance", response_model=list[RebalanceSuggestion])
async def rebalance(
    body: RebalanceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calcola i trade suggeriti (buy/sell per asset) per raggiungere l'allocazione target.
    I target in `targets` devono sommare a 100. Le posizioni aperte vengono raggruppate
    per asset class; il delta (target - current) determina buy o sell.
    """
    from app.api.v1.endpoints.portfolio import _load_all_transactions, _fetch_prices_parallel

    transactions = await _load_all_transactions(db, current_user.id)
    positions = calculate_positions(transactions)
    if not positions:
        return []

    result = await db.execute(select(Asset).where(Asset.id.in_(list(positions.keys()))))
    asset_map = {a.id: a for a in result.scalars()}
    price_map = await _fetch_prices_parallel(db, asset_map, background_tasks)

    # Prezzi e valori correnti
    price_eur: dict[int, float] = {}
    for aid in positions:
        data = price_map.get(aid)
        if data and data.get("price") is not None:
            price_eur[aid] = data["price"] * data.get("exchange_rate", 1.0)

    total_value = sum(
        positions[aid].quantity * price_eur[aid]
        for aid in positions if aid in price_eur
    )
    investable = total_value + body.cash_available
    if investable <= 0:
        return []

    # Valori correnti per asset class
    group_value_current: dict[str, float] = {g: 0.0 for g in _GROUP_TYPES}
    asset_to_group: dict[int, str] = {}
    for aid, pos in positions.items():
        asset = asset_map.get(aid)
        if not asset or aid not in price_eur:
            continue
        raw_type = asset.type if isinstance(asset.type, str) else asset.type.value
        group = next((g for g, types in _GROUP_TYPES.items() if raw_type in types), "Altro")
        asset_to_group[aid] = group
        group_value_current[group] = group_value_current.get(group, 0) + positions[aid].quantity * price_eur[aid]

    # Target per gruppo
    target_map = {t.label: t.pct / 100 for t in body.targets}

    suggestions: list[RebalanceSuggestion] = []

    for aid, pos in positions.items():
        asset = asset_map.get(aid)
        if not asset or aid not in price_eur:
            continue

        group = asset_to_group.get(aid, "Altro")
        current_value = pos.quantity * price_eur[aid]
        current_pct = (current_value / investable) * 100

        target_group_pct = target_map.get(group, 0.0)
        group_current_pct = (group_value_current.get(group, 0) / investable) * 100

        delta_group = target_group_pct * 100 - group_current_pct  # delta % del gruppo

        if abs(delta_group) < 1.0:
            continue  # differenza < 1% → non suggerire

        # Distribuisce il delta del gruppo proporzionalmente alla posizione all'interno del gruppo
        group_val = group_value_current.get(group, 1)
        position_weight = current_value / group_val if group_val > 0 else 0
        amount_eur = abs((delta_group / 100) * investable * position_weight)

        if amount_eur < 10:
            continue  # sotto 10 EUR non ha senso

        target_pct = round(current_pct + (delta_group * position_weight), 2)
        suggestions.append(RebalanceSuggestion(
            asset_id=aid,
            symbol=asset.symbol,
            name=asset.name,
            action="buy" if delta_group > 0 else "sell",
            amount_eur=round(amount_eur, 2),
            current_pct=round(current_pct, 2),
            target_pct=target_pct,
            delta_pct=round(delta_group * position_weight, 2),
        ))

    return sorted(suggestions, key=lambda s: abs(s.amount_eur), reverse=True)
