"""Parabolic SAR trend following."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register
from .indicators import parabolic_sar


@register
@dataclass(frozen=True)
class ParabolicSAR(PositionStrategy):
    """Long while the SAR dots sit below the price, flat otherwise."""

    af_start: float = 0.02
    af_step: float = 0.02
    af_max: float = 0.2

    id = "parabolic_sar"
    label = "Parabolic SAR"
    description = "Long while the SAR is below the price, else cash"

    def warmup(self) -> int:
        return 2

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        sar = parabolic_sar(bars, self.af_start, self.af_step, self.af_max)
        return pd.Series(np.where(sar < bars["Close"], 1.0, 0.0), index=bars.index)
