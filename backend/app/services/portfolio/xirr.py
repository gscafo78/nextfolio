"""
XIRR — Extended Internal Rate of Return per flussi di cassa irregolari.
Algoritmo: metodo di Newton-Raphson su NPV.
"""
from datetime import date


def xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """
    cashflows: lista (data, importo) dove importo < 0 = esborso, > 0 = incasso.
    Restituisce il tasso annualizzato (es. 0.12 = 12%) oppure None se non converge.
    """
    if len(cashflows) < 2:
        return None

    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    t0 = dates[0]
    times = [(d - t0).days / 365.0 for d in dates]

    # servono flussi di segno opposto per avere una soluzione
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None

    def npv(r: float) -> float:
        if r <= -1:
            return float("inf")
        return sum(a / (1.0 + r) ** t for t, a in zip(times, amounts))

    def dnpv(r: float) -> float:
        if r <= -1:
            return float("inf")
        return sum(-t * a / (1.0 + r) ** (t + 1) for t, a in zip(times, amounts))

    r = guess
    for _ in range(200):
        f = npv(r)
        df = dnpv(r)
        if df == 0 or abs(df) < 1e-15:
            break
        r_new = r - f / df
        if abs(r_new - r) < 1e-9:
            return round(r_new * 100, 4)
        r = r_new

    return None
