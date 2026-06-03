"""
Enrichment automatico dei dettagli cedola da Borsa Italiana.

Fonte: https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/dati-completi.html?isin={ISIN}&mic=MOTX

Campi estratti (verificati sul BTP IT0005413171):
  - Scadenza             → maturity_date  (formato dd/mm/yy)
  - Tasso Cedola Periodale → tasso per periodo (es. 0,825 = 0.825%)
  - Data Godimento       → issue_date / base per first_coupon_date
  - Nome                 → contiene il tasso annuo es. "Btp Tf 1,65% Dc30 Eur"

Nota: "Tasso Cedola su base Annua" è sempre vuoto nella pagina — si ricava da Nome e Periodale.
"""
import re
from datetime import date

import httpx
from dateutil.relativedelta import relativedelta

from app.models.bond_detail import CouponFrequency

_TIMEOUT = 12.0
_BASE_URL = "https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/dati-completi.html"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.borsaitaliana.it/",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "it-IT,it;q=0.9",
}


class BIEnrichmentResult:
    __slots__ = (
        "coupon_rate", "coupon_frequency", "first_coupon_date",
        "maturity_date", "issue_date", "face_value",
    )

    def __init__(
        self,
        coupon_rate: float,
        coupon_frequency: CouponFrequency,
        first_coupon_date: date,
        maturity_date: date | None,
        issue_date: date | None,
        face_value: float = 100.0,
    ):
        self.coupon_rate = coupon_rate
        self.coupon_frequency = coupon_frequency
        self.first_coupon_date = first_coupon_date
        self.maturity_date = maturity_date
        self.issue_date = issue_date
        self.face_value = face_value


def _parse_it_date(s: str) -> date | None:
    """Converte dd/mm/yy o dd/mm/yyyy in date."""
    s = s.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return date.fromisoformat(__import__("datetime").datetime.strptime(s, fmt).date().isoformat())
        except ValueError:
            continue
    return None


def _parse_it_float(s: str) -> float | None:
    """Converte '0,825' o '1.65' in float."""
    try:
        return float(s.strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _extract_cells(html: str) -> dict[str, str]:
    """Estrae coppie label→valore dalle celle <td> della tabella dati."""
    # Estrae il contenuto di ogni <td>
    cells_raw = re.findall(r"<td[^>]*>\s*(.*?)\s*</td>", html, re.S | re.I)
    cells = []
    for c in cells_raw:
        text = re.sub(r"<[^>]+>", " ", c)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cells.append(text)

    # Le celle sono in coppie: label, valore
    result: dict[str, str] = {}
    for i in range(len(cells) - 1):
        label = cells[i].lower().strip()
        value = cells[i + 1].strip()
        # Evita di usare una cella che è a sua volta una label come valore
        known_labels = {
            "nome", "codice isin", "scadenza", "tasso cedola periodale",
            "tasso cedola su base annua", "data godimento", "tipo bond",
            "lotto minimo", "valuta di negoziazione", "mercato",
        }
        if label in known_labels and value.lower() not in known_labels:
            result[label] = value
    return result


def _infer_frequency(annual: float, periodic: float) -> CouponFrequency:
    if periodic < 1e-10:
        return CouponFrequency.SEMI_ANNUAL
    ratio = round(annual / periodic)
    return {
        1:  CouponFrequency.ANNUAL,
        2:  CouponFrequency.SEMI_ANNUAL,
        4:  CouponFrequency.QUARTERLY,
        12: CouponFrequency.MONTHLY,
    }.get(ratio, CouponFrequency.SEMI_ANNUAL)


async def fetch_bond_details(isin: str, mic: str = "MOTX") -> BIEnrichmentResult | None:
    """
    Scarica e analizza la pagina dati-completi di Borsa Italiana per l'ISIN dato.
    Restituisce BIEnrichmentResult o None se i dati non sono presenti.
    """
    url = _BASE_URL
    params = {"isin": isin, "mic": mic}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=_HEADERS)
            resp.raise_for_status()
    except httpx.HTTPError:
        return None

    html = resp.text
    cells = _extract_cells(html)

    # ── Tasso cedola periodale ──────────────────────────────────────────────
    periodic_str = cells.get("tasso cedola periodale", "")
    periodic_pct = _parse_it_float(periodic_str)   # es. 0.825 (già in %)
    if periodic_pct is None:
        return None
    periodic_rate = periodic_pct / 100.0           # → 0.00825

    # ── Tasso annuo: priorità al campo esplicito, poi nome, poi calcolo ────
    annual_pct: float | None = None

    # 1. "Tasso Cedola su base Annua" (presente per es. su BTP Valore)
    annual_str = cells.get("tasso cedola su base annua", "")
    if annual_str:
        annual_pct = _parse_it_float(annual_str)

    # 2. Regex sul Nome — gestisce sia "1,65%" (IT) sia "3.35%" (EN)
    if annual_pct is None:
        nome = cells.get("nome", "")
        m = re.search(r"(\d+[,\.]\d+)%", nome)
        if m:
            raw = m.group(1)
            if "," in raw:
                annual_pct = _parse_it_float(raw)          # formato italiano: "1,65"
            else:
                try:
                    annual_pct = float(raw)                 # formato internazionale: "3.35"
                except ValueError:
                    pass

    # 3. Fallback: assume SEMI_ANNUAL e raddoppia il periodale
    if annual_pct is None:
        annual_pct = periodic_pct * 2

    annual_rate = annual_pct / 100.0               # → 0.0165

    # ── Frequenza cedola ────────────────────────────────────────────────────
    frequency = _infer_frequency(annual_pct, periodic_pct)

    # ── Data scadenza ───────────────────────────────────────────────────────
    maturity_date = _parse_it_date(cells.get("scadenza", ""))

    # ── Data godimento → issue_date e first_coupon_date ────────────────────
    issue_date = _parse_it_date(cells.get("data godimento", ""))
    if issue_date is None:
        return None

    first_coupon_date = issue_date + relativedelta(months=frequency.months_between)

    return BIEnrichmentResult(
        coupon_rate=annual_rate,
        coupon_frequency=frequency,
        first_coupon_date=first_coupon_date,
        maturity_date=maturity_date,
        issue_date=issue_date,
        face_value=100.0,
    )
