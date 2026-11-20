"""
Proiezioni del patrimonio: Monte Carlo per obiettivi e FIRE.

Modello: rendimenti mensili log-normali indipendenti, con media annua ``mu`` e
volatilità annua ``sigma`` (r_m = exp(N(m, s)) − 1, s = σ/√12,
m = ln(1 + μ)/12 − s²/2, così il rendimento medio annuo atteso è μ).
Versamenti a fine mese. Seed fisso: stessi input → stessi risultati.

Rendimento e volatilità attesi derivano dall'allocazione per asset class con
ipotesi di lungo periodo modificabili (``DEFAULT_ASSUMPTIONS``) e una matrice di
correlazione semplificata. Sono ipotesi, non previsioni: la pagina le mostra e
permette di cambiarle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.services.portfolio.classification import BOND, CRYPTO, EQUITY, MONEY_MARKET, OTHER

# Ipotesi di lungo periodo per asset class (rendimento annuo nominale, volatilità annua)
DEFAULT_ASSUMPTIONS: dict[str, tuple[float, float]] = {
    EQUITY: (0.07, 0.16),
    BOND: (0.03, 0.06),
    MONEY_MARKET: (0.02, 0.005),
    CRYPTO: (0.15, 0.60),
    OTHER: (0.04, 0.15),
}
_CORR = {
    frozenset((EQUITY, BOND)): 0.1, frozenset((EQUITY, CRYPTO)): 0.4, frozenset((EQUITY, OTHER)): 0.3,
    frozenset((BOND, CRYPTO)): 0.0, frozenset((BOND, OTHER)): 0.2, frozenset((CRYPTO, OTHER)): 0.2,
}
N_PATHS = 5000
SEED = 42


def portfolio_assumptions(weights: dict[str, float], assumptions: dict[str, tuple[float, float]] | None = None) -> tuple[float, float]:
    """(μ, σ) annui del portafoglio dati i pesi per asset class."""
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    tot = sum(weights.values()) or 1.0
    w = {c: v / tot for c, v in weights.items() if v > 0}
    mu = sum(w[c] * a[c][0] for c in w)
    var = 0.0
    for i in w:
        for j in w:
            rho = 1.0 if i == j else (0.0 if MONEY_MARKET in (i, j) else _CORR.get(frozenset((i, j)), 0.3))
            var += w[i] * w[j] * a[i][1] * a[j][1] * rho
    return mu, math.sqrt(max(var, 0.0))


def _monthly_returns(mu: float, sigma: float, months: int, n_paths: int, seed: int) -> np.ndarray:
    s = sigma / math.sqrt(12)
    m = math.log(1 + mu) / 12 - s * s / 2
    if s == 0:
        return np.full((n_paths, months), math.exp(m) - 1)
    rng = np.random.default_rng(seed)
    return np.exp(rng.normal(m, s, size=(n_paths, months))) - 1


def simulate_paths(initial: float, monthly: float, months: int, mu: float, sigma: float,
                   n_paths: int = N_PATHS, seed: int = SEED) -> np.ndarray:
    """Matrice (percorsi × mesi+1) dei valori nominali."""
    r = _monthly_returns(mu, sigma, months, n_paths, seed)
    v = np.empty((n_paths, months + 1))
    v[:, 0] = initial
    for t in range(months):
        v[:, t + 1] = v[:, t] * (1 + r[:, t]) + monthly
    return v


@dataclass
class GoalProjection:
    months: int
    mu: float
    sigma: float
    probability: float                      # P(valore reale a scadenza ≥ obiettivo)
    median_final: float                     # in euro di oggi
    p10_final: float
    p90_final: float
    total_contributed: float
    required_monthly_80: float | None       # versamento mensile per l'80% di probabilità
    yearly: list[dict]                      # [{year, p10, p25, p50, p75, p90, contributed}] in euro di oggi


def _deflator(months: int, inflation: float) -> np.ndarray:
    return (1 + inflation) ** (np.arange(months + 1) / 12)


def project_goal(initial: float, monthly: float, months: int, target: float, mu: float, sigma: float,
                 inflation: float = 0.02, n_paths: int = N_PATHS, seed: int = SEED) -> GoalProjection:
    months = max(int(months), 1)
    paths = simulate_paths(initial, monthly, months, mu, sigma, n_paths, seed)
    real = paths / _deflator(months, inflation)
    final = real[:, -1]
    yearly = []
    for t in range(0, months + 1, 12):
        q = np.percentile(real[:, t], [10, 25, 50, 75, 90])
        yearly.append({"year": t // 12, "p10": round(float(q[0]), 2), "p25": round(float(q[1]), 2),
                       "p50": round(float(q[2]), 2), "p75": round(float(q[3]), 2), "p90": round(float(q[4]), 2),
                       "contributed": round(initial + monthly * t, 2)})
    if months % 12:
        q = np.percentile(final, [10, 25, 50, 75, 90])
        yearly.append({"year": round(months / 12, 2), "p10": round(float(q[0]), 2), "p25": round(float(q[1]), 2),
                       "p50": round(float(q[2]), 2), "p75": round(float(q[3]), 2), "p90": round(float(q[4]), 2),
                       "contributed": round(initial + monthly * months, 2)})
    return GoalProjection(
        months=months, mu=mu, sigma=sigma,
        probability=round(float((final >= target).mean()), 4),
        median_final=round(float(np.median(final)), 2),
        p10_final=round(float(np.percentile(final, 10)), 2),
        p90_final=round(float(np.percentile(final, 90)), 2),
        total_contributed=round(initial + monthly * months, 2),
        required_monthly_80=required_monthly(initial, months, target, mu, sigma, inflation, 0.8, n_paths=2000),
        yearly=yearly,
    )


def required_monthly(initial: float, months: int, target: float, mu: float, sigma: float, inflation: float,
                     probability: float = 0.8, n_paths: int = 2000, seed: int = SEED) -> float | None:
    """Versamento mensile minimo per raggiungere l'obiettivo con la probabilità data (bisezione)."""
    defl = (1 + inflation) ** (months / 12)

    def prob(c: float) -> float:
        final = simulate_paths(initial, c, months, mu, sigma, n_paths, seed)[:, -1] / defl
        return float((final >= target).mean())

    if prob(0.0) >= probability:
        return 0.0
    hi = max(target, 1.0) / max(months, 1) * 2 + 1
    while prob(hi) < probability:
        hi *= 2
        if hi > 1e8:
            return None
    lo = 0.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if prob(mid) >= probability:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1:
            break
    return round(hi, 0)


@dataclass
class FireResult:
    target_capital: float          # spese annue / tasso di prelievo
    years_to_fire_median: float | None
    years_to_fire_p10: float | None    # scenario sfavorevole (10° percentile)
    success_probability: float     # capitale non esaurito sull'orizzonte di prelievo
    sustainable_withdrawal_90: float   # prelievo annuo con il 90% di successo


def _years_to_reach(paths_real: np.ndarray, target: float, q: float) -> float | None:
    curve = np.percentile(paths_real, q, axis=0)
    hit = np.nonzero(curve >= target)[0]
    return round(float(hit[0]) / 12, 1) if hit.size else None


def _depletion_success(capital: float, annual_withdrawal: float, years: int, mu: float, sigma: float,
                       inflation: float, n_paths: int, seed: int) -> float:
    months = years * 12
    r = _monthly_returns(mu, sigma, months, n_paths, seed + 1)
    v = np.full(n_paths, capital, dtype=float)
    alive = np.ones(n_paths, dtype=bool)
    for t in range(months):
        w = annual_withdrawal / 12 * (1 + inflation) ** (t / 12)   # prelievo indicizzato all'inflazione
        v = v * (1 + r[:, t]) - w
        alive &= v > 0
        v = np.where(alive, v, 0.0)
    return float(alive.mean())


def fire(current: float, monthly: float, annual_expenses: float, withdrawal_rate: float, mu: float, sigma: float,
         inflation: float = 0.02, horizon_years: int = 40, max_years: int = 50,
         n_paths: int = 3000, seed: int = SEED) -> FireResult:
    target = annual_expenses / withdrawal_rate
    months = max_years * 12
    real = simulate_paths(current, monthly, months, mu, sigma, n_paths, seed) / _deflator(months, inflation)
    success = _depletion_success(target, annual_expenses, horizon_years, mu, sigma, inflation, n_paths, seed)
    lo, hi = 0.0, target * 0.2
    for _ in range(25):
        mid = (lo + hi) / 2
        if _depletion_success(target, mid, horizon_years, mu, sigma, inflation, 1000, seed) >= 0.9:
            lo = mid
        else:
            hi = mid
    return FireResult(
        target_capital=round(target, 0),
        years_to_fire_median=_years_to_reach(real, target, 50),
        years_to_fire_p10=_years_to_reach(real, target, 10),
        success_probability=round(success, 4),
        sustainable_withdrawal_90=round(lo, 0),
    )
