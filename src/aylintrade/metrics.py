"""Performance statistics computed from a series of per-period returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Metrics:
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    periods: int
    years: float

    def as_dict(self, prefix: str = "") -> dict[str, float]:
        return {f"{prefix}{k}": v for k, v in asdict(self).items()}


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def compute_metrics(returns: pd.Series, periods_per_year: int) -> Metrics:
    """Annualised statistics. Sharpe and Sortino use a zero risk-free rate."""
    r = returns.dropna().astype(float)
    n = len(r)
    if n < 2:
        raise ValueError("need at least two returns")
    equity = (1 + r).cumprod()
    years = n / periods_per_year
    final = float(equity.iloc[-1])
    cagr = final ** (1 / years) - 1 if final > 0 else -1.0
    sd = float(r.std())
    downside = float(np.sqrt((r.clip(upper=0) ** 2).mean()))
    ann = np.sqrt(periods_per_year)
    mdd = max_drawdown(equity)
    return Metrics(
        total_return=final - 1,
        cagr=cagr,
        volatility=sd * ann,
        sharpe=float(r.mean() / sd * ann) if sd > 0 else 0.0,
        sortino=float(r.mean() / downside * ann) if downside > 0 else 0.0,
        max_drawdown=mdd,
        calmar=cagr / abs(mdd) if mdd < 0 else 0.0,
        periods=n,
        years=years,
    )
