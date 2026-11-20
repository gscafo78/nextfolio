"""
Pianificazione fiscale (Italia): zainetto in scadenza, vendite suggerite,
simulazione di vendite multiple con impatto sulle imposte dell'anno.

Si appoggia al motore fiscale (``services/tax/calculator.py``): costo medio
ponderato, titoli di Stato al 48,08%, plusvalenze ETF come redditi di capitale
(NON compensabili), zainetto separato per le cripto-attività.

Limiti dichiarati: lo zainetto è considerato unico per tutti i conti (in regime
amministrato ogni intermediario ha il proprio); non si verificano regole
anti-abuso. Le vendite seguite da riacquisto immediato servono solo a
"aggiornare" il costo fiscale: valuta costi di negoziazione e spread.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services.tax.calculator import (
    CARRYFORWARD_YEARS,
    CATEGORY_CRYPTO,
    CATEGORY_FUND,
    CATEGORY_GOVT,
    GOVT_WEIGHT,
    RATE_STANDARD,
    build_annual_reports,
    carryforward_pools,
    compute_tax_events,
    crypto_rate,
    fund_taxable_fraction,
    open_cost_pools,
    tax_category,
)


@dataclass
class HoldingPool:
    """Posizione aperta in un pool fiscale (conto amministrato o insieme dei conti dichiarativi)."""
    asset: object
    account: object | None         # conto (amministrato) o None (pool dichiarativo)
    account_name: str
    quantity: float
    avg_cost_eur: float
    price_eur: float

    @property
    def category(self) -> str:
        return tax_category(self.asset)

    @property
    def gain_per_unit(self) -> float:
        return self.price_eur - self.avg_cost_eur

    @property
    def weight(self) -> float:
        """Quota imponibile del risultato (48,08% per i titoli di Stato, ridotta per ETF con quota titoli di Stato)."""
        if self.category == CATEGORY_GOVT:
            return GOVT_WEIGHT
        if self.category == CATEGORY_FUND:
            return fund_taxable_fraction(self.asset)
        return 1.0


def holding_pools(transactions: list, price_eur: dict[int, float]) -> list[HoldingPool]:
    accounts = {t.account_id: t.account for t in transactions}
    assets = {t.asset_id: t.asset for t in transactions}
    out = []
    for key, pool in open_cost_pools(transactions).items():
        asset_id = key[-1]
        if asset_id not in price_eur:
            continue
        acc = accounts.get(key[1]) if key[0] == "A" else None
        out.append(HoldingPool(asset=assets[asset_id], account=acc,
                               account_name=acc.name if acc else "Conti dichiarativi",
                               quantity=pool.quantity, avg_cost_eur=pool.avg_cost_per_unit,
                               price_eur=price_eur[asset_id]))
    return out


@dataclass
class TaxOverview:
    year: int
    pool_standard: list[dict]          # [{year, amount, expires_year, expiring}]
    pool_crypto: list[dict]
    expiring_standard: float           # minusvalenze che scadono a fine anno
    expiring_crypto: float
    use_losses: list[dict]             # vendite in guadagno per usare le minus in scadenza
    harvest_losses: list[dict]         # vendite in perdita per compensare plus dell'anno
    year_tax: dict                     # stima imposte dell'anno
    notes: list[str] = field(default_factory=list)


def _pool_rows(pool: dict[int, float], year: int) -> list[dict]:
    return [{"year": y, "amount": round(a, 2), "expires_year": y + CARRYFORWARD_YEARS,
             "expiring": y + CARRYFORWARD_YEARS == year} for y, a in sorted(pool.items())]


def tax_overview(transactions: list, price_eur: dict[int, float], today: datetime.date | None = None,
                 wealth_tax_eur: float = 0.0) -> TaxOverview:
    today = today or datetime.date.today()
    year = today.year
    events = compute_tax_events(transactions)
    reports = {r.year: r for r in build_annual_reports(events)}
    std, crypto = carryforward_pools(events, year)
    exp_std = sum(a for y, a in std.items() if y + CARRYFORWARD_YEARS == year)
    exp_crypto = sum(a for y, a in crypto.items() if y + CARRYFORWARD_YEARS == year)
    pools = holding_pools(transactions, price_eur)

    # (a) usare le minusvalenze in scadenza realizzando plusvalenze compensabili (non ETF: redditi di capitale)
    use_losses: list[dict] = []
    for pool_name, remaining, cats, rate in (
        ("standard", exp_std, {"standard", CATEGORY_GOVT}, RATE_STANDARD),
        ("crypto", exp_crypto, {CATEGORY_CRYPTO}, crypto_rate(year)),
    ):
        candidates = sorted([p for p in pools if p.category in cats and p.gain_per_unit > 0],
                            key=lambda p: p.gain_per_unit * p.weight * p.quantity, reverse=True)
        for p in candidates:
            if remaining <= 0.5:
                break
            taxable_per_unit = p.gain_per_unit * p.weight
            qty = min(p.quantity, remaining / taxable_per_unit)
            used = qty * taxable_per_unit
            remaining -= used
            use_losses.append({
                "asset_id": p.asset.id, "name": p.asset.name, "account": p.account_name, "pool": pool_name,
                "quantity": round(qty, 6), "price_eur": round(p.price_eur, 4), "proceeds_eur": round(qty * p.price_eur, 2),
                "gain_eur": round(qty * p.gain_per_unit, 2), "losses_used_eur": round(used, 2),
                "tax_saved_eur": round(used * rate, 2),
            })

    # (b) compensare le plusvalenze già realizzate nell'anno realizzando minusvalenze
    rep = reports.get(year)
    harvest: list[dict] = []
    for pool_name, net, cats, rate in (
        ("standard", rep.net_taxable_standard if rep else 0.0, {"standard", CATEGORY_GOVT, CATEGORY_FUND}, RATE_STANDARD),
        ("crypto", rep.net_taxable_crypto if rep else 0.0, {CATEGORY_CRYPTO}, crypto_rate(year)),
    ):
        remaining = net
        candidates = sorted([p for p in pools if p.category in cats and p.gain_per_unit < 0],
                            key=lambda p: p.gain_per_unit * p.weight * p.quantity)
        for p in candidates:
            if remaining <= 0.5:
                break
            loss_per_unit = -p.gain_per_unit * p.weight
            qty = min(p.quantity, remaining / loss_per_unit)
            offset = qty * loss_per_unit
            remaining -= offset
            harvest.append({
                "asset_id": p.asset.id, "name": p.asset.name, "account": p.account_name, "pool": pool_name,
                "quantity": round(qty, 6), "price_eur": round(p.price_eur, 4), "proceeds_eur": round(qty * p.price_eur, 2),
                "loss_eur": round(qty * p.gain_per_unit, 2), "gains_offset_eur": round(offset, 2),
                "tax_saved_eur": round(offset * rate, 2),
            })

    year_tax = {
        "capital_gains_tax_eur": rep.total_tax_due if rep else 0.0,
        "income_tax_eur": rep.income_tax_eur if rep else 0.0,
        "wealth_tax_eur": round(wealth_tax_eur, 2),
        "net_taxable_standard_eur": rep.net_taxable_standard if rep else 0.0,
        "gains_funds_eur": rep.gains_funds if rep else 0.0,
    }
    year_tax["total_eur"] = round(sum(v for k, v in year_tax.items() if k.endswith("tax_eur")), 2)

    notes = [
        "Lo zainetto è considerato unico per tutti i conti: in regime amministrato ogni intermediario tiene il proprio.",
        "Le plusvalenze da ETF/fondi sono redditi di capitale e non usano lo zainetto; le minusvalenze da ETF sì.",
        "Vendere e riacquistare aggiorna il costo fiscale: considera commissioni, spread e la possibile contestazione per abuso del diritto.",
    ]
    return TaxOverview(year=year, pool_standard=_pool_rows(std, year), pool_crypto=_pool_rows(crypto, year),
                       expiring_standard=round(exp_std, 2), expiring_crypto=round(exp_crypto, 2),
                       use_losses=use_losses, harvest_losses=harvest, year_tax=year_tax, notes=notes)


@dataclass
class Sale:
    asset_id: int
    quantity: float
    price_eur: float
    account: object                 # conto da cui vendere
    fee_eur: float = 0.0


def _year_summary(r) -> dict:
    if r is None:
        return {"total_tax_eur": 0.0, "tax_standard_eur": 0.0, "tax_funds_eur": 0.0, "tax_crypto_eur": 0.0,
                "carryforward_used_eur": 0.0, "new_carryforward_eur": 0.0}
    return {"total_tax_eur": r.total_tax_due, "tax_standard_eur": r.tax_standard, "tax_funds_eur": r.tax_funds,
            "tax_crypto_eur": r.tax_crypto,
            "carryforward_used_eur": round(r.carryforward_applied_standard + r.carryforward_applied_crypto, 2),
            "new_carryforward_eur": round(r.new_carryforward_standard + r.new_carryforward_crypto, 2)}


def simulate_sales(transactions: list, sales: list[Sale], today: datetime.date | None = None) -> dict:
    """Imposte dell'anno prima/dopo un insieme di vendite ipotetiche alla data odierna."""
    today = today or datetime.date.today()
    assets = {t.asset_id: t.asset for t in transactions}
    synthetic = [
        SimpleNamespace(id=10**12 + i, account=s.account, account_id=s.account.id, asset=assets[s.asset_id],
                        asset_id=s.asset_id, type=TransactionType.SELL, date=today, quantity=s.quantity,
                        price=s.price_eur, exchange_rate=1.0, fee=s.fee_eur, price_currency="EUR")
        for i, s in enumerate(sales)
    ]
    before = {r.year: r for r in build_annual_reports(compute_tax_events(transactions))}.get(today.year)
    after_events = compute_tax_events(list(transactions) + synthetic)
    after = {r.year: r for r in build_annual_reports(after_events)}.get(today.year)
    sale_events = [e for e in after_events if e.date == today and e.tx_type == "SELL"][-len(sales):] if sales else []
    rows = [{"asset_id": e.asset_id, "name": e.asset_name, "quantity": e.quantity, "proceeds_eur": round(e.proceeds_eur, 2),
             "cost_eur": round(e.cost_eur or 0, 2), "gain_loss_eur": round(e.gain_loss_eur, 2), "category": e.category,
             "tax_rate": round(e.tax_rate, 4)} for e in sale_events]
    b, a = _year_summary(before), _year_summary(after)
    return {"year": today.year, "sales": rows, "before": b, "after": a,
            "delta_tax_eur": round(a["total_tax_eur"] - b["total_tax_eur"], 2),
            "proceeds_eur": round(sum(r["proceeds_eur"] for r in rows), 2)}
