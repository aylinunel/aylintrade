"""Shooting-star candlestick reversal."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register


@register
@dataclass(frozen=True)
class ShootingStar(PositionStrategy):
    """Short after a confirmed shooting star; exit on a +/-``stop`` move or after ``max_hold`` bars.

    The eight conditions follow Investopedia via the original script: a bearish candle with
    a small real body, a long upper wick, almost no lower wick, after two rising closes,
    confirmed by a lower high and lower close the next day. Because confirmation needs the
    next bar, the short is entered at that next bar's close (the original entered a bar
    early, which is look-ahead). "Small body" means smaller than ``body_size`` times the
    average absolute body to date (the original compared with a near-zero signed average,
    so it never fired).
    """

    lower_wick: float = 0.2
    body_size: float = 0.5
    stop: float = 0.05
    max_hold: int = 7

    id = "shooting_star"
    label = "Shooting Star"
    description = "Short after a confirmed shooting star, exit at +/-5% or after 7 days"

    def signals(self, bars: pd.DataFrame) -> pd.Series:
        """True on the bar whose close confirms a shooting star on the previous bar."""
        o, h, l, c = (bars[k] for k in ("Open", "High", "Low", "Close"))
        body = (o - c).abs()
        star = (
            (o >= c)
            & ((c - l) < self.lower_wick * body)
            & (body < body.expanding().mean() * self.body_size)
            & ((h - o) >= 2 * (o - c))
            & (c >= c.shift(1))
            & (c.shift(1) >= c.shift(2))
        )
        confirmed = star.shift(1, fill_value=False) & (h <= h.shift(1)) & (c <= c.shift(1))
        return confirmed.astype(bool)

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        sig = self.signals(bars).to_numpy()
        c = bars["Close"].to_numpy(float)
        pos = np.zeros(len(c))
        entry, held = None, 0
        for i in range(len(c)):
            if entry is not None:
                held += 1
                if abs(c[i] / entry - 1) > self.stop or held >= self.max_hold:
                    entry = None
            elif sig[i]:
                entry, held = c[i], 0
            pos[i] = -1.0 if entry is not None else 0.0
        return pd.Series(pos, index=bars.index)
