"""Transaction-cost models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ProportionalCost:
    """A fixed fraction of traded notional per side (spread + fees + slippage).

    ``turnover`` is the absolute change in exposure, so going from flat to fully long costs
    one side, and flipping from long to short costs two.
    """

    per_side: float

    def __post_init__(self) -> None:
        if self.per_side < 0:
            raise ValueError("cost per side must be non-negative")

    def __call__(self, turnover: pd.Series) -> pd.Series:
        return turnover.abs() * self.per_side

    def round_trip(self) -> float:
        return 2 * self.per_side
