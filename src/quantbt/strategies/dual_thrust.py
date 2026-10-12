"""Dual Thrust opening-range breakout (intraday, run on daily bars)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import TRADE_COLUMNS, IntradayStrategy, register


@register
@dataclass(frozen=True)
class DualThrust(IntradayStrategy):
    """Buy above ``open + k * range``, sell below ``open - (1 - k) * range``, flat at the close.

    ``range`` is the larger of (highest high - lowest close) and (highest close - lowest low)
    over the previous ``lookback`` days (the original included the current day, which is
    look-ahead). With daily bars the intraday order is unknown when both thresholds break on
    the same day, so the worse of the two possible sequences is assumed.
    """

    lookback: int = 5
    k: float = 0.5

    id = "dual_thrust"
    label = "Dual Thrust"
    description = "Intraday long/short breakout from the open, flat at the close"

    def warmup(self) -> int:
        return self.lookback

    def trades(self, bars: pd.DataFrame) -> pd.DataFrame:
        prev = bars.shift(1)
        hh = prev["High"].rolling(self.lookback).max()
        ll = prev["Low"].rolling(self.lookback).min()
        hc = prev["Close"].rolling(self.lookback).max()
        lc = prev["Close"].rolling(self.lookback).min()
        rng = np.maximum(hh - lc, hc - ll)
        upper = bars["Open"] + self.k * rng
        lower = bars["Open"] - (1 - self.k) * rng

        rows: list[tuple[pd.Timestamp, int, float, float]] = []
        for day, r, up, lo in zip(bars.index, bars.itertuples(), upper, lower, strict=True):
            if not np.isfinite(up) or up <= lo:
                continue
            broke_up, broke_down = r.High > up, r.Low < lo
            if broke_up and broke_down:
                long_first = [(day, 1, up, lo), (day, -1, lo, r.Close)]
                short_first = [(day, -1, lo, up), (day, 1, up, r.Close)]
                pnl = lambda seq: sum(s * (x / e - 1) for _, s, e, x in seq)  # noqa: E731
                rows += min(long_first, short_first, key=pnl)
            elif broke_up:
                rows.append((day, 1, up, r.Close))
            elif broke_down:
                rows.append((day, -1, lo, r.Close))
        return pd.DataFrame(rows, columns=TRADE_COLUMNS)
