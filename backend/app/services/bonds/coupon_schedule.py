"""
Calcolo calendario cedole per obbligazioni a tasso fisso.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.models.bond_detail import BondDetail, CouponFrequency


def generate_coupon_dates(
    bond: BondDetail,
    from_date: date,
    to_date: date,
) -> list[date]:
    """
    Genera tutte le date cedola nell'intervallo [from_date, to_date].
    Parte dalla first_coupon_date e avanza di months_between mesi per iterazione.
    """
    freq = CouponFrequency(bond.coupon_frequency)
    step = freq.months_between
    end = bond.maturity_date or to_date

    dates: list[date] = []
    current = bond.first_coupon_date

    # Avanza fino a from_date
    while current < from_date:
        current += relativedelta(months=step)

    # Raccoglie le date nell'intervallo
    while current <= min(end, to_date):
        dates.append(current)
        current += relativedelta(months=step)

    return dates


def coupon_per_unit(bond: BondDetail) -> float:
    return bond.coupon_per_unit


def upcoming_coupon_entries(
    bond: BondDetail,
    quantity: float,
    from_date: date,
    days: int,
    recorded_dates: set[date] | None = None,
) -> list[dict]:
    """
    Restituisce le cedole future (o recenti) per una posizione.
    recorded_dates: date per cui esiste già una transazione COUPON.
    """
    to_date = from_date + timedelta(days=days)
    dates = generate_coupon_dates(bond, from_date - timedelta(days=5), to_date)
    cpu = coupon_per_unit(bond)
    recorded = recorded_dates or set()
    today = date.today()

    entries = []
    for d in dates:
        entries.append({
            "date": d,
            "coupon_per_unit": cpu,
            "total_coupon_eur": round(quantity * cpu, 2),
            "days_until": (d - today).days,
            "already_recorded": d in recorded,
        })
    return entries
