"""MACD oscillator (moving-average crossover)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register
from .indicators import sma


@register
@dataclass(frozen=True)
class MACD(PositionStrategy):
    """Long while the fast simple moving average is at or above the slow one, flat otherwise.

    The original script recommends 10/21 days (two weeks vs one month of trading days).
    """

    fast: int = 10
    slow: int = 21

    id = "macd"
    label = "MACD oscillator"
    description = "Long when the 10-day average is at or above the 21-day average, else cash"

    def __post_init__(self) -> None:
        if not 0 < self.fast < self.slow:
            raise ValueError("macd: need 0 < fast < slow")

    def warmup(self) -> int:
        return self.slow

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        fast, slow = sma(bars["Close"], self.fast), sma(bars["Close"], self.slow)
        pos = pd.Series(np.where(fast >= slow, 1.0, 0.0), index=bars.index)
        pos[slow.isna()] = 0.0
        return pos
