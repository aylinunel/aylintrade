"""Cointegration pair trading (statistical arbitrage)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

from .base import PairStrategy, register


def engle_granger(
    x: np.ndarray, y: np.ndarray, pvalue: float = 0.05
) -> tuple[bool, np.ndarray, np.ndarray]:
    """Engle-Granger two-step test.

    Returns ``(cointegrated, params, residuals)`` where ``params`` are the intercept and slope
    of ``y ~ x``. Uses the Engle-Granger residual critical values and requires a
    non-positive error-correction coefficient. Degenerate inputs fail closed.
    """
    if len(x) < 20 or len(x) != len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        return False, np.array([0.0, 0.0]), np.zeros(len(x))
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return False, np.array([0.0, 0.0]), np.zeros(len(x))
    step1 = sm.OLS(y, sm.add_constant(x)).fit()
    resid = np.asarray(step1.resid)
    result = coint(y, x)
    test_p = float(result.pvalue) if hasattr(result, "pvalue") else float(result[1])
    if not np.isfinite(test_p) or test_p > pvalue or np.std(resid) < 1e-12:
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
    inside the band or cointegration breaks. Hedge quantities use the fitted slope;
    their notionals are normalized to unit gross exposure.
    """

    window: int = 250
    z_entry: float = 1.0
    pvalue: float = 0.05

    id = "pair_trading"
    label = "Pair trading"
    description = "Relative value: trades a cointegrated spread with fitted hedge quantities"

    def __post_init__(self) -> None:
        if self.window < 20 or not self.z_entry > 0 or not 0 < self.pvalue < 1:
            raise ValueError("Need window >= 20, positive entry threshold and 0 < pvalue < 1")

    def warmup(self) -> int:
        return self.window

    def positions(self, a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
        x, y = a.to_numpy(float), b.to_numpy(float)
        leg_a, leg_b = np.zeros(len(x)), np.zeros(len(x))
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
            if sd < 1e-12 or c1 <= 0:
                model = None
                continue
            z = (y[i] - (c0 + c1 * x[i]) - mu) / sd
            if z > self.z_entry:
                side = 1.0
            elif z < -self.z_entry:
                side = -1.0
            else:
                continue
            gross = c1 * x[i] + y[i]
            if gross > 0:
                leg_a[i] = side * c1 * x[i] / gross
                leg_b[i] = -side * y[i] / gross
        return pd.Series(leg_a, index=a.index), pd.Series(leg_b, index=b.index)
