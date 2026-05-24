"""
Calcolo dell'allocazione del portafoglio per tipo, valuta e conto.
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


def calculate_allocation(
    positions: dict[int, PositionCalc],
    asset_info: dict[int, dict],        # {asset_id: {type, currency, symbol, name}}
    price_eur: dict[int, float],        # {asset_id: prezzo in EUR}
    account_values: dict[str, float],   # {account_name: valore EUR}
) -> AllocationOut:
    by_type: dict[str, float] = defaultdict(float)
    by_type_count: dict[str, int] = defaultdict(int)
    by_currency: dict[str, float] = defaultdict(float)
    by_currency_count: dict[str, int] = defaultdict(int)
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
        total_value_eur=round(total, 2),
    )
