"""Bollinger Bands bottom-W (double bottom) pattern."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register
from .indicators import bollinger_bands


@register
@dataclass(frozen=True)
class BollingerW(PositionStrategy):
    """Go long when a double bottom inside the bands breaks out above the upper band.

    The W is found by walking back from today's breakout (node *i*): a middle peak at the
    mid band (*j*), a first bottom touching the lower band (*k*), and a second bottom (*m*)
    above the lower band but below the first. Exit when the bands contract, defined as the
    band width falling below its own ``lookback``-bar average.

    ``tolerance`` is the "touch" distance as a fraction of price (the original used 0.0001
    in GBP/USD price units). The original exit (band std < 0.0001) never fires outside FX.
    """

    window: int = 20
    num_std: float = 2.0
    lookback: int = 75
    tolerance: float = 0.01

    id = "bollinger_w"
    label = "Bollinger Bands W"
    description = "Long on a double-bottom breakout, exit when the bands contract"

    def warmup(self) -> int:
        return self.lookback + self.window

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["Close"]
        bb = bollinger_bands(close, self.window, self.num_std)
        width = (bb["upper"] - bb["lower"]) / bb["mid"]
        width_avg = width.rolling(self.lookback).mean().to_numpy()
        width = width.to_numpy()
        p, mid, up, lo = (
            close.to_numpy(),
            bb["mid"].to_numpy(),
            bb["upper"].to_numpy(),
            bb["lower"].to_numpy(),
        )
        tol, lb = self.tolerance, self.lookback

        pos = np.zeros(len(p))
        holding = False
        for i in range(self.warmup(), len(p)):
            entered = False
            if not holding and p[i] > up[i]:
                j = next(
                    (
                        x
                        for x in range(i, i - lb, -1)
                        if abs(mid[x] - p[x]) < tol * p[x] and abs(mid[x] - up[i]) < tol * p[i]
                    ),
                    None,
                )
                k = (
                    None
                    if j is None
                    else next(
                        (x for x in range(j, i - lb, -1) if abs(lo[x] - p[x]) < tol * p[x]), None
                    )
                )
                if k is not None:
                    first_bottom = p[k]
                    entered = any(
                        p[m] - lo[m] < tol * p[m] and p[m] > lo[m] and p[m] < first_bottom
                        for m in range(i, j, -1)  # type: ignore[arg-type]
                    )
                    holding = entered
            if holding and not entered and width[i] < width_avg[i]:
                holding = False
            pos[i] = 1.0 if holding else 0.0
        return pd.Series(pos, index=bars.index)
