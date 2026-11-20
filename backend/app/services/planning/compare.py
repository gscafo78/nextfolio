"""
Confronto tra titoli e backtest di un portafoglio modello (funzioni pure).

Le serie in ingresso sono [{date, close}] in EUR (giornaliere). Il confronto usa
la finestra comune a tutti i titoli; il backtest usa le chiusure di fine mese.
"""
from __future__ import annotations

import math
import re
from datetime import date

from app.services.planning.metrics import _parse, price_metrics


def _common(series_map: dict[str, list[dict]], start: date | None = None) -> tuple[list[date], dict[str, dict[date, float]]]:
    parsed = {k: dict(_parse(v)) for k, v in series_map.items()}
    if not parsed or any(not p for p in parsed.values()):
        return [], parsed
    first = max(min(p) for p in parsed.values())
    if start:
        first = max(first, start)
    dates = sorted(set.intersection(*(set(d for d in p if d >= first) for p in parsed.values())))
    return dates, parsed


def compare(series_map: dict[str, list[dict]], start: date | None = None) -> dict:
    """Serie ribasate a 100 dalla prima data comune, metriche e correlazioni dei rendimenti giornalieri."""
    dates, parsed = _common(series_map, start)
    keys = list(series_map)
    if len(dates) < 2:
        return {"dates": [], "normalized": {}, "metrics": {}, "correlation": {}, "start": None, "end": None}
    normalized = {k: [round(parsed[k][d] / parsed[k][dates[0]] * 100, 3) for d in dates] for k in keys}
    window = {k: [{"date": d.isoformat(), "close": parsed[k][d]} for d in dates] for k in keys}
    metrics = {k: {**price_metrics(series_map[k]),
                   "window_return_pct": round(normalized[k][-1] - 100, 2),
                   "window_ann_return_pct": _annualize(normalized[k][-1] / 100, dates)} for k in keys}
    for k in keys:
        metrics[k]["window_volatility_pct"] = price_metrics(window[k]).get("volatility_1y_pct")
    rets = {k: [parsed[k][dates[i]] / parsed[k][dates[i - 1]] - 1 for i in range(1, len(dates))] for k in keys}
    corr = {a: {b: round(_pearson(rets[a], rets[b]), 3) for b in keys} for a in keys}
    step = max(1, len(dates) // 400)   # al massimo ~400 punti per il grafico
    idx = list(range(0, len(dates), step)) + ([len(dates) - 1] if (len(dates) - 1) % step else [])
    return {"dates": [dates[i].isoformat() for i in idx],
            "normalized": {k: [normalized[k][i] for i in idx] for k in keys},
            "metrics": metrics, "correlation": corr, "start": dates[0].isoformat(), "end": dates[-1].isoformat()}


def _annualize(factor: float, dates: list[date]) -> float | None:
    days = (dates[-1] - dates[0]).days
    if days < 300 or factor <= 0:
        return None
    return round((factor ** (365 / days) - 1) * 100, 2)


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return cov / (va * vb) if va and vb else 0.0


_SUFFIX = re.compile(r"\b(inc|corp|corporation|plc|ltd|limited|co|sa|ag|nv|se|class [a-z]|ordinary shares?|shs|adr)\b\.?", re.I)


def _norm_name(h: dict) -> str:
    n = (h.get("name") or h.get("symbol") or "").lower()
    n = _SUFFIX.sub(" ", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def holdings_overlap(a: list[dict], b: list[dict]) -> dict:
    """Sovrapposizione tra due ETF: Σ min(peso) sulle holding comuni (dati: principali posizioni disponibili)."""
    wa = {_norm_name(h): float(h.get("weight") or 0) for h in a if _norm_name(h)}
    wb = {_norm_name(h): float(h.get("weight") or 0) for h in b if _norm_name(h)}
    common = sorted(set(wa) & set(wb), key=lambda k: -min(wa[k], wb[k]))
    return {"overlap_pct": round(sum(min(wa[k], wb[k]) for k in common) * 100, 2),
            "common": [{"name": k, "weight_a": round(wa[k] * 100, 2), "weight_b": round(wb[k] * 100, 2)} for k in common],
            "coverage_a_pct": round(sum(wa.values()) * 100, 1), "coverage_b_pct": round(sum(wb.values()) * 100, 1)}


def _month_ends(dates: list[date]) -> list[date]:
    out = []
    for i, d in enumerate(dates):
        if i == len(dates) - 1 or dates[i + 1].month != d.month:
            out.append(d)
    return out


def backtest(series_map: dict[str, list[dict]], weights: dict[str, float], *, start: date | None = None,
             initial: float = 10_000.0, monthly: float = 0.0, rebalance: str = "none",
             threshold_pct: float = 5.0) -> dict:
    """Backtest mensile: capitale iniziale, versamento mensile ripartito secondo i pesi, ribilanciamento
    ``none`` | ``annual`` | ``threshold`` (quando un peso si scosta più di ``threshold_pct`` punti)."""
    keys = [k for k, w in weights.items() if w > 0]
    tot = sum(weights[k] for k in keys) or 1.0
    w = {k: weights[k] / tot for k in keys}
    dates, parsed = _common({k: series_map[k] for k in keys}, start)
    months = _month_ends(dates)
    if len(months) < 2:
        return {"series": [], "metrics": {}, "warnings": ["Storico comune insufficiente per il backtest."]}

    units = {k: initial * w[k] / parsed[k][months[0]] for k in keys}
    invested = initial
    chain = 1.0
    prev_value = initial
    series = [{"date": months[0].isoformat(), "value": round(initial, 2), "invested": round(initial, 2)}]
    monthly_rets = []
    rebalances = 0
    for i, d in enumerate(months[1:], 1):
        value = sum(units[k] * parsed[k][d] for k in keys)
        r = value / prev_value - 1 if prev_value > 0 else 0.0     # rendimento prima del versamento
        chain *= 1 + r
        monthly_rets.append(r)
        if monthly > 0:
            for k in keys:
                units[k] += monthly * w[k] / parsed[k][d]
            invested += monthly
            value += monthly
        do_rebal = (rebalance == "annual" and d.month == months[0].month and i >= 12) or (
            rebalance == "threshold" and any(abs(units[k] * parsed[k][d] / value - w[k]) * 100 > threshold_pct for k in keys))
        if do_rebal:
            units = {k: value * w[k] / parsed[k][d] for k in keys}
            rebalances += 1
        prev_value = value
        series.append({"date": d.isoformat(), "value": round(value, 2), "invested": round(invested, 2)})

    years = (months[-1] - months[0]).days / 365.25
    vol = (math.sqrt(sum((x - sum(monthly_rets) / len(monthly_rets)) ** 2 for x in monthly_rets) / (len(monthly_rets) - 1))
           * math.sqrt(12) * 100) if len(monthly_rets) > 2 else None
    peak, mdd, idx = 1.0, 0.0, 1.0
    for x in monthly_rets:
        idx *= 1 + x
        peak = max(peak, idx)
        mdd = min(mdd, idx / peak - 1)
    return {
        "series": series,
        "metrics": {
            "start": months[0].isoformat(), "end": months[-1].isoformat(),
            "final_value": series[-1]["value"], "invested": round(invested, 2),
            "twrr_pct": round((chain - 1) * 100, 2),
            "twrr_ann_pct": round((chain ** (1 / years) - 1) * 100, 2) if years >= 1 and chain > 0 else None,
            "volatility_pct": round(vol, 2) if vol is not None else None,
            "max_drawdown_pct": round(mdd * 100, 2), "rebalances": rebalances,
        },
        "warnings": [] if years >= 3 else [f"Storico comune di soli {years:.1f} anni: risultati poco indicativi."],
    }
