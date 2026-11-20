"""Metriche su una serie di prezzi giornalieri (scheda titolo, confronto, backtest)."""
from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import stdev


def _parse(series: list[dict]) -> list[tuple[date, float]]:
    out = []
    for p in series:
        d = p["date"] if isinstance(p["date"], date) else date.fromisoformat(str(p["date"])[:10])
        c = p.get("close")
        if c is not None and c > 0 and not math.isnan(c):
            out.append((d, float(c)))
    out.sort()
    return out


def _value_at(points: list[tuple[date, float]], d: date) -> float | None:
    before = [c for dd, c in points if dd <= d]
    return before[-1] if before else None


def price_metrics(series: list[dict], today: date | None = None) -> dict:
    """Rendimento 1A e annualizzato 3A/5A, volatilità e max drawdown a 1A (giorni di borsa)."""
    pts = _parse(series)
    if len(pts) < 2:
        return {"return_1y_pct": None, "return_3y_ann_pct": None, "return_5y_ann_pct": None,
                "volatility_1y_pct": None, "max_drawdown_1y_pct": None, "first_date": None, "last_date": None}
    today = today or pts[-1][0]
    last = pts[-1][1]

    def ret(years: int, annualize: bool) -> float | None:
        start = today - timedelta(days=365 * years)
        if pts[0][0] > start + timedelta(days=10):
            return None   # storico troppo corto
        v0 = _value_at(pts, start)
        if not v0:
            return None
        r = last / v0
        return round(((r ** (1 / years)) - 1) * 100 if annualize else (r - 1) * 100, 2)

    one_year = [c for d, c in pts if d >= today - timedelta(days=365)]
    vol = dd = None
    if len(one_year) > 20:
        rets = [one_year[i] / one_year[i - 1] - 1 for i in range(1, len(one_year))]
        vol = round(stdev(rets) * math.sqrt(252) * 100, 2)
        peak, worst = one_year[0], 0.0
        for c in one_year:
            peak = max(peak, c)
            worst = min(worst, c / peak - 1)
        dd = round(worst * 100, 2)

    return {
        "return_1y_pct": ret(1, False),
        "return_3y_ann_pct": ret(3, True),
        "return_5y_ann_pct": ret(5, True),
        "volatility_1y_pct": vol,
        "max_drawdown_1y_pct": dd,
        "first_date": pts[0][0].isoformat(),
        "last_date": pts[-1][0].isoformat(),
    }
