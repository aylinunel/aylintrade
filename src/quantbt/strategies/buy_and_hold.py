"""Benchmark: hold the asset the whole time."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .base import PositionStrategy, register


@register
@dataclass(frozen=True)
class BuyAndHold(PositionStrategy):
    id = "buy_and_hold"
    label = "Buy & hold"
    description = (
        "Fully invested from the first bar; the benchmark every strategy is compared with."
    )

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=bars.index)
