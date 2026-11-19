"""
Metriche di rischio dalla serie di performance.

Usa i rendimenti giornalieri *neutralizzati dai flussi* calcolati da
``performance.compute_performance`` (``daily_return_pct``), solo sui giorni di
borsa e solo quelli con base affidabile: versamenti, acquisti e vendite non
contano come rendimento.

- Volatilità annualizzata: std campionaria dei rendimenti × √252
- Max drawdown: sull'indice TWRR (non sul valore, che include i versamenti)
- Sharpe: (media rendimenti − rf giornaliero) / std × √252
- Sortino: (media − rf) / downside deviation × √252, con downside deviation =
  √(media di min(r − rf, 0)²) su tutti i giorni (target = risk-free)
- Calmar: TWRR annualizzato / |max drawdown| (solo con almeno un anno di dati)

Il tasso risk-free è annuo (frazione) e viene convertito in giornaliero
composto: (1 + rf)^(1/252) − 1.
"""
import math
from statistics import mean, stdev

from app.schemas.portfolio import PerformancePoint, RiskMetricsOut

_TRADING_DAYS = 252

# Soglie di plausibilità (oltre: avviso "dati sospetti")
SANITY_MAX_DAILY_ABS = 0.20
SANITY_MAX_BEST_WORST = 0.15
SANITY_MAX_VOL_PCT = 60.0
SANITY_MAX_SHARPE = 3.0
SANITY_MIN_DAYS = 20


def _empty(period: str, n: int = 0, rf: float = 0.0, warnings: list[str] | None = None) -> RiskMetricsOut:
    return RiskMetricsOut(
        period=period,
        trading_days=n,
        annualized_volatility_pct=0.0,
        max_drawdown_pct=0.0,
        max_drawdown_start=None,
        max_drawdown_end=None,
        sharpe_ratio=None,
        sortino_ratio=None,
        calmar_ratio=None,
        twrr_annualized_pct=None,
        best_day_pct=0.0,
        worst_day_pct=0.0,
        positive_days_pct=0.0,
        risk_free_pct=round(rf * 100, 3),
        warnings=warnings or [],
    )


def _returns(series: list[PerformancePoint]) -> tuple[list[float], int]:
    """(rendimenti affidabili, giorni esclusi per base troppo piccola)."""
    if any(p.daily_return_pct is not None for p in series):
        usable = [p for p in series if p.daily_return_pct is not None]
        good = [p.daily_return_pct / 100 for p in usable if p.reliable]
        return good, len(usable) - len(good)
    # Serie legacy senza rendimenti giornalieri: ricava dalla catena TWRR
    idx = [1 + p.twrr_pct / 100 for p in series]
    return [idx[i] / idx[i - 1] - 1 for i in range(1, len(idx)) if idx[i - 1] > 0], 0


def compute_risk_metrics(
    period: str,
    series: list[PerformancePoint],
    risk_free_annual: float = 0.0,
) -> RiskMetricsOut:
    if len(series) < 3:
        return _empty(period, len(series), risk_free_annual)

    rets, excluded = _returns(series)
    n = len(rets)
    warnings: list[str] = []
    if excluded:
        warnings.append(f"{excluded} giorni esclusi: valore del portafoglio troppo basso per un rendimento affidabile.")
    if n < 2:
        return _empty(period, n, risk_free_annual, warnings)
    if n < SANITY_MIN_DAYS:
        warnings.append(f"Campione ridotto ({n} giorni di borsa): metriche poco significative.")

    # ── Volatilità ───────────────────────────────────────────────────────────
    daily_vol = stdev(rets)
    ann_vol_pct = daily_vol * math.sqrt(_TRADING_DAYS) * 100

    # ── Max drawdown sull'indice TWRR ────────────────────────────────────────
    dates = [p.date for p in series]
    index = [1 + p.twrr_pct / 100 for p in series]
    peak, peak_date = index[0], dates[0]
    max_dd, max_dd_start, max_dd_end = 0.0, None, None
    for v, d in zip(index, dates):
        if v > peak:
            peak, peak_date = v, d
        if peak > 0:
            dd = v / peak - 1
            if dd < max_dd:
                max_dd, max_dd_start, max_dd_end = dd, peak_date, d

    # ── TWRR annualizzato (solo con almeno un anno) ─────────────────────────
    n_calendar = (dates[-1] - dates[0]).days
    total_factor = index[-1]
    twrr_ann = None
    if n_calendar >= 365 and total_factor > 0:
        twrr_ann = (total_factor ** (365.0 / n_calendar) - 1) * 100

    # ── Sharpe / Sortino ─────────────────────────────────────────────────────
    rf_daily = (1 + risk_free_annual) ** (1 / _TRADING_DAYS) - 1
    excess = [r - rf_daily for r in rets]
    sharpe = mean(excess) / daily_vol * math.sqrt(_TRADING_DAYS) if daily_vol > 0 else None
    downside_dev = math.sqrt(sum(min(e, 0.0) ** 2 for e in excess) / n)
    sortino = mean(excess) / downside_dev * math.sqrt(_TRADING_DAYS) if downside_dev > 0 else None

    calmar = twrr_ann / abs(max_dd * 100) if twrr_ann is not None and max_dd < -0.001 else None

    best, worst = max(rets), min(rets)

    # ── Sanity check ─────────────────────────────────────────────────────────
    outliers = sum(1 for r in rets if abs(r) > SANITY_MAX_DAILY_ABS)
    if outliers:
        warnings.append(f"Dati sospetti: {outliers} rendimenti giornalieri oltre ±{SANITY_MAX_DAILY_ABS:.0%}.")
    if ann_vol_pct > SANITY_MAX_VOL_PCT:
        warnings.append(f"Dati sospetti: volatilità annualizzata {ann_vol_pct:.1f}% oltre il {SANITY_MAX_VOL_PCT:.0f}%.")
    if sharpe is not None and sharpe > SANITY_MAX_SHARPE:
        warnings.append(f"Dati sospetti: Sharpe {sharpe:.2f} oltre {SANITY_MAX_SHARPE:.0f}.")
    if max(abs(best), abs(worst)) > SANITY_MAX_BEST_WORST:
        warnings.append(f"Dati sospetti: miglior/peggior giorno oltre ±{SANITY_MAX_BEST_WORST:.0%}.")

    return RiskMetricsOut(
        period=period,
        trading_days=n,
        annualized_volatility_pct=round(ann_vol_pct, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        max_drawdown_start=max_dd_start,
        max_drawdown_end=max_dd_end,
        sharpe_ratio=round(sharpe, 3) if sharpe is not None else None,
        sortino_ratio=round(sortino, 3) if sortino is not None else None,
        calmar_ratio=round(calmar, 3) if calmar is not None else None,
        twrr_annualized_pct=round(twrr_ann, 2) if twrr_ann is not None else None,
        best_day_pct=round(best * 100, 2),
        worst_day_pct=round(worst * 100, 2),
        positive_days_pct=round(sum(1 for r in rets if r > 0) / n * 100, 1),
        risk_free_pct=round(risk_free_annual * 100, 3),
        warnings=warnings,
    )
