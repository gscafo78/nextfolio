"""
Versamento intelligente: dove investire un importo per avvicinarsi all'allocazione
obiettivo **senza vendere** (niente costi né imposte di vendita).

Algoritmo (per asset class del sottostante):
  T' = patrimonio dopo il versamento (T + A se denaro nuovo, T se dalla liquidità,
       nel qual caso A viene tolto dalla classe Monetario)
  deficit_c = max(0, w_c · T' − V_c)
  se Σ deficit ≥ A → A ripartito in proporzione ai deficit
  altrimenti       → deficit colmati, il resto ripartito secondo i pesi obiettivo
Dentro ogni classe l'importo va agli strumenti preferiti (con i loro pesi) o, in
mancanza, alle posizioni già detenute in quella classe in proporzione al valore.
Con le quote intere si arrotonda per difetto; ordini sotto il minimo sono scartati
e l'importo non investito resta in liquidità.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.services.portfolio.classification import ASSET_CLASS_LABELS, ASSET_CLASSES, MONEY_MARKET, asset_class_weights


@dataclass
class Instrument:
    name: str
    price_eur: float
    weight: float = 1.0               # peso dentro la classe
    asset_id: int | None = None
    symbol: str | None = None
    type: str = "ETF"


@dataclass
class Order:
    name: str
    asset_class: str
    amount_eur: float
    quantity: float
    price_eur: float
    fee_eur: float
    asset_id: int | None = None
    symbol: str | None = None
    type: str = "ETF"


@dataclass
class ContributionPlan:
    amount_eur: float
    per_class: list[dict]             # [{class, label, target_pct, before_pct, after_pct, allocated_eur}]
    orders: list[Order]
    uninvested_eur: float
    warnings: list[str] = field(default_factory=list)


def class_values(snapshot) -> dict[str, float]:
    """Valore per asset class (look-through, ETF bilanciati ripartiti) + liquidità in Monetario."""
    values = {c: 0.0 for c in ASSET_CLASSES}
    for aid, pos in snapshot.positions.items():
        price = snapshot.price_eur.get(aid)
        if price is None:
            continue
        for c, w in asset_class_weights(snapshot.asset_info.get(aid, {})).items():
            values[c] += pos.quantity * price * w
    values[MONEY_MARKET] += sum(max(b.value_eur, 0.0) for b in snapshot.cash)
    return values


def drift(values: dict[str, float], targets: dict[str, float], tolerance_pct: float) -> list[dict]:
    total = sum(values.values())
    out = []
    for c in ASSET_CLASSES:
        if c not in targets and values.get(c, 0) <= 0:
            continue
        cur = values.get(c, 0.0) / total * 100 if total > 0 else 0.0
        tgt = targets.get(c, 0.0) * 100
        out.append({"class": c, "label": ASSET_CLASS_LABELS[c], "current_pct": round(cur, 2),
                    "target_pct": round(tgt, 2), "delta_pct": round(cur - tgt, 2),
                    "out_of_band": abs(cur - tgt) > tolerance_pct})
    return out


def plan_contribution(
    values: dict[str, float],
    targets: dict[str, float],
    amount: float,
    instruments: dict[str, list[Instrument]],
    *,
    from_cash: bool = False,
    whole_units: bool = False,
    min_order_eur: float = 0.0,
    fee_per_order_eur: float = 0.0,
) -> ContributionPlan:
    warnings: list[str] = []
    total_w = sum(targets.values())
    if total_w <= 0 or amount <= 0:
        return ContributionPlan(amount, [], [], amount, ["Imposta un'allocazione obiettivo e un importo positivo."])
    targets = {c: w / total_w for c, w in targets.items()}

    base = dict(values)
    if from_cash:
        cash = base.get(MONEY_MARKET, 0.0)
        if amount > cash + 0.005:
            warnings.append(f"Liquidità disponibile {cash:.2f} € inferiore all'importo da investire {amount:.2f} €.")
        base[MONEY_MARKET] = cash - amount
    total_after = sum(base.values()) + amount

    deficits = {c: max(0.0, targets.get(c, 0.0) * total_after - base.get(c, 0.0)) for c in targets}
    sum_def = sum(deficits.values())
    if sum_def >= amount:
        alloc = {c: amount * d / sum_def for c, d in deficits.items()} if sum_def > 0 else {}
    else:
        rest = amount - sum_def
        alloc = {c: deficits[c] + rest * targets[c] for c in targets}

    orders: list[Order] = []
    uninvested = 0.0
    for c, a in alloc.items():
        if a <= 0.005:
            continue
        instr = [i for i in instruments.get(c, []) if i.price_eur and i.price_eur > 0]
        if not instr:
            if c == MONEY_MARKET:
                continue   # quota monetaria: resta liquidità
            warnings.append(f"Nessuno strumento per «{ASSET_CLASS_LABELS[c]}»: scegline uno tra gli strumenti preferiti.")
            uninvested += a
            continue
        wsum = sum(i.weight for i in instr) or 1.0
        for i in instr:
            share = a * i.weight / wsum
            budget = share - fee_per_order_eur
            qty = budget / i.price_eur if budget > 0 else 0.0
            if whole_units:
                qty = math.floor(qty + 1e-9)
            spent = qty * i.price_eur
            if qty <= 0 or spent < max(min_order_eur, 0.01):
                uninvested += share
                if qty > 0 or budget > 0:
                    warnings.append(f"{i.name}: ordine da {share:.2f} € sotto il minimo o inferiore a una quota, non eseguito.")
                continue
            orders.append(Order(name=i.name, asset_class=ASSET_CLASS_LABELS[c], amount_eur=round(spent, 2),
                                quantity=round(qty, 6), price_eur=i.price_eur, fee_eur=fee_per_order_eur,
                                asset_id=i.asset_id, symbol=i.symbol, type=i.type))
            uninvested += share - spent - fee_per_order_eur

    # Allocazione risultante (la parte non investita resta in liquidità)
    after = dict(base)
    for o in orders:
        cls = next(k for k, v in ASSET_CLASS_LABELS.items() if v == o.asset_class)
        after[cls] = after.get(cls, 0.0) + o.amount_eur
    after[MONEY_MARKET] = after.get(MONEY_MARKET, 0.0) + max(uninvested, 0.0)
    tb, ta = sum(values.values()), sum(after.values())
    per_class = [
        {"class": c, "label": ASSET_CLASS_LABELS[c], "target_pct": round(targets.get(c, 0.0) * 100, 2),
         "before_pct": round(values.get(c, 0.0) / tb * 100, 2) if tb > 0 else 0.0,
         "after_pct": round(after.get(c, 0.0) / ta * 100, 2) if ta > 0 else 0.0,
         "allocated_eur": round(alloc.get(c, 0.0), 2)}
        for c in ASSET_CLASSES if c in targets or values.get(c, 0) > 0
    ]
    return ContributionPlan(amount, per_class, orders, round(max(uninvested, 0.0), 2), warnings)
