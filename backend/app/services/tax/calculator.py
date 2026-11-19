"""
Tax engine per la normativa italiana (persone fisiche, redditi finanziari).

Categorie di realizzo (``TaxEvent.category``):
  - ``standard``         azioni, obbligazioni societarie, ETC/ETN, REIT, altro
                         → redditi diversi, 26%
  - ``government_bond``  titoli di Stato italiani ed equiparati (white list,
                         sovranazionali) → redditi diversi, imponibili al 48,08%
                         (12,5/26): aliquota effettiva 12,5%
  - ``fund``             ETF / OICR: le *plusvalenze* sono redditi di capitale
                         (26% pieno, NON compensabili con lo zainetto); le
                         *minusvalenze* sono redditi diversi e alimentano lo zainetto
  - ``crypto``           cripto-attività (art. 67 c.1 c-sexies TUIR): 26% fino al
                         2025, 33% dal 2026 (L. 207/2024); compensazione e riporto
                         nel proprio zainetto

Zainetto fiscale (minusvalenze):
  - unico per i redditi diversi al 26%: plus/minus su titoli di Stato vi entrano
    ponderate al 48,08% (D.Lgs. 461/97, DM 13/12/2011, DL 66/2014)
  - zainetto separato per le cripto-attività (art. 68 c.9-bis TUIR)
  - riporto fino al quarto periodo d'imposta successivo

Costo fiscale: costo medio ponderato (art. 68 c.6 TUIR) in entrambi i regimi.
  - regime amministrato → un pool per (conto, asset): ogni intermediario tiene
    il proprio costo medio
  - regime dichiarativo → un pool per asset su tutti i conti dichiarativi

Semplificazioni note:
  - lo zainetto è unico per tutti i conti (in realtà ogni intermediario in
    regime amministrato ha il proprio zainetto)
  - ETF che investono in titoli di Stato: la quota (``govt_bond_share`` sull'asset,
    comunicata semestralmente dall'emittente) va inserita a mano; non è aggiornata
    automaticamente
  - plus/minus su valuta (art. 67 c.1-ter, LIFO) non calcolate
  - dividendi, cedole e interessi sono mostrati come redditi informativi
"""
import datetime
import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionType

RATE_STANDARD = 0.26
RATE_GOVT = 0.125
RATE_CRYPTO_FROM_2026 = 0.33
GOVT_WEIGHT = RATE_GOVT / RATE_STANDARD  # 0,480769… → "48,08%"

CATEGORY_STANDARD = "standard"
CATEGORY_GOVT = "government_bond"
CATEGORY_FUND = "fund"
CATEGORY_CRYPTO = "crypto"

CARRYFORWARD_YEARS = 4


def crypto_rate(year: int) -> float:
    return RATE_CRYPTO_FROM_2026 if year >= 2026 else RATE_STANDARD


# ── Riconoscimento titoli di Stato ────────────────────────────────────────────

# Emissioni dello Stato italiano
_IT_GOVT = re.compile(
    r"\b(BTP|BOT|CCT|CTZ|CCTEU|BTPI|BTP\s*-?\s*(ITALIA|VALORE|FUTURA|PIU|PIÙ|GREEN|€I)|"
    r"BUONI\s+(POLIENNALI|ORDINARI)|REPUBBLICA\s+ITALIANA|ITALY\s+(GOVT|GOVERNMENT|REP))\b",
    re.IGNORECASE,
)
# Titoli di Stato esteri (Paesi white list) e organismi sovranazionali
_FOREIGN_GOVT = re.compile(
    r"\b(BUND|BOBL|SCHATZ|BUNDESREPUBLIK|BUNDESANLEIHE|OAT|BTAN|BONOS|OBLIGACIONES\s+DEL\s+ESTADO|"
    r"GILT|TREASURY|TREASURIES|T-?BILL|T-?NOTE|T-?BOND|US\s+TREAS|"
    r"REPUBLIC\s+OF|REPUBLIQUE|REP\.?\s+OF|KINGDOM\s+OF|GOVERNMENT\s+OF|STATE\s+OF|"
    r"EIB|BEI|EUROPEAN\s+INVESTMENT\s+BANK|BANCA\s+EUROPEA\s+(PER\s+GLI\s+)?INVESTIMENTI|"
    r"WORLD\s+BANK|IBRD|BIRS|BIRD|EBRD|BERS|EUROPEAN\s+UNION|UNIONE\s+EUROPEA|"
    r"ESM|EFSF|COUNCIL\s+OF\s+EUROPE|CEB|ASIAN\s+DEVELOPMENT\s+BANK|INTER-?AMERICAN\s+DEVELOPMENT|"
    r"AFRICAN\s+DEVELOPMENT\s+BANK|INTERNATIONAL\s+FINANCE\s+CORP)\b",
    re.IGNORECASE,
)


def _asset_type(asset) -> str:
    return asset.type if isinstance(asset.type, str) else asset.type.value


def _is_government_bond(asset: Asset) -> bool:
    """Titolo di Stato o equiparato → plus/minus al 48,08%, cedole al 12,5%.

    Priorità: flag manuale ``govt_bond_override`` sull'asset; altrimenti
    riconoscimento dal nome (BTP/BOT/CCT/CTZ…, Bund/OAT/Treasury…, BEI/BIRS…).
    L'ISIN da solo non basta: anche le obbligazioni societarie italiane hanno
    ISIN ``IT`` e scontano il 26%.
    """
    override = getattr(asset, "govt_bond_override", None)
    if override is not None:
        return bool(override)
    if _asset_type(asset) != "BOND":
        return False
    name = f"{getattr(asset, 'name', '') or ''} {getattr(asset, 'symbol', '') or ''}"
    return bool(_IT_GOVT.search(name) or _FOREIGN_GOVT.search(name))


def fund_taxable_fraction(asset: Asset) -> float:
    """Quota imponibile per ETF/OICR: la parte in titoli di Stato vale il 48,08%."""
    share = getattr(asset, "govt_bond_share", None) or 0.0
    share = min(max(float(share), 0.0), 1.0)
    return 1.0 - share * (1.0 - GOVT_WEIGHT)


def tax_category(asset: Asset) -> str:
    if _is_government_bond(asset):
        return CATEGORY_GOVT
    t = _asset_type(asset)
    if t == "CRYPTO":
        return CATEGORY_CRYPTO
    if t == "ETF":
        return CATEGORY_FUND
    return CATEGORY_STANDARD


# ── Strutture dati interne ────────────────────────────────────────────────────

@dataclass
class _WACLot:
    """Pool a costo medio ponderato (PMC)."""
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
        """Restituisce il costo fiscale al PMC e aggiorna il pool."""
        cost_of_sold = min(qty, self.quantity) * self.avg_cost_per_unit
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
    calculation_method: str = "PMC"
    category: str | None = None          # derivata da asset_type/is_government_bond se None
    # ETF/OICR con quota di titoli di Stato white list: quota imponibile del risultato
    taxable_fraction: float = 1.0

    def __post_init__(self):
        if self.category is None:
            if self.is_government_bond:
                self.category = CATEGORY_GOVT
            elif self.asset_type == "CRYPTO":
                self.category = CATEGORY_CRYPTO
            elif self.asset_type == "ETF":
                self.category = CATEGORY_FUND
            else:
                self.category = CATEGORY_STANDARD

    @property
    def tax_rate(self) -> float:
        """Aliquota effettiva sul guadagno."""
        if self.tx_type != "SELL":
            return RATE_GOVT if self.is_government_bond else RATE_STANDARD
        if self.category == CATEGORY_GOVT:
            return RATE_GOVT
        if self.category == CATEGORY_CRYPTO:
            return crypto_rate(self.date.year)
        if self.category == CATEGORY_FUND:
            return RATE_STANDARD * self.taxable_fraction
        return RATE_STANDARD

    @property
    def tax_bracket(self) -> str:
        return self.category


@dataclass
class CarryForwardEntry:
    year: int
    amount: float  # importo residuo (positivo = perdita disponibile)
    expires_year: int  # ultimo anno di utilizzo (year + 4)


@dataclass
class AnnualTaxReport:
    year: int

    # Redditi diversi al 26% — importi reali
    gains_standard: float = 0.0
    losses_standard: float = 0.0
    # Titoli di Stato — importi reali (entrano nello zainetto al 48,08%)
    gains_govt: float = 0.0
    losses_govt: float = 0.0
    govt_weight: float = GOVT_WEIGHT
    # ETF/OICR: minusvalenze nello zainetto, plusvalenze tassate a parte
    losses_funds: float = 0.0
    gains_funds: float = 0.0
    tax_funds: float = 0.0

    # Zainetto unico 26% (importi già ponderati)
    taxable_gains_standard: float = 0.0   # gains_standard + gains_govt × 48,08%
    taxable_losses_standard: float = 0.0  # losses_standard + losses_govt × 48,08% + losses_funds
    carryforward_applied_standard: float = 0.0
    net_taxable_standard: float = 0.0
    tax_standard: float = 0.0
    new_carryforward_standard: float = 0.0
    prior_carryforward_standard: list[CarryForwardEntry] = field(default_factory=list)

    # Cripto-attività (zainetto separato)
    gains_crypto: float = 0.0
    losses_crypto: float = 0.0
    crypto_rate: float = RATE_STANDARD
    carryforward_applied_crypto: float = 0.0
    net_taxable_crypto: float = 0.0
    tax_crypto: float = 0.0
    new_carryforward_crypto: float = 0.0
    prior_carryforward_crypto: list[CarryForwardEntry] = field(default_factory=list)

    # Reddito (cedole, dividendi, interessi)
    dividends_eur: float = 0.0
    coupons_govt_eur: float = 0.0
    coupons_standard_eur: float = 0.0
    interests_eur: float = 0.0
    income_tax_eur: float = 0.0
    administered_income_tax: float = 0.0
    declaratory_income_tax: float = 0.0

    total_tax_due: float = 0.0

    events: list[TaxEvent] = field(default_factory=list)

    # Breakdown per regime (sugli eventi dell'anno, senza zainetto pregresso)
    administered_gains_standard: float = 0.0
    administered_losses_standard: float = 0.0
    administered_gains_govt: float = 0.0
    administered_losses_govt: float = 0.0
    administered_gains_funds: float = 0.0
    administered_losses_funds: float = 0.0
    administered_gains_crypto: float = 0.0
    administered_losses_crypto: float = 0.0
    administered_taxable_gains: float = 0.0
    administered_taxable_losses: float = 0.0
    administered_tax_standard: float = 0.0
    administered_tax_funds: float = 0.0
    administered_tax_crypto: float = 0.0
    administered_dividends_eur: float = 0.0
    administered_total_tax: float = 0.0

    declaratory_gains_standard: float = 0.0
    declaratory_losses_standard: float = 0.0
    declaratory_gains_govt: float = 0.0
    declaratory_losses_govt: float = 0.0
    declaratory_gains_funds: float = 0.0
    declaratory_losses_funds: float = 0.0
    declaratory_gains_crypto: float = 0.0
    declaratory_losses_crypto: float = 0.0
    declaratory_taxable_gains: float = 0.0
    declaratory_taxable_losses: float = 0.0
    declaratory_tax_standard: float = 0.0
    declaratory_tax_funds: float = 0.0
    declaratory_tax_crypto: float = 0.0
    declaratory_dividends_eur: float = 0.0
    declaratory_total_tax: float = 0.0

    has_declaratory_accounts: bool = False


# ── Engine principale ─────────────────────────────────────────────────────────

def _pool_key(tx) -> tuple:
    """Pool PMC: per conto in amministrato, unico per asset in dichiarativo."""
    if getattr(tx.account, "is_sostituto_imposta", False):
        return ("A", tx.account_id, tx.asset_id)
    return ("D", tx.asset_id)


def _replay(transactions: list[Transaction]) -> tuple[list[TaxEvent], dict[tuple, _WACLot]]:
    pools: dict[tuple, _WACLot] = defaultdict(_WACLot)
    events: list[TaxEvent] = []

    for tx in sorted(transactions, key=lambda t: (t.date, t.id)):
        asset: Asset = tx.asset
        govt = _is_government_bond(asset)
        sostituto = getattr(tx.account, "is_sostituto_imposta", False)
        asset_type_str = _asset_type(asset)
        amount = tx.quantity * tx.price * tx.exchange_rate

        if tx.type == TransactionType.BUY:
            pools[_pool_key(tx)].buy(tx.quantity, amount + tx.fee)

        elif tx.type == TransactionType.SELL:
            proceeds = amount - tx.fee
            cost_of_sold = pools[_pool_key(tx)].sell(tx.quantity)
            events.append(TaxEvent(
                date=tx.date, asset_id=tx.asset_id, asset_name=asset.name, asset_type=asset_type_str,
                tx_type="SELL", quantity=tx.quantity, proceeds_eur=proceeds, cost_eur=cost_of_sold,
                gain_loss_eur=proceeds - cost_of_sold, is_government_bond=govt,
                is_sostituto_imposta=sostituto, calculation_method="PMC", category=tax_category(asset),
                taxable_fraction=fund_taxable_fraction(asset) if tax_category(asset) == CATEGORY_FUND else 1.0,
            ))

        elif tx.type in (TransactionType.DIVIDEND, TransactionType.COUPON, TransactionType.INTEREST):
            income = amount - tx.fee
            kind = tx.type.value if hasattr(tx.type, "value") else str(tx.type)
            events.append(TaxEvent(
                date=tx.date, asset_id=tx.asset_id, asset_name=asset.name, asset_type=asset_type_str,
                tx_type=kind, quantity=None, proceeds_eur=income, cost_eur=None, gain_loss_eur=income,
                # solo le cedole dei titoli di Stato hanno l'aliquota agevolata
                is_government_bond=govt and kind == "COUPON",
                is_sostituto_imposta=sostituto,
            ))

    return events, pools


def compute_tax_events(transactions: list[Transaction]) -> list[TaxEvent]:
    """Eventi fiscali in ordine cronologico, costo fiscale al PMC."""
    return _replay(transactions)[0]


def open_cost_pools(transactions: list[Transaction]) -> dict[tuple, _WACLot]:
    """Pool PMC aperti a oggi: chiave ("A", account_id, asset_id) o ("D", asset_id)."""
    return {k: v for k, v in _replay(transactions)[1].items() if v.quantity > 1e-10}


def _apply_carryforward(
    gains: float,
    pool: dict[int, float],
    current_year: int,
) -> tuple[float, float, list[CarryForwardEntry]]:
    """
    Applica lo zainetto disponibile alle plusvalenze nette dell'anno.

    Restituisce (importo usato, imponibile residuo, stato dello zainetto PRIMA
    dell'applicazione).
    """
    for y in [k for k in pool if current_year - k > CARRYFORWARD_YEARS]:
        del pool[y]
    snapshot = [
        CarryForwardEntry(year=y, amount=a, expires_year=y + CARRYFORWARD_YEARS)
        for y, a in sorted(pool.items())
        if a > 1e-6
    ]

    applied = 0.0
    remaining = gains
    for y in sorted(pool):
        if remaining < 1e-6:
            break
        use = min(pool[y], remaining)
        pool[y] -= use
        applied += use
        remaining -= use

    for y in [k for k in pool if pool[k] < 1e-6]:
        del pool[y]

    return applied, max(0.0, gains - applied), snapshot


@dataclass
class _Totals:
    gains_standard: float = 0.0
    losses_standard: float = 0.0
    gains_govt: float = 0.0
    losses_govt: float = 0.0
    gains_funds: float = 0.0
    losses_funds: float = 0.0
    gains_crypto: float = 0.0
    losses_crypto: float = 0.0
    taxable_gains_funds: float = 0.0    # ridotte per la quota titoli di Stato
    taxable_losses_funds: float = 0.0

    @property
    def taxable_gains(self) -> float:
        return self.gains_standard + self.gains_govt * GOVT_WEIGHT

    @property
    def taxable_losses(self) -> float:
        return self.losses_standard + self.losses_govt * GOVT_WEIGHT + self.taxable_losses_funds


def _totals(events: list[TaxEvent]) -> _Totals:
    t = _Totals()
    for e in events:
        if e.tx_type != "SELL":
            continue
        key = {CATEGORY_GOVT: "govt", CATEGORY_FUND: "funds", CATEGORY_CRYPTO: "crypto"}.get(e.category, "standard")
        if e.gain_loss_eur > 0:
            setattr(t, f"gains_{key}", getattr(t, f"gains_{key}") + e.gain_loss_eur)
            if key == "funds":
                t.taxable_gains_funds += e.gain_loss_eur * e.taxable_fraction
        elif e.gain_loss_eur < 0:
            setattr(t, f"losses_{key}", getattr(t, f"losses_{key}") - e.gain_loss_eur)
            if key == "funds":
                t.taxable_losses_funds -= e.gain_loss_eur * e.taxable_fraction
    return t


def _compensate(gains: float, losses: float, pool: dict[int, float], year: int):
    """Compensazione nell'anno, poi zainetto pregresso. Aggiorna ``pool``."""
    net_gains = max(0.0, gains - losses)
    net_loss = max(0.0, losses - gains)
    applied, net_taxable, snapshot = _apply_carryforward(net_gains, pool, year)
    if net_loss > 1e-6:
        pool[year] = pool.get(year, 0.0) + net_loss
    return applied, net_taxable, net_loss, snapshot


def build_annual_reports(events: list[TaxEvent]) -> list[AnnualTaxReport]:
    """Report fiscale per anno con zainetto (26% unico + cripto) su 4 anni."""
    if not events:
        return []

    by_year: dict[int, list[TaxEvent]] = defaultdict(list)
    for ev in events:
        by_year[ev.date.year].append(ev)

    pool_standard: dict[int, float] = {}
    pool_crypto: dict[int, float] = {}
    reports: list[AnnualTaxReport] = []

    for year in range(min(by_year), max(by_year) + 1):
        year_events = by_year.get(year, [])
        if not year_events:
            continue
        r = AnnualTaxReport(year=year, events=year_events)
        t = _totals(year_events)

        # ── Redditi diversi 26% (titoli di Stato al 48,08%, minus ETF incluse)
        r.gains_standard, r.losses_standard = t.gains_standard, t.losses_standard
        r.gains_govt, r.losses_govt = t.gains_govt, t.losses_govt
        r.losses_funds = t.losses_funds
        r.taxable_gains_standard = t.taxable_gains
        r.taxable_losses_standard = t.taxable_losses
        (r.carryforward_applied_standard, r.net_taxable_standard,
         r.new_carryforward_standard, r.prior_carryforward_standard) = _compensate(
            t.taxable_gains, t.taxable_losses, pool_standard, year)
        r.tax_standard = round(r.net_taxable_standard * RATE_STANDARD, 2)

        # ── Cripto-attività
        r.gains_crypto, r.losses_crypto = t.gains_crypto, t.losses_crypto
        r.crypto_rate = crypto_rate(year)
        (r.carryforward_applied_crypto, r.net_taxable_crypto,
         r.new_carryforward_crypto, r.prior_carryforward_crypto) = _compensate(
            t.gains_crypto, t.losses_crypto, pool_crypto, year)
        r.tax_crypto = round(r.net_taxable_crypto * r.crypto_rate, 2)

        # ── ETF/OICR: plusvalenze = redditi di capitale, nessuna compensazione
        r.gains_funds = t.gains_funds
        r.tax_funds = round(t.taxable_gains_funds * RATE_STANDARD, 2)

        # ── Redditi (informativi)
        r.dividends_eur = sum(e.gain_loss_eur for e in year_events if e.tx_type == "DIVIDEND")
        r.coupons_govt_eur = sum(e.gain_loss_eur for e in year_events if e.tx_type == "COUPON" and e.is_government_bond)
        r.coupons_standard_eur = sum(e.gain_loss_eur for e in year_events if e.tx_type == "COUPON" and not e.is_government_bond)
        r.interests_eur = sum(e.gain_loss_eur for e in year_events if e.tx_type == "INTEREST")
        r.income_tax_eur = round(
            (r.dividends_eur + r.coupons_standard_eur + r.interests_eur) * RATE_STANDARD
            + r.coupons_govt_eur * RATE_GOVT,
            2,
        )

        r.total_tax_due = round(r.tax_standard + r.tax_crypto + r.tax_funds, 2)

        # ── Breakdown per regime (solo eventi dell'anno)
        for administered in (True, False):
            prefix = "administered" if administered else "declaratory"
            evs = [e for e in year_events if e.is_sostituto_imposta == administered]
            tt = _totals(evs)
            tax_s = round(max(0.0, tt.taxable_gains - tt.taxable_losses) * RATE_STANDARD, 2)
            tax_c = round(max(0.0, tt.gains_crypto - tt.losses_crypto) * crypto_rate(year), 2)
            tax_f = round(tt.taxable_gains_funds * RATE_STANDARD, 2)
            income = [e for e in evs if e.tx_type in ("DIVIDEND", "COUPON", "INTEREST")]
            inc_tax = round(sum(e.gain_loss_eur * e.tax_rate for e in income), 2)
            for name in ("gains_standard", "losses_standard", "gains_govt", "losses_govt",
                         "gains_funds", "losses_funds", "gains_crypto", "losses_crypto"):
                setattr(r, f"{prefix}_{name}", getattr(tt, name))
            setattr(r, f"{prefix}_taxable_gains", tt.taxable_gains)
            setattr(r, f"{prefix}_taxable_losses", tt.taxable_losses)
            setattr(r, f"{prefix}_tax_standard", tax_s)
            setattr(r, f"{prefix}_tax_crypto", tax_c)
            setattr(r, f"{prefix}_tax_funds", tax_f)
            setattr(r, f"{prefix}_dividends_eur", sum(e.gain_loss_eur for e in income))
            setattr(r, f"{prefix}_income_tax", inc_tax)
            setattr(r, f"{prefix}_total_tax", round(tax_s + tax_c + tax_f + inc_tax, 2))

        r.has_declaratory_accounts = any(not e.is_sostituto_imposta for e in year_events)
        reports.append(r)

    return reports


def simulate_sell(
    asset: Asset,
    quantity: float,
    current_price_eur: float,
    avg_cost_per_unit_eur: float,
    year: int | None = None,
) -> dict:
    """Stima l'imposta di una vendita ipotetica al costo medio ponderato.

    Non considera lo zainetto: un guadagno è tassato per intero (per gli ETF è
    comunque così), una perdita non genera imposta.
    """
    year = year or datetime.date.today().year
    category = tax_category(asset)
    rate = {
        CATEGORY_GOVT: RATE_GOVT,
        CATEGORY_CRYPTO: crypto_rate(year),
        CATEGORY_FUND: RATE_STANDARD * fund_taxable_fraction(asset),
    }.get(category, RATE_STANDARD)

    proceeds = quantity * current_price_eur
    cost_basis = quantity * avg_cost_per_unit_eur
    gain_loss = proceeds - cost_basis
    estimated_tax = max(0.0, round(gain_loss * rate, 2))

    return {
        "asset_name": asset.name,
        "asset_type": _asset_type(asset),
        "quantity": quantity,
        "current_price_eur": current_price_eur,
        "proceeds_eur": proceeds,
        "cost_basis_eur": cost_basis,
        "gain_loss_eur": gain_loss,
        "tax_bracket": category,
        "tax_rate": rate,
        "estimated_tax_eur": estimated_tax,
        "net_proceeds_eur": proceeds - estimated_tax,
    }
