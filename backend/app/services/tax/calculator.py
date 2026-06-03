"""
Tax engine per normativa italiana.

Aliquote:
  - 26%    Azioni, ETF, crypto, commodity, REIT, obbligazioni societarie, dividendi
  - 12.5%  Titoli di Stato italiani (BTP, BOT, CCT) su MOT — capital gain e cedole

Zainetto fiscale:
  - Le minusvalenze compensano le plusvalenze entro 4 anni
  - Due zainetti separati: standard (26%) e titoli di Stato (12.5%)
  - Le minusvalenze da dividendi NON compensano i capital gain

Semplificazioni MVP:
  - Metodo FIFO (sia per regime dichiarativo che amministrato)
  - Dividendi e cedole mostrati come reddito informativo (spesso già ritenuta alla fonte)
  - IVAFE non calcolata (richiede classificazione dei conti esteri)
  - PIR non gestito
"""
import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from app.models.asset import Asset, AssetType, Exchange
from app.models.transaction import Transaction, TransactionType

RATE_STANDARD = 0.26
RATE_GOVT = 0.125


def _is_government_bond(asset: Asset) -> bool:
    """BTP/BOT/CCT: BOND con ISIN italiano (IT...) → aliquota 12,5%."""
    asset_type = asset.type if isinstance(asset.type, str) else asset.type.value
    isin = asset.isin or ""
    return asset_type == "BOND" and isin.startswith("IT")


# ── Strutture dati interne ────────────────────────────────────────────────────

@dataclass
class _Lot:
    quantity: float
    cost_per_unit_eur: float


@dataclass
class _WACLot:
    """Lot aggregato per regime amministrato (Prezzo Medio di Carico / WAC)."""
    quantity: float = 0.0
    avg_cost_per_unit: float = 0.0

    def buy(self, qty: float, cost_eur: float) -> None:
        total_qty = self.quantity + qty
        self.avg_cost_per_unit = (
            (self.quantity * self.avg_cost_per_unit + cost_eur) / total_qty
            if total_qty > 1e-10 else 0.0
        )
        self.quantity = total_qty

    def sell(self, qty: float) -> float:
        """Restituisce il costo base al PMC e aggiorna il lot."""
        cost_of_sold = qty * self.avg_cost_per_unit
        self.quantity -= qty
        if self.quantity < 1e-10:
            self.quantity = 0.0
            self.avg_cost_per_unit = 0.0
        return cost_of_sold


@dataclass
class TaxEvent:
    date: datetime.date
    asset_id: int
    asset_name: str
    asset_type: str
    tx_type: str          # "SELL" | "DIVIDEND" | "COUPON" | "INTEREST"
    quantity: float | None
    proceeds_eur: float
    cost_eur: float | None
    gain_loss_eur: float
    is_government_bond: bool
    is_sostituto_imposta: bool = False   # regime del conto sorgente
    calculation_method: str = "FIFO"    # "FIFO" | "PMC"

    @property
    def tax_rate(self) -> float:
        return RATE_GOVT if self.is_government_bond else RATE_STANDARD

    @property
    def tax_bracket(self) -> str:
        return "government_bond" if self.is_government_bond else "standard"


@dataclass
class CarryForwardEntry:
    year: int
    amount: float  # importo residuo (positivo = perdita disponibile)
    expires_year: int  # ultimo anno di utilizzo (year + 4)


@dataclass
class AnnualTaxReport:
    year: int

    # Capital gain — bracket standard 26%
    gains_standard: float = 0.0
    losses_standard: float = 0.0
    carryforward_applied_standard: float = 0.0
    net_taxable_standard: float = 0.0
    tax_standard: float = 0.0

    # Capital gain — titoli di Stato 12.5%
    gains_govt: float = 0.0
    losses_govt: float = 0.0
    carryforward_applied_govt: float = 0.0
    net_taxable_govt: float = 0.0
    tax_govt: float = 0.0

    # Reddito (cedole, dividendi, interessi)
    dividends_eur: float = 0.0
    coupons_govt_eur: float = 0.0
    coupons_standard_eur: float = 0.0
    interests_eur: float = 0.0
    income_tax_eur: float = 0.0          # ritenuta stimata su redditi (tutti i conti)
    administered_income_tax: float = 0.0  # ritenuta già applicata dal broker
    declaratory_income_tax: float = 0.0  # ritenuta da dichiarare nel 730

    total_tax_due: float = 0.0

    # Perdite portate agli anni successivi
    new_carryforward_standard: float = 0.0
    new_carryforward_govt: float = 0.0

    # Carryforward disponibile a inizio anno (prima dell'applicazione)
    prior_carryforward_standard: list[CarryForwardEntry] = field(default_factory=list)
    prior_carryforward_govt: list[CarryForwardEntry] = field(default_factory=list)

    events: list[TaxEvent] = field(default_factory=list)

    # Breakdown per regime (calcolato sugli eventi, senza carryforward separato)
    administered_gains_standard: float = 0.0   # gestito dal broker
    administered_losses_standard: float = 0.0
    administered_tax_standard: float = 0.0
    administered_gains_govt: float = 0.0
    administered_losses_govt: float = 0.0
    administered_tax_govt: float = 0.0
    administered_dividends_eur: float = 0.0
    administered_total_tax: float = 0.0

    declaratory_gains_standard: float = 0.0    # da dichiarare nel 730
    declaratory_losses_standard: float = 0.0
    declaratory_tax_standard: float = 0.0
    declaratory_gains_govt: float = 0.0
    declaratory_losses_govt: float = 0.0
    declaratory_tax_govt: float = 0.0
    declaratory_dividends_eur: float = 0.0
    declaratory_total_tax: float = 0.0

    has_declaratory_accounts: bool = False


# ── Engine principale ─────────────────────────────────────────────────────────

def compute_tax_events(transactions: list[Transaction]) -> list[TaxEvent]:
    """
    Scorre le transazioni in ordine cronologico e genera gli eventi fiscali.

    Metodo di calcolo del costo base:
    - Regime amministrato (is_sostituto_imposta=True) → PMC/WAC per conto
      Pool: lots_wac[(account_id, asset_id)]
    - Regime dichiarativo (is_sostituto_imposta=False) → FIFO globale per asset
      Pool: lots_fifo[asset_id]
    """
    lots_fifo: dict[int, list[_Lot]] = defaultdict(list)
    lots_wac: dict[tuple[int, int], _WACLot] = defaultdict(_WACLot)
    events: list[TaxEvent] = []

    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        asset: Asset = tx.asset
        govt = _is_government_bond(asset)
        sostituto = getattr(tx.account, "is_sostituto_imposta", False)
        asset_type_str = asset.type if isinstance(asset.type, str) else asset.type.value

        if tx.type == TransactionType.BUY:
            cost_eur = tx.quantity * tx.price * tx.exchange_rate + tx.fee
            if sostituto:
                lots_wac[(tx.account_id, tx.asset_id)].buy(tx.quantity, cost_eur)
            else:
                cost_per_unit = cost_eur / tx.quantity if tx.quantity > 0 else 0.0
                lots_fifo[tx.asset_id].append(_Lot(tx.quantity, cost_per_unit))

        elif tx.type == TransactionType.SELL:
            proceeds = tx.quantity * tx.price * tx.exchange_rate - tx.fee

            if sostituto:
                wac = lots_wac[(tx.account_id, tx.asset_id)]
                cost_of_sold = wac.sell(tx.quantity)
                method = "PMC"
            else:
                remaining = tx.quantity
                cost_of_sold = 0.0
                asset_lots = lots_fifo[tx.asset_id]
                i = 0
                while remaining > 1e-10 and i < len(asset_lots):
                    lot = asset_lots[i]
                    used = min(remaining, lot.quantity)
                    cost_of_sold += used * lot.cost_per_unit_eur
                    remaining -= used
                    lot.quantity -= used
                    i += 1
                lots_fifo[tx.asset_id] = [l for l in asset_lots if l.quantity > 1e-10]
                method = "FIFO"

            events.append(TaxEvent(
                date=tx.date,
                asset_id=tx.asset_id,
                asset_name=asset.name,
                asset_type=asset_type_str,
                tx_type="SELL",
                quantity=tx.quantity,
                proceeds_eur=proceeds,
                cost_eur=cost_of_sold,
                gain_loss_eur=proceeds - cost_of_sold,
                is_government_bond=govt,
                is_sostituto_imposta=sostituto,
                calculation_method=method,
            ))

        elif tx.type == TransactionType.DIVIDEND:
            amount = tx.quantity * tx.price * tx.exchange_rate - tx.fee
            events.append(TaxEvent(
                date=tx.date,
                asset_id=tx.asset_id,
                asset_name=asset.name,
                asset_type=asset_type_str,
                tx_type="DIVIDEND",
                quantity=None,
                proceeds_eur=amount,
                cost_eur=None,
                gain_loss_eur=amount,
                is_government_bond=False,
                is_sostituto_imposta=sostituto,
            ))

        elif tx.type == TransactionType.COUPON:
            amount = tx.quantity * tx.price * tx.exchange_rate - tx.fee
            events.append(TaxEvent(
                date=tx.date,
                asset_id=tx.asset_id,
                asset_name=asset.name,
                asset_type=asset_type_str,
                tx_type="COUPON",
                quantity=None,
                proceeds_eur=amount,
                cost_eur=None,
                gain_loss_eur=amount,
                is_government_bond=govt,
                is_sostituto_imposta=sostituto,
            ))

        elif tx.type == TransactionType.INTEREST:
            amount = tx.quantity * tx.price * tx.exchange_rate - tx.fee
            events.append(TaxEvent(
                date=tx.date,
                asset_id=tx.asset_id,
                asset_name=asset.name,
                asset_type=asset_type_str,
                tx_type="INTEREST",
                quantity=None,
                proceeds_eur=amount,
                cost_eur=None,
                gain_loss_eur=amount,
                is_government_bond=False,
                is_sostituto_imposta=sostituto,
            ))

    return events


def _apply_carryforward(
    gains: float,
    pool: dict[int, float],
    current_year: int,
) -> tuple[float, float, list[CarryForwardEntry]]:
    """
    Applica il carryforward disponibile al reddito dell'anno corrente.

    Restituisce:
      - applied: importo effettivamente utilizzato
      - net_taxable: gains dopo applicazione
      - snapshot: stato del pool PRIMA dell'applicazione (per il report)
    """
    snapshot = [
        CarryForwardEntry(year=y, amount=a, expires_year=y + 4)
        for y, a in sorted(pool.items())
        if a > 1e-6 and current_year - y <= 4
    ]

    applied = 0.0
    remaining_gains = gains
    for y in sorted(pool.keys()):
        if current_year - y > 4 or remaining_gains < 1e-6:
            continue
        use = min(pool[y], remaining_gains)
        pool[y] -= use
        applied += use
        remaining_gains -= use

    # Rimuovi voci scadute o azzerate
    expired = [y for y in list(pool.keys()) if current_year - y > 4 or pool[y] < 1e-6]
    for y in expired:
        del pool[y]

    return applied, max(0.0, gains - applied), snapshot


def build_annual_reports(events: list[TaxEvent]) -> list[AnnualTaxReport]:
    """
    Raggruppa gli eventi per anno e calcola il report fiscale completo,
    gestendo il carryforward delle minusvalenze su 4 anni.
    """
    if not events:
        return []

    by_year: dict[int, list[TaxEvent]] = defaultdict(list)
    for ev in events:
        by_year[ev.date.year].append(ev)

    pool_standard: dict[int, float] = {}  # {anno_perdita: importo_residuo}
    pool_govt: dict[int, float] = {}

    reports: list[AnnualTaxReport] = []

    for year in sorted(by_year.keys()):
        year_events = by_year[year]
        report = AnnualTaxReport(year=year, events=year_events)

        # Separa eventi per categoria
        sell_standard = [e for e in year_events if e.tx_type == "SELL" and not e.is_government_bond]
        sell_govt = [e for e in year_events if e.tx_type == "SELL" and e.is_government_bond]
        dividends = [e for e in year_events if e.tx_type == "DIVIDEND"]
        coupons_govt = [e for e in year_events if e.tx_type == "COUPON" and e.is_government_bond]
        coupons_std = [e for e in year_events if e.tx_type == "COUPON" and not e.is_government_bond]
        interests = [e for e in year_events if e.tx_type == "INTEREST"]

        # Capital gain standard (26%)
        gains_s = sum(e.gain_loss_eur for e in sell_standard if e.gain_loss_eur > 0)
        losses_s = sum(-e.gain_loss_eur for e in sell_standard if e.gain_loss_eur < 0)
        report.gains_standard = gains_s
        report.losses_standard = losses_s

        # Stessa-anno: le minusvalenze compensano le plusvalenze prima del carryforward
        net_gains_s = max(0.0, gains_s - losses_s)
        net_loss_s  = max(0.0, losses_s - gains_s)

        if net_gains_s > 1e-6:
            applied_s, net_s, snap_s = _apply_carryforward(net_gains_s, pool_standard, year)
            report.carryforward_applied_standard = applied_s
            report.net_taxable_standard = net_s
            report.prior_carryforward_standard = snap_s
        else:
            report.prior_carryforward_standard = [
                CarryForwardEntry(year=y, amount=a, expires_year=y + 4)
                for y, a in sorted(pool_standard.items())
                if a > 1e-6 and year - y <= 4
            ]
            # Rimuovi scadute
            for y in [k for k in list(pool_standard.keys()) if year - k > 4]:
                del pool_standard[y]

        if net_loss_s > 1e-6:
            pool_standard[year] = pool_standard.get(year, 0.0) + net_loss_s
        report.new_carryforward_standard = net_loss_s
        report.tax_standard = round(report.net_taxable_standard * RATE_STANDARD, 2)

        # Capital gain titoli di Stato (12.5%)
        gains_g = sum(e.gain_loss_eur for e in sell_govt if e.gain_loss_eur > 0)
        losses_g = sum(-e.gain_loss_eur for e in sell_govt if e.gain_loss_eur < 0)
        report.gains_govt = gains_g
        report.losses_govt = losses_g

        net_gains_g = max(0.0, gains_g - losses_g)
        net_loss_g  = max(0.0, losses_g - gains_g)

        if net_gains_g > 1e-6:
            applied_g, net_g, snap_g = _apply_carryforward(net_gains_g, pool_govt, year)
            report.carryforward_applied_govt = applied_g
            report.net_taxable_govt = net_g
            report.prior_carryforward_govt = snap_g
        else:
            report.prior_carryforward_govt = [
                CarryForwardEntry(year=y, amount=a, expires_year=y + 4)
                for y, a in sorted(pool_govt.items())
                if a > 1e-6 and year - y <= 4
            ]
            for y in [k for k in list(pool_govt.keys()) if year - k > 4]:
                del pool_govt[y]

        if net_loss_g > 1e-6:
            pool_govt[year] = pool_govt.get(year, 0.0) + net_loss_g
        report.new_carryforward_govt = net_loss_g
        report.tax_govt = round(report.net_taxable_govt * RATE_GOVT, 2)

        # Reddito
        report.dividends_eur = sum(e.gain_loss_eur for e in dividends)
        report.coupons_govt_eur = sum(e.gain_loss_eur for e in coupons_govt)
        report.coupons_standard_eur = sum(e.gain_loss_eur for e in coupons_std)
        report.interests_eur = sum(e.gain_loss_eur for e in interests)
        report.income_tax_eur = round(
            report.dividends_eur * RATE_STANDARD
            + report.coupons_govt_eur * RATE_GOVT
            + report.coupons_standard_eur * RATE_STANDARD
            + report.interests_eur * RATE_STANDARD,
            2,
        )

        report.total_tax_due = round(report.tax_standard + report.tax_govt, 2)

        # ── Breakdown per regime ──────────────────────────────────────────────
        for administered in (True, False):
            prefix = "administered" if administered else "declaratory"
            ev_sell_s = [e for e in year_events if e.tx_type == "SELL" and not e.is_government_bond and e.is_sostituto_imposta == administered]
            ev_sell_g = [e for e in year_events if e.tx_type == "SELL" and e.is_government_bond and e.is_sostituto_imposta == administered]
            ev_div    = [e for e in year_events if e.tx_type in ("DIVIDEND", "COUPON", "INTEREST") and e.is_sostituto_imposta == administered]

            g_s = sum(e.gain_loss_eur for e in ev_sell_s if e.gain_loss_eur > 0)
            l_s = sum(-e.gain_loss_eur for e in ev_sell_s if e.gain_loss_eur < 0)
            net_s = max(0.0, g_s - l_s)
            t_s = round(net_s * RATE_STANDARD, 2)

            g_g = sum(e.gain_loss_eur for e in ev_sell_g if e.gain_loss_eur > 0)
            l_g = sum(-e.gain_loss_eur for e in ev_sell_g if e.gain_loss_eur < 0)
            net_g = max(0.0, g_g - l_g)
            t_g = round(net_g * RATE_GOVT, 2)

            divs = sum(e.gain_loss_eur for e in ev_div)
            ev_div_govt = [e for e in ev_div if e.is_government_bond]
            ev_div_std  = [e for e in ev_div if not e.is_government_bond]
            inc_tax = round(
                sum(e.gain_loss_eur for e in ev_div_govt) * RATE_GOVT
                + sum(e.gain_loss_eur for e in ev_div_std) * RATE_STANDARD,
                2,
            )

            setattr(report, f"{prefix}_gains_standard", g_s)
            setattr(report, f"{prefix}_losses_standard", l_s)
            setattr(report, f"{prefix}_tax_standard", t_s)
            setattr(report, f"{prefix}_gains_govt", g_g)
            setattr(report, f"{prefix}_losses_govt", l_g)
            setattr(report, f"{prefix}_tax_govt", t_g)
            setattr(report, f"{prefix}_dividends_eur", divs)
            setattr(report, f"{prefix}_income_tax", inc_tax)
            setattr(report, f"{prefix}_total_tax", round(t_s + t_g + inc_tax, 2))

        report.has_declaratory_accounts = any(not e.is_sostituto_imposta for e in year_events)

        reports.append(report)

    return reports


def simulate_sell(
    asset: Asset,
    quantity: float,
    current_price_eur: float,
    open_lots: list[_Lot],
) -> dict:
    """
    Stima l'impatto fiscale di una vendita ipotetica, usando i lotti FIFO aperti.
    """
    govt = _is_government_bond(asset)
    rate = RATE_GOVT if govt else RATE_STANDARD

    remaining = quantity
    cost_basis = 0.0
    for lot in open_lots:
        if remaining < 1e-10:
            break
        used = min(remaining, lot.quantity)
        cost_basis += used * lot.cost_per_unit_eur
        remaining -= used

    proceeds = quantity * current_price_eur
    gain_loss = proceeds - cost_basis
    estimated_tax = max(0.0, round(gain_loss * rate, 2))

    return {
        "asset_name": asset.name,
        "asset_type": asset.type if isinstance(asset.type, str) else asset.type.value,
        "quantity": quantity,
        "current_price_eur": current_price_eur,
        "proceeds_eur": proceeds,
        "cost_basis_eur": cost_basis,
        "gain_loss_eur": gain_loss,
        "tax_bracket": "government_bond" if govt else "standard",
        "tax_rate": rate,
        "estimated_tax_eur": estimated_tax,
        "net_proceeds_eur": proceeds - estimated_tax,
    }
