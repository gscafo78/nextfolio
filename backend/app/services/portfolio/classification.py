"""
Classificazione degli asset per sottostante (non per tipo di strumento).

- ``asset_class``: Azioni / Obbligazioni / Monetario / Crypto / Altro.
  Un ETF obbligazionario è "Obbligazioni", non "Azioni". Priorità: override
  manuale sull'asset → tipo strumento → nome dell'ETF/fondo → look-through
  settoriale.
- ``currency_exposure``: valute del sottostante (look-through dei paesi), con
  gestione degli ETF con copertura valutaria (hedged).
- ``maturity_date``: scadenza di un'obbligazione dal nome (es. "Btp Tf 1,65% Dc30").
- ``display_ticker``: ticker leggibile (mai l'ISIN).

Le funzioni lavorano su un dizionario ``asset_info`` (vedi ``build_asset_info``)
per poter essere usate sia con oggetti ORM sia nei test.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

EQUITY = "EQUITY"
BOND = "BOND"
MONEY_MARKET = "MONEY_MARKET"
CRYPTO = "CRYPTO"
OTHER = "OTHER"

ASSET_CLASSES = (EQUITY, BOND, MONEY_MARKET, CRYPTO, OTHER)
ASSET_CLASS_LABELS = {
    EQUITY: "Azioni",
    BOND: "Obbligazioni",
    MONEY_MARKET: "Monetario",
    CRYPTO: "Crypto",
    OTHER: "Altro",
}

UNCLASSIFIED_CURRENCY = "Non dettagliata"

_MONEY_RE = re.compile(
    r"\b(MONEY\s+MARKET|MONETARI[OA]|OVERNIGHT|€STR|ESTR|EONIA|SONIA|SOFR|CASH|ULTRA\s*SHORT|"
    r"LIQUIDIT[AÀ]|TREASURY\s+BILLS?|T-?BILLS?|0-[136]\s*M(ONTHS?)?)\b",
    re.IGNORECASE,
)
_BOND_RE = re.compile(
    r"\b(BONDS?|GOVT|GOVERNMENT|GOV|TREASURY|TREASURIES|AGGREGATE|AGG|CORPORATE|CORP|HIGH\s+YIELD|"
    r"FIXED\s+INCOME|OBBLIGAZ\w*|INFLATION[\s-]+LINKED|LINKERS?|BUND|GILTS?|SOVEREIGN|CREDIT|"
    r"COVERED|FLOATING\s+RATE|BTP|EMERGING\s+MARKETS?\s+DEBT|EM\s+DEBT)\b",
    re.IGNORECASE,
)
_OTHER_RE = re.compile(r"\b(GOLD|ORO|SILVER|ARGENTO|COMMODIT\w*|PHYSICAL|ETC|OIL|PETROLIO)\b", re.IGNORECASE)
# Bilanciati: "LifeStrategy 60% Equity", "60/40"
_EQUITY_SHARE_RE = re.compile(r"\b(\d{2})\s*%\s*(EQUITY|AZION\w*)\b", re.IGNORECASE)

_HEDGED_RE = re.compile(
    r"(\b(EUR|€)\s*[-(]?\s*(HEDGED|HDG|H)\b|\bHEDGED\s*(TO\s*)?(EUR|€)|\bEUR[\s-]*HEDGED\b|"
    r"\b(HEDGED|HDG)\b.*\b(EUR|€)\b|\(EUR\s*H\))",
    re.IGNORECASE,
)
_NAME_CCY = [
    ("USD", re.compile(r"\b(USD|US\$|U\.S\.\s+DOLLAR|DOLLAR)\b", re.IGNORECASE)),
    ("EUR", re.compile(r"(€|\bEUR\b|\bEURO\b|\bEUROZONE\b|\bEURO\s+AREA\b|\bEMU\b)", re.IGNORECASE)),
    ("GBP", re.compile(r"\b(GBP|STERLING|GILTS?)\b", re.IGNORECASE)),
    ("JPY", re.compile(r"\b(JPY|YEN)\b", re.IGNORECASE)),
    ("CHF", re.compile(r"\bCHF\b", re.IGNORECASE)),
]

_EUROZONE = {
    "AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT", "LT", "LU", "LV", "MT", "NL",
    "PT", "SI", "SK",
    "Austria", "Belgium", "Cyprus", "Germany", "Estonia", "Spain", "Finland", "France", "Greece", "Croatia",
    "Ireland", "Italy", "Lithuania", "Luxembourg", "Latvia", "Malta", "Netherlands", "Portugal", "Slovenia",
    "Slovakia",
}
_COUNTRY_CCY = {
    "US": "USD", "United States": "USD", "GB": "GBP", "United Kingdom": "GBP", "JP": "JPY", "Japan": "JPY",
    "CH": "CHF", "Switzerland": "CHF", "CA": "CAD", "Canada": "CAD", "AU": "AUD", "Australia": "AUD",
}
_DEVELOPED_OTHER = {
    "SE", "Sweden", "DK", "Denmark", "NO", "Norway", "NZ", "New Zealand", "HK", "Hong Kong", "SG", "Singapore",
    "IL", "Israel",
}
_EMERGING = {
    "CN", "China", "TW", "Taiwan", "KR", "South Korea", "Korea", "IN", "India", "BR", "Brazil", "ZA",
    "South Africa", "MX", "Mexico", "SA", "Saudi Arabia", "ID", "Indonesia", "TH", "Thailand", "MY",
    "Malaysia", "PL", "Poland", "TR", "Turkey", "AE", "United Arab Emirates", "QA", "Qatar", "CL", "Chile",
    "PH", "Philippines", "CO", "Colombia", "PE", "Peru", "HU", "Hungary", "CZ", "Czech Republic", "KW",
    "Kuwait", "EG", "Egypt", "GR_EM",
}

_IT_MONTHS = {"GN": 1, "GE": 1, "FB": 2, "MZ": 3, "AP": 4, "MG": 5, "GI": 6, "GU": 6, "LG": 7, "AG": 8,
              "ST": 9, "OT": 10, "NV": 11, "DC": 12}
_MONTH_CODE_RE = re.compile(r"\b(GN|GE|FB|MZ|AP|MG|GI|GU|LG|AG|ST|OT|NV|DC)\s?(\d{2})\b", re.IGNORECASE)
_DMY_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})\b")
_YEAR_RE = re.compile(r"\b(20[2-9]\d)\b")


def _type(a: dict) -> str:
    t = a.get("type", "OTHER")
    return t if isinstance(t, str) else t.value


def _eff(a: dict, key: str):
    v = a.get(f"{key}_override")
    return v if v is not None else a.get(key)


def build_asset_info(asset) -> dict:
    """Dizionario con i campi usati da allocazione, X-Ray e classificazione."""
    t = getattr(asset, "type", "OTHER")
    g = lambda k: getattr(asset, k, None)  # noqa: E731
    return {
        "type": t if isinstance(t, str) else t.value,
        "name": g("name") or "",
        "symbol": g("symbol"),
        "isin": g("isin"),
        "yahoo_ticker": g("yahoo_ticker"),
        "currency": g("currency"),
        "sectors": g("sectors"),
        "countries": g("countries"),
        "sectors_override": g("sectors_override"),
        "countries_override": g("countries_override"),
        "asset_class_override": g("asset_class_override"),
    }


# ── Asset class ───────────────────────────────────────────────────────────────

def asset_class_weights(a: dict) -> dict[str, float]:
    """Ripartizione dell'asset per classe (somma 1). Gli ETF bilanciati sono divisi."""
    override = a.get("asset_class_override")
    if override in ASSET_CLASSES:
        return {override: 1.0}

    t = _type(a)
    if t in ("STOCK", "REIT"):
        return {EQUITY: 1.0}
    if t == "BOND":
        return {BOND: 1.0}
    if t == "CRYPTO":
        return {CRYPTO: 1.0}
    if t == "COMMODITY":
        return {OTHER: 1.0}

    name = a.get("name") or ""
    if t == "OTHER":
        return {MONEY_MARKET: 1.0} if _MONEY_RE.search(name) else {OTHER: 1.0}

    # ETF / fondi: dal nome, poi dal look-through settoriale
    m = _EQUITY_SHARE_RE.search(name)
    if m:
        eq = min(max(int(m.group(1)) / 100, 0.0), 1.0)
        return {EQUITY: eq, BOND: 1.0 - eq} if eq < 1 else {EQUITY: 1.0}
    if _MONEY_RE.search(name):
        return {MONEY_MARKET: 1.0}
    if _BOND_RE.search(name):
        return {BOND: 1.0}
    if _OTHER_RE.search(name):
        return {OTHER: 1.0}
    sectors = _eff(a, "sectors") or []
    bond_w = sum(float(s.get("weight", 0)) for s in sectors if str(s.get("name", "")).lower() in ("bonds", "bond"))
    if bond_w > 0.5:
        return {BOND: 1.0}
    return {EQUITY: 1.0}


def asset_class(a: dict) -> str:
    """Classe prevalente."""
    w = asset_class_weights(a)
    return max(w, key=w.get)


def is_diversified_fund(a: dict) -> bool:
    """ETF/fondi: diversificati, esclusi dalla regola di concentrazione per titolo."""
    return _type(a) == "ETF"


# ── Valute ────────────────────────────────────────────────────────────────────

def _country_currency(code: str) -> str:
    if code in _EUROZONE:
        return "EUR"
    if code in _COUNTRY_CCY:
        return _COUNTRY_CCY[code]
    if code in _EMERGING:
        return "Valute emergenti"
    if code in _DEVELOPED_OTHER:
        return "Altre sviluppate"
    return UNCLASSIFIED_CURRENCY


def _name_currency(name: str) -> str | None:
    for ccy, rx in _NAME_CCY:
        if rx.search(name):
            return ccy
    return None


def currency_exposure(a: dict) -> dict[str, float]:
    """Esposizione valutaria del sottostante (pesi che sommano a 1)."""
    name = a.get("name") or ""
    if _HEDGED_RE.search(name):
        return {"EUR": 1.0}
    cls = asset_class(a)
    t = _type(a)
    if cls == CRYPTO:
        return {"Crypto": 1.0}
    if t in ("BOND", "OTHER") or cls == MONEY_MARKET:
        return {(_name_currency(name) if t == "ETF" else None) or a.get("currency") or "EUR": 1.0}
    if cls == OTHER:
        return {"USD": 1.0}  # materie prime quotate in dollari
    if cls == BOND:
        # ETF obbligazionari: la valuta dell'indice è nel nome (es. "USD High Yield", "€ Aggregate")
        ccy = _name_currency(name)
        if ccy:
            return {ccy: 1.0}

    countries = _eff(a, "countries") or []
    if countries:
        out: dict[str, float] = {}
        total = 0.0
        for c in countries:
            w = float(c.get("weight", 0.0))
            if w <= 0:
                continue
            ccy = _country_currency(c.get("code") or c.get("name") or "")
            out[ccy] = out.get(ccy, 0.0) + w
            total += w
        if total < 0.999:
            out[UNCLASSIFIED_CURRENCY] = out.get(UNCLASSIFIED_CURRENCY, 0.0) + (1.0 - total)
        elif total > 1.001:
            out = {k: v / total for k, v in out.items()}
        return out
    if t == "STOCK" or t == "REIT":
        return {a.get("currency") or "EUR": 1.0}
    return {UNCLASSIFIED_CURRENCY: 1.0}


# ── Obbligazioni ──────────────────────────────────────────────────────────────

def maturity_from_name(name: str) -> date | None:
    """Scadenza dal nome: "Dc30" (codici mese Borsa Italiana), "15/12/2030" o un anno."""
    if not name:
        return None
    m = _MONTH_CODE_RE.search(name)
    if m:
        month = _IT_MONTHS[m.group(1).upper()]
        year = 2000 + int(m.group(2))
        return date(year, month, calendar.monthrange(year, month)[1])
    m = _DMY_RE.search(name)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return date(y, mo, d)
        except ValueError:
            pass
    m = _YEAR_RE.search(name)
    if m:
        return date(int(m.group(1)), 12, 31)
    return None


def residual_months(maturity: date | None, today: date | None = None) -> float | None:
    if maturity is None:
        return None
    today = today or date.today()
    return (maturity - today).days / 30.4375


# ── Ticker ────────────────────────────────────────────────────────────────────

def display_ticker(a: dict) -> str:
    """Ticker leggibile: il simbolo se diverso dall'ISIN, altrimenti il ticker Yahoo senza suffisso di borsa."""
    sym = (a.get("symbol") or "").strip()
    isin = (a.get("isin") or "").strip()
    if sym and sym.upper() != isin.upper():
        return sym
    yt = (a.get("yahoo_ticker") or "").strip()
    return yt.split(".")[0] if yt else ""


# ── Broker ────────────────────────────────────────────────────────────────────

_BROKERS = [
    ("Trade Republic", r"trade\s*republic|traderepublic"),
    ("Scalable Capital", r"scalable"),
    ("Fineco", r"fineco"),
    ("Directa", r"directa"),
    ("Degiro", r"degiro"),
    ("Interactive Brokers", r"interactive\s*brokers|\bibkr\b"),
    ("Banca Sella", r"\bsella\b"),
    ("Webank", r"webank"),
    ("Intesa Sanpaolo", r"intesa|isybank"),
    ("UniCredit", r"unicredit"),
    ("BG Saxo", r"saxo"),
    ("Moneyfarm", r"moneyfarm"),
    ("Banca Mediolanum", r"mediolanum"),
    ("Revolut", r"revolut"),
    ("eToro", r"etoro"),
    ("XTB", r"\bxtb\b"),
    ("Freedom24", r"freedom24|freedom\s*finance"),
    ("Banca Generali", r"banca\s*generali"),
    ("Poste Italiane", r"poste|bancoposta"),
    ("Binance", r"binance"),
    ("Coinbase", r"coinbase"),
    ("Young Platform", r"young\s*platform"),
]


def infer_broker(name: str | None, url: str | None = None) -> str | None:
    text = f"{name or ''} {url or ''}"
    for label, rx in _BROKERS:
        if re.search(rx, text, re.IGNORECASE):
            return label
    return None
