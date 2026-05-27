"""
Metriche di rischio del portafoglio calcolate sulla serie temporale TWRR.

Metriche:
- Volatilità annualizzata: std(rendimenti_giornalieri) × √252
- Max drawdown: massima riduzione picco-valle del valore portafoglio
- Sharpe ratio: rendimento_annualizzato / volatilità_annualizzata
- Sortino ratio: rendimento_annualizzato / downside_deviation_annualizzata
- Calmar ratio: rendimento_annualizzato / |max_drawdown|
"""
import math
from statistics import mean, stdev

from app.schemas.portfolio import PerformancePoint, RiskMetricsOut

_TRADING_DAYS = 252


def _empty(period: str, n: int = 0) -> RiskMetricsOut:
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
        twrr_annualized_pct=0.0,
        best_day_pct=0.0,
        worst_day_pct=0.0,
        positive_days_pct=0.0,
    )


def compute_risk_metrics(
    period: str,
    series: list[PerformancePoint],
    risk_free_annual: float = 0.0,
) -> RiskMetricsOut:
    if len(series) < 3:
        return _empty(period, len(series))

    values = [p.value_eur for p in series]
    dates = [p.date for p in series]

    # Daily returns (only where previous value > 0)
    daily_returns = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] > 0
    ]
    n = len(daily_returns)
    if n < 2:
        return _empty(period, n)

    # ── Volatilità annualizzata ──────────────────────────────────────────────
    daily_vol = stdev(daily_returns)
    ann_vol_pct = daily_vol * math.sqrt(_TRADING_DAYS) * 100

    # ── Max drawdown ─────────────────────────────────────────────────────────
    peak = values[0]
    peak_date = dates[0]
    max_dd = 0.0
    max_dd_start = None
    max_dd_end = None

    for v, d in zip(values, dates):
        if v > peak:
            peak = v
            peak_date = d
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
                max_dd_start = peak_date
                max_dd_end = d

    # ── TWRR annualizzato ────────────────────────────────────────────────────
    n_calendar = (dates[-1] - dates[0]).days
    total_factor = 1.0 + series[-1].twrr_pct / 100
    if n_calendar > 0 and total_factor > 0:
        twrr_ann = (total_factor ** (365.0 / n_calendar) - 1) * 100
    else:
        twrr_ann = 0.0

    # ── Sharpe ratio ─────────────────────────────────────────────────────────
    rf_daily = risk_free_annual / _TRADING_DAYS
    excess_mean = mean(daily_returns) - rf_daily
    sharpe = (excess_mean / daily_vol) * math.sqrt(_TRADING_DAYS) if daily_vol > 0 else None

    # ── Sortino ratio (downside deviation rispetto a 0) ──────────────────────
    downside_sq_mean = sum(min(r, 0.0) ** 2 for r in daily_returns) / n
    downside_dev = math.sqrt(downside_sq_mean)
    sortino = (
        (mean(daily_returns) - rf_daily) * math.sqrt(_TRADING_DAYS) / downside_dev
        if downside_dev > 0
        else None
    )

    # ── Calmar ratio ─────────────────────────────────────────────────────────
    calmar = twrr_ann / abs(max_dd * 100) if max_dd < -0.001 else None

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
        twrr_annualized_pct=round(twrr_ann, 2),
        best_day_pct=round(max(daily_returns) * 100, 2),
        worst_day_pct=round(min(daily_returns) * 100, 2),
        positive_days_pct=round(sum(1 for r in daily_returns if r > 0) / n * 100, 1),
    )
