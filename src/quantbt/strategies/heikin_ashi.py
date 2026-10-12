"""Heikin-Ashi candle momentum."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register
from .indicators import heikin_ashi


@register
@dataclass(frozen=True)
class HeikinAshi(PositionStrategy):
    """Scales into up to ``max_units`` longs and exits all of them on the repo's exit candle.

    Entry (as written in the original script): a bearish Heikin-Ashi candle with no upper
    wick and a larger body than the previous bearish candle. Exit: a bullish candle with no
    lower wick following another bullish candle. Exposure is ``units / max_units``.
    """

    max_units: int = 3

    id = "heikin_ashi"
    label = "Heikin-Ashi"
    description = "Scales into up to 3 longs on the repo's Heikin-Ashi signal"

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        ha = heikin_ashi(bars)
        o, h, l, c = (ha[k].to_numpy() for k in ("open", "high", "low", "close"))
        units = np.zeros(len(ha))
        u = 0
        for i in range(1, len(ha)):
            bearish, prev_bearish = o[i] > c[i], o[i - 1] > c[i - 1]
            bullish, prev_bullish = o[i] < c[i], o[i - 1] < c[i - 1]
            if (
                bearish
                and o[i] == h[i]
                and abs(o[i] - c[i]) > abs(o[i - 1] - c[i - 1])
                and prev_bearish
            ):
                u = min(u + 1, self.max_units)
            elif bullish and o[i] == l[i] and prev_bullish:
                u = 0
            units[i] = u
        return pd.Series(units / self.max_units, index=bars.index)
