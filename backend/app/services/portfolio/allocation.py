"""
Calcolo dell'allocazione del portafoglio per tipo, valuta, conto, settore e continente.
"""
from collections import defaultdict

from app.schemas.portfolio import AllocationItem, AllocationOut
from app.services.portfolio.positions import PositionCalc

_TYPE_LABELS = {
    "STOCK": "Azioni",
    "ETF": "ETF",
    "BOND": "Obbligazioni",
    "CRYPTO": "Crypto",
    "COMMODITY": "Commodity",
    "REIT": "REIT",
}

# Mappa nome paese (come restituito da Yahoo Finance info.country) → continente
# Ispirata al mapping di Ghostfolio (SymbolProfile.countries → continent grouping)
_COUNTRY_TO_CONTINENT: dict[str, str] = {
    # Nord America
    "United States": "Nord America",
    "Canada": "Nord America",
    "Mexico": "Nord America",
    "Panama": "Nord America",
    "Puerto Rico": "Nord America",
    # Europa
    "Germany": "Europa",
    "France": "Europa",
    "Italy": "Europa",
    "United Kingdom": "Europa",
    "Switzerland": "Europa",
    "Netherlands": "Europa",
    "Sweden": "Europa",
    "Spain": "Europa",
    "Belgium": "Europa",
    "Ireland": "Europa",
    "Denmark": "Europa",
    "Norway": "Europa",
    "Finland": "Europa",
    "Austria": "Europa",
    "Luxembourg": "Europa",
    "Portugal": "Europa",
    "Poland": "Europa",
    "Czech Republic": "Europa",
    "Hungary": "Europa",
    "Greece": "Europa",
    "Romania": "Europa",
    "Russia": "Europa",
    "Turkey": "Europa",
    "Ukraine": "Europa",
    "Bermuda": "Europa",
    # Asia-Pacifico
    "Japan": "Asia-Pacifico",
    "China": "Asia-Pacifico",
    "South Korea": "Asia-Pacifico",
    "India": "Asia-Pacifico",
    "Australia": "Asia-Pacifico",
    "Hong Kong": "Asia-Pacifico",
    "Singapore": "Asia-Pacifico",
    "Taiwan": "Asia-Pacifico",
    "Indonesia": "Asia-Pacifico",
    "Malaysia": "Asia-Pacifico",
    "Thailand": "Asia-Pacifico",
    "Philippines": "Asia-Pacifico",
    "Vietnam": "Asia-Pacifico",
    "New Zealand": "Asia-Pacifico",
    "Pakistan": "Asia-Pacifico",
    "Bangladesh": "Asia-Pacifico",
    # Medio Oriente e Africa del Nord
    "Israel": "Medio Oriente",
    "Saudi Arabia": "Medio Oriente",
    "United Arab Emirates": "Medio Oriente",
    "Qatar": "Medio Oriente",
    "Kuwait": "Medio Oriente",
    "Egypt": "Medio Oriente",
    "Morocco": "Medio Oriente",
    # Africa
    "South Africa": "Africa",
    "Nigeria": "Africa",
    "Kenya": "Africa",
    "Ghana": "Africa",
    # Sud America
    "Brazil": "Sud America",
    "Chile": "Sud America",
    "Colombia": "Sud America",
    "Argentina": "Sud America",
    "Peru": "Sud America",
    "Uruguay": "Sud America",
    # Supporto anche per codici ISO (per compatibilità futura)
    "US": "Nord America",
    "CA": "Nord America",
    "DE": "Europa",
    "FR": "Europa",
    "IT": "Europa",
    "GB": "Europa",
    "CH": "Europa",
    "NL": "Europa",
    "SE": "Europa",
    "ES": "Europa",
    "JP": "Asia-Pacifico",
    "CN": "Asia-Pacifico",
    "KR": "Asia-Pacifico",
    "IN": "Asia-Pacifico",
    "AU": "Asia-Pacifico",
    "HK": "Asia-Pacifico",
    "SG": "Asia-Pacifico",
    "TW": "Asia-Pacifico",
    "BR": "Sud America",
    "ZA": "Africa",
    "IL": "Medio Oriente",
    "SA": "Medio Oriente",
}


def _effective(asset_info: dict, key: str):
    """Restituisce il valore override se presente, altrimenti il valore enriched."""
    override = asset_info.get(f"{key}_override")
    if override is not None:
        return override
    return asset_info.get(key)


def calculate_allocation(
    positions: dict[int, PositionCalc],
    asset_info: dict[int, dict],        # {asset_id: {type, currency, sectors, countries, ...}}
    price_eur: dict[int, float],        # {asset_id: prezzo in EUR}
    account_values: dict[str, float],   # {account_name: valore EUR}
) -> AllocationOut:
    by_type: dict[str, float] = defaultdict(float)
    by_type_count: dict[str, int] = defaultdict(int)
    by_currency: dict[str, float] = defaultdict(float)
    by_currency_count: dict[str, int] = defaultdict(int)
    by_sector: dict[str, float] = defaultdict(float)
    by_continent: dict[str, float] = defaultdict(float)
    total = 0.0

    for asset_id, pos in positions.items():
        info = asset_info.get(asset_id, {})
        price = price_eur.get(asset_id)
        if price is None:
            continue
        value = pos.quantity * price
        total += value

        raw_type = info.get("type", "OTHER")
        label_type = _TYPE_LABELS.get(raw_type, raw_type)
        by_type[label_type] += value
        by_type_count[label_type] += 1

        currency = info.get("currency", "EUR")
        by_currency[currency] += value
        by_currency_count[currency] += 1

        # Look-through settoriale (con supporto override)
        sectors = _effective(info, "sectors") or []
        if sectors:
            for s in sectors:
                name = s.get("name", "Other")
                weight = float(s.get("weight", 0.0))
                by_sector[name] += value * weight
        else:
            by_sector["Non classificato"] += value

        # Look-through geografico → continente (con supporto override)
        countries = _effective(info, "countries") or []
        if countries:
            for c in countries:
                # Ghostfolio usa codici ISO; il nostro enricher usa nomi completi
                identifier = c.get("code") or c.get("name") or ""
                weight = float(c.get("weight", 1.0))
                continent = _COUNTRY_TO_CONTINENT.get(identifier, "Altro")
                by_continent[continent] += value * weight

    def to_items(values: dict[str, float], counts: dict[str, int]) -> list[AllocationItem]:
        items = [
            AllocationItem(
                label=k,
                value_eur=round(v, 2),
                pct=round((v / total) * 100, 1) if total > 0 else 0.0,
                count=counts.get(k, 0),
            )
            for k, v in values.items()
        ]
        return sorted(items, key=lambda x: x.value_eur, reverse=True)

    # Settori: normalizza su totale settoriale (può differire da total per asset senza dati)
    sector_total = sum(by_sector.values()) or 1.0
    sector_items = sorted(
        [
            AllocationItem(
                label=k,
                value_eur=round(v, 2),
                pct=round((v / sector_total) * 100, 1),
                count=0,
            )
            for k, v in by_sector.items()
            if v > 0
        ],
        key=lambda x: x.value_eur,
        reverse=True,
    )

    # Continenti
    continent_total = sum(by_continent.values()) or 1.0
    continent_items = sorted(
        [
            AllocationItem(
                label=k,
                value_eur=round(v, 2),
                pct=round((v / continent_total) * 100, 1),
                count=0,
            )
            for k, v in by_continent.items()
            if v > 0
        ],
        key=lambda x: x.value_eur,
        reverse=True,
    ) if by_continent else []

    acct_total = sum(account_values.values()) or 1.0
    by_account = sorted(
        [
            AllocationItem(
                label=name,
                value_eur=round(v, 2),
                pct=round((v / acct_total) * 100, 1),
                count=0,
            )
            for name, v in account_values.items()
            if v > 0
        ],
        key=lambda x: x.value_eur,
        reverse=True,
    )

    return AllocationOut(
        by_type=to_items(by_type, by_type_count),
        by_currency=to_items(by_currency, by_currency_count),
        by_account=by_account,
        by_sector=sector_items,
        by_continent=continent_items,
        total_value_eur=round(total, 2),
    )
