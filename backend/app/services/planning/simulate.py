"""
Simulatore d'acquisto: effetto di acquisti ipotetici sul portafoglio.

``simulate()`` è una funzione pura: riceve lo snapshot corrente e gli acquisti
già risolti (prezzo in EUR, look-through del titolo) e ricalcola allocazione e
regole X-Ray prima/dopo. Il caricamento dei dati (DB, Yahoo) è nell'endpoint.
"""
from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from datetime import date

from app.schemas.portfolio import AllocationOut, PositionOut, XRayResponse
from app.services.portfolio.allocation import calculate_allocation
from app.services.portfolio.positions import Lot, PositionCalc
from app.services.portfolio.xray import compute_xray


@dataclass
class SimItem:
    """Acquisto ipotetico già risolto."""
    name: str
    info: dict                     # build_asset_info (anche per titoli esterni)
    price_eur: float
    quantity: float
    asset_id: int | None = None    # None = titolo non ancora in Nextfolio
    symbol: str | None = None      # ticker Yahoo per i titoli esterni
    fee_eur: float = 0.0
    account_id: int | None = None

    @property
    def amount_eur(self) -> float:
        return self.quantity * self.price_eur


@dataclass
class SimResult:
    allocation_before: AllocationOut
    allocation_after: AllocationOut
    xray_before: XRayResponse
    xray_after: XRayResponse
    weights: list[dict]            # [{name, before_pct, after_pct, delta_pct, new}]
    total_before_eur: float        # investimenti + liquidità
    total_after_eur: float
    invested_eur: float            # controvalore degli acquisti
    fees_eur: float
    cash_before_eur: float
    cash_after_eur: float
    warnings: list[str] = field(default_factory=list)

    @property
    def rule_changes(self) -> list[dict]:
        before = {r.key: r for r in self.xray_before.rules}
        out = []
        for r in self.xray_after.rules:
            b = before.get(r.key)
            out.append({
                "key": r.key, "name": r.name, "category": r.category,
                "before_status": b.status if b else None, "after_status": r.status,
                "before_actual": b.actual if b else None, "after_actual": r.actual,
                "changed": bool(b and b.status != r.status),
            })
        return out


def _positions_out(positions: dict, info: dict, price_eur: dict) -> list[PositionOut]:
    out = []
    for aid, pos in positions.items():
        i = info.get(aid, {})
        p = price_eur.get(aid)
        value = pos.quantity * p if p is not None else None
        cost = pos.quantity * pos.pmc_eur
        out.append(PositionOut(
            asset_id=aid, symbol=i.get("symbol") or str(aid), name=i.get("name") or str(aid),
            asset_type=i.get("type", "OTHER"), currency=i.get("currency") or "EUR", exchange="OTHER",
            quantity=pos.quantity, pmc_eur=pos.pmc_eur, total_invested_eur=cost, realized_pnl_eur=0.0,
            current_price=p, current_price_eur=p, current_value_eur=value,
            unrealized_pnl_eur=(value - cost) if value is not None else None,
            unrealized_pnl_pct=((value - cost) / cost * 100) if value is not None and cost > 0 else None,
            change_pct=None,
        ))
    return out


def _cash_total(cash: list) -> float:
    return sum(max(b.value_eur, 0.0) for b in cash)


def _evaluate(snapshot, positions, info, price_eur, account_values, cash, maturities, today):
    alloc = calculate_allocation(positions, info, price_eur, account_values, cash=cash)
    cash_eur = _cash_total(cash)
    invest = sum(p.quantity * price_eur[a] for a, p in positions.items() if a in price_eur)
    xray = compute_xray(
        positions=_positions_out(positions, info, price_eur), allocation=alloc,
        transactions=snapshot.transactions, total_value=invest + cash_eur,
        asset_info=info, maturities=maturities, today=today, cash_eur=cash_eur,
    )
    return alloc, xray, invest + cash_eur


def simulate(
    snapshot,
    items: list[SimItem],
    *,
    use_cash: bool = False,
    accounts: dict[int, str] | None = None,   # {account_id: nome}
    maturities: dict | None = None,
    today: date | None = None,
) -> SimResult:
    accounts = accounts or {a.id: a.name for a in snapshot.accounts}
    maturities = maturities or {}
    warnings: list[str] = []

    alloc_b, xray_b, total_b = _evaluate(snapshot, snapshot.positions, snapshot.asset_info, snapshot.price_eur,
                                         snapshot.account_values, snapshot.cash, maturities, today)

    positions = {aid: PositionCalc(asset_id=aid, lots=copy.deepcopy(p.lots), realized_pnl_eur=p.realized_pnl_eur,
                                   total_invested_eur=p.total_invested_eur)
                 for aid, p in snapshot.positions.items()}
    info = dict(snapshot.asset_info)
    price_eur = dict(snapshot.price_eur)
    account_values = dict(snapshot.account_values)
    cash = [dataclasses.replace(b) for b in snapshot.cash]
    names: dict[int, str] = {aid: i.get("name", str(aid)) for aid, i in info.items()}

    next_virtual = -1
    new_ids: set[int] = set()
    for it in items:
        if it.quantity <= 0 or it.price_eur <= 0:
            warnings.append(f"{it.name}: quantità o prezzo non validi, acquisto ignorato.")
            continue
        aid = it.asset_id
        if aid is None or aid not in info:
            # titolo nuovo (esterno o non in portafoglio): id virtuale se non è nel DB
            if aid is None:
                aid = next_virtual
                next_virtual -= 1
            info[aid] = it.info
            names[aid] = it.name
            new_ids.add(aid)
        price_eur.setdefault(aid, it.price_eur)
        pos = positions.setdefault(aid, PositionCalc(asset_id=aid))
        pos.lots.append(Lot(quantity=it.quantity, cost_per_unit_eur=(it.amount_eur + it.fee_eur) / it.quantity))
        pos.total_invested_eur += it.amount_eur + it.fee_eur

        # Il valore va al prezzo corrente del titolo (non al prezzo d'acquisto ipotizzato)
        value_now = it.quantity * price_eur[aid]
        acc_name = accounts.get(it.account_id) if it.account_id is not None else None
        if acc_name:
            account_values[acc_name] = account_values.get(acc_name, 0.0) + value_now

        if use_cash:
            spend = it.amount_eur + it.fee_eur
            target = next((b for b in cash if b.account_id == it.account_id), None) if it.account_id else None
            if target is None:
                # senza conto indicato: si usa la liquidità dei conti in ordine, finché basta
                for b in cash:
                    if b.value_eur > 0:
                        target = b
                        break
            if target is None:
                warnings.append(f"{it.name}: nessuna liquidità registrata da cui prelevare {spend:.2f} €.")
                continue
            if target.value_eur < spend - 0.005:
                warnings.append(
                    f"{it.name}: liquidità insufficiente sul conto {target.account_name} "
                    f"({target.value_eur:.2f} € disponibili, servono {spend:.2f} €)."
                )
            ratio = target.balance / target.value_eur if target.value_eur else 1.0
            target.value_eur -= spend
            target.balance = target.value_eur * ratio

    alloc_a, xray_a, total_a = _evaluate(snapshot, positions, info, price_eur, account_values, cash, maturities, today)

    def weights(pos, prices, total):
        return {a: p.quantity * prices[a] / total * 100 for a, p in pos.items() if a in prices and total > 0}

    wb = weights(snapshot.positions, snapshot.price_eur, total_b)
    wa = weights(positions, price_eur, total_a)
    rows = [
        {"name": names.get(a, str(a)), "before_pct": round(wb.get(a, 0.0), 2), "after_pct": round(wa.get(a, 0.0), 2),
         "delta_pct": round(wa.get(a, 0.0) - wb.get(a, 0.0), 2), "new": a in new_ids}
        for a in set(wb) | set(wa)
    ]
    rows.sort(key=lambda r: r["after_pct"], reverse=True)

    valid = [it for it in items if it.quantity > 0 and it.price_eur > 0]
    return SimResult(
        allocation_before=alloc_b, allocation_after=alloc_a, xray_before=xray_b, xray_after=xray_a,
        weights=rows, total_before_eur=round(total_b, 2), total_after_eur=round(total_a, 2),
        invested_eur=round(sum(it.amount_eur for it in valid), 2),
        fees_eur=round(sum(it.fee_eur for it in valid), 2),
        cash_before_eur=round(_cash_total(snapshot.cash), 2), cash_after_eur=round(_cash_total(cash), 2),
        warnings=warnings,
    )
