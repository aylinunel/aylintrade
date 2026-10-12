"""Cointegration pair trading (statistical arbitrage)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from .base import PairStrategy, register


def adf_pvalue(x: np.ndarray) -> float:
    """ADF test p-value, compatible with statsmodels before and after the result-object change."""
    try:
        return float(adfuller(x, result_object=True).pvalue)
    except TypeError:  # statsmodels < 0.15
        return float(adfuller(x)[1])


def engle_granger(
    x: np.ndarray, y: np.ndarray, pvalue: float = 0.05
) -> tuple[bool, np.ndarray, np.ndarray]:
    """Engle-Granger two-step test.

    Returns ``(cointegrated, params, residuals)`` where ``params`` are the intercept and slope
    of ``y ~ x``. Cointegrated means the residuals pass ADF at ``pvalue`` and the
    error-correction coefficient is not positive.

    This follows the original script, which uses ordinary ADF p-values on the residuals.
    Those are optimistic for estimated residuals, so spurious pairs pass more often than
    ``pvalue`` suggests (see docs/methodology.md).
    """
    step1 = sm.OLS(y, sm.add_constant(x)).fit()
    resid = np.asarray(step1.resid)
    if adf_pvalue(resid) > pvalue:
        return False, np.asarray(step1.params), resid
    ecm_x = sm.add_constant(np.column_stack([np.diff(x), resid[:-1]]))
    step2 = sm.OLS(np.diff(y), ecm_x).fit()
    return bool(step2.params[-1] <= 0), np.asarray(step1.params), resid


@register
@dataclass(frozen=True)
class PairTrading(PairStrategy):
    """Trade the z-score of the spread between two cointegrated assets.

    Every bar, re-test cointegration on the previous ``window`` bars. When it starts, freeze
    the hedge model; while it holds, long ``a`` / short ``b`` when ``b`` is rich
    (z > ``z_entry``) and the reverse when it is cheap. Positions close when |z| falls back
    inside the band or cointegration breaks. Each leg uses half the capital.
    """

    window: int = 250
    z_entry: float = 1.0
    pvalue: float = 0.05

    id = "pair_trading"
    label = "Pair trading"
    description = "Market-neutral: trades the spread between two cointegrated assets"

    def warmup(self) -> int:
        return self.window

    def positions(self, a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
        x, y = a.to_numpy(float), b.to_numpy(float)
        sig = np.zeros(len(x))
        model: tuple[np.ndarray, float, float] | None = None
        for i in range(self.window, len(x)):
            ok, params, resid = engle_granger(
                x[i - self.window : i], y[i - self.window : i], self.pvalue
            )
            if not ok:
                model = None
                continue
            if model is None:
                model = (params, float(resid.mean()), float(resid.std(ddof=1)))
            (c0, c1), mu, sd = model
            z = (y[i] - (c0 + c1 * x[i]) - mu) / sd
            if z > self.z_entry:
                sig[i] = 1.0
            elif z < -self.z_entry:
                sig[i] = -1.0
        leg = pd.Series(0.5 * sig, index=a.index)
        return leg, -leg
