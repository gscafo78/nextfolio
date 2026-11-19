"""
Calcolo dell'allocazione del portafoglio per tipo, valuta, conto, settore e continente.
"""
from collections import defaultdict

from app.schemas.portfolio import AllocationItem, AllocationOut
from app.services.portfolio.classification import (
    ASSET_CLASS_LABELS,
    BOND,
    CRYPTO,
    EQUITY,
    MONEY_MARKET,
    asset_class_weights,
    build_asset_info,  # noqa: F401  (riesportato per gli endpoint)
    currency_exposure,
)
from app.services.portfolio.positions import PositionCalc

# Pubblico: importato anche da xray.py per tradurre i tipi raw nei label usati in by_type
TYPE_LABELS = {
    "STOCK": "Azioni",
    "ETF": "ETF",
    "BOND": "Obbligazioni",
    "CRYPTO": "Crypto",
    "COMMODITY": "Commodity",
    "REIT": "REIT",
}
_TYPE_LABELS = TYPE_LABELS  # alias privato per compatibilità interna

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
    cash: list | None = None,           # list[CashBalance] — saldi di cassa dei conti
) -> AllocationOut:
    by_type: dict[str, float] = defaultdict(float)
    by_type_count: dict[str, int] = defaultdict(int)
    by_currency: dict[str, float] = defaultdict(float)
    by_currency_count: dict[str, int] = defaultdict(int)
    by_sector: dict[str, float] = defaultdict(float)
    by_continent: dict[str, float] = defaultdict(float)
    by_class: dict[str, float] = defaultdict(float)
    by_class_count: dict[str, int] = defaultdict(int)
    by_fx: dict[str, float] = defaultdict(float)
    by_continent_cls: dict[str, dict[str, float]] = {EQUITY: defaultdict(float), BOND: defaultdict(float)}
    italy_value = 0.0
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

        # Asset class dal sottostante (ETF obbligazionari = Obbligazioni)
        class_weights = asset_class_weights(info)
        main_class = max(class_weights, key=class_weights.get)
        for cls, w in class_weights.items():
            by_class[ASSET_CLASS_LABELS[cls]] += value * w
        by_class_count[ASSET_CLASS_LABELS[main_class]] += 1

        # Esposizione valutaria look-through (hedged → EUR)
        for ccy, w in currency_exposure(info).items():
            by_fx[ccy] += value * w

        # Look-through settoriale (con supporto override)
        sectors = _effective(info, "sectors") or []
        if sectors:
            for s in sectors:
                name = s.get("name", "Other")
                weight = float(s.get("weight", 0.0))
                by_sector[name] += value * weight
        elif main_class == BOND:
            by_sector["Bonds"] += value
        elif main_class == MONEY_MARKET:
            by_sector["Monetario"] += value
        elif main_class == CRYPTO:
            by_sector["Crypto"] += value
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
                # Geografia separata per azioni e obbligazioni
                for cls in (EQUITY, BOND):
                    if class_weights.get(cls):
                        by_continent_cls[cls][continent] += value * weight * class_weights[cls]
                if identifier in ("IT", "Italy"):
                    italy_value += value * weight

    # Liquidità dei conti: classe Monetario, valuta del conto, nessun look-through geografico
    account_values = dict(account_values)
    for b in cash or []:
        v = b.value_eur
        if v <= 0:
            continue  # saldi negativi (scoperto) non sono un'attività
        total += v
        by_type["Liquidità"] += v
        by_type_count["Liquidità"] += 1
        label = ASSET_CLASS_LABELS[MONEY_MARKET]
        by_class[label] += v
        by_class_count[label] += 1
        by_currency[b.currency] += v
        by_currency_count[b.currency] += 1
        by_fx[b.currency] += v
        by_sector["Liquidità"] += v
        account_values[b.account_name] = account_values.get(b.account_name, 0.0) + v

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

    def share_items(values: dict[str, float]) -> list[AllocationItem]:
        tot = sum(values.values()) or 1.0
        return sorted(
            [AllocationItem(label=k, value_eur=round(v, 2), pct=round(v / tot * 100, 1), count=0)
             for k, v in values.items() if v > 0],
            key=lambda x: x.value_eur, reverse=True,
        )

    return AllocationOut(
        by_asset_class=to_items(by_class, by_class_count),
        by_currency_exposure=share_items(by_fx),
        by_continent_equity=share_items(by_continent_cls[EQUITY]),
        by_continent_bond=share_items(by_continent_cls[BOND]),
        italy_exposure_pct=round(italy_value / total * 100, 1) if total > 0 else None,
        by_type=to_items(by_type, by_type_count),
        by_currency=to_items(by_currency, by_currency_count),
        by_account=by_account,
        by_sector=sector_items,
        by_continent=continent_items,
        total_value_eur=round(total, 2),
    )
