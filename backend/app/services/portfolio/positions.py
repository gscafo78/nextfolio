"""
FIFO P&L engine per il portafoglio.

Per ogni asset calcola:
- Posizione aperta (quantity + lotti FIFO rimanenti)
- PMC (Prezzo Medio di Carico) sui lotti aperti
- P&L realizzato sulle vendite già chiuse
"""
from dataclasses import dataclass, field

from app.models.transaction import Transaction, TransactionType


@dataclass
class Lot:
    quantity: float
    cost_per_unit_eur: float  # costo unitario in EUR al momento dell'acquisto


@dataclass
class PositionCalc:
    asset_id: int
    lots: list = field(default_factory=list)
    realized_pnl_eur: float = 0.0
    total_invested_eur: float = 0.0  # cumulativo costo BUY in EUR

    @property
    def quantity(self) -> float:
        return sum(lot.quantity for lot in self.lots)

    @property
    def pmc_eur(self) -> float:
        qty = self.quantity
        if qty < 1e-10:
            return 0.0
        return sum(lot.quantity * lot.cost_per_unit_eur for lot in self.lots) / qty


def calculate_positions(transactions: list[Transaction]) -> dict[int, PositionCalc]:
    """
    Calcola le posizioni aperte con metodo FIFO.
    Restituisce {asset_id: PositionCalc} solo per asset con quantità > 0.
    """
    positions: dict[int, PositionCalc] = {}

    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        asset_id = tx.asset_id
        if asset_id not in positions:
            positions[asset_id] = PositionCalc(asset_id=asset_id)
        pos = positions[asset_id]

        if tx.type == TransactionType.BUY:
            cost_eur = tx.quantity * tx.price * tx.exchange_rate + tx.fee
            cost_per_unit = cost_eur / tx.quantity if tx.quantity > 0 else 0.0
            pos.lots.append(Lot(quantity=tx.quantity, cost_per_unit_eur=cost_per_unit))
            pos.total_invested_eur += cost_eur

        elif tx.type == TransactionType.SELL:
            proceeds_eur = tx.quantity * tx.price * tx.exchange_rate - tx.fee
            remaining = tx.quantity
            cost_of_sold = 0.0

            i = 0
            while remaining > 1e-10 and i < len(pos.lots):
                lot = pos.lots[i]
                used = min(remaining, lot.quantity)
                cost_of_sold += used * lot.cost_per_unit_eur
                remaining -= used
                lot.quantity -= used
                i += 1

            pos.lots = [lot for lot in pos.lots if lot.quantity > 1e-10]
            pos.realized_pnl_eur += proceeds_eur - cost_of_sold

    return {k: v for k, v in positions.items() if v.quantity > 1e-6}
