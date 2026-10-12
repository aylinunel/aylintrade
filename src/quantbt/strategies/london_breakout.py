"""London Breakout: trade the break of the last pre-London hour's range."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .base import TRADE_COLUMNS, IntradayStrategy, register


@register
@dataclass(frozen=True)
class LondonBreakout(IntradayStrategy):
    """Opening-range breakout at the London open, on hourly bars (UTC).

    The range is the high/low of the ``range_hour`` bar (07:00-07:59 UTC). If the
    ``entry_hour`` bar breaks one side, enter at the threshold (or the open if it gapped
    through). Skip the day if the entry is more than ``max_slippage`` beyond the threshold or
    if both sides break inside the entry bar (order unknown). Take profit and stop loss sit at
    +/- ``max_slippage / 2``; if both are inside one bar the stop is assumed first. Anything
    still open is closed at the last bar before ``close_hour``.

    The original used 0.01 in GBP/USD price units (about 0.77%) for ``max_slippage``.
    """

    range_hour: int = 7
    entry_hour: int = 8
    close_hour: int = 17
    max_slippage: float = 0.0075

    id = "london_breakout"
    label = "London Breakout"
    description = "Trades the 08:00 UTC London-open breakout of the 07:00 hour's range"
    interval = "1h"

    def trades(self, bars: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for day, g in bars.groupby(pd.DatetimeIndex(bars.index).normalize()):
            hours = pd.DatetimeIndex(g.index).hour
            rng, entry_bar = g[hours == self.range_hour], g[hours == self.entry_hour]
            if rng.empty or entry_bar.empty:
                continue
            upper, lower = rng["High"].iloc[0], rng["Low"].iloc[0]
            b = entry_bar.iloc[0]
            up, down = b["High"] > upper, b["Low"] < lower
            if up == down:
                continue
            side = 1 if up else -1
            level = upper if up else lower
            entry = max(level, b["Open"]) if up else min(level, b["Open"])
            if abs(entry - level) / level > self.max_slippage:
                continue
            target = entry * (1 + side * self.max_slippage / 2)
            stop = entry * (1 - side * self.max_slippage / 2)
            later = g[(hours > self.entry_hour) & (hours < self.close_hour)]
            exit_price = later["Close"].iloc[-1] if len(later) else b["Close"]
            for bar in later.itertuples():
                stopped = bar.Low <= stop if side == 1 else bar.High >= stop
                hit = bar.High >= target if side == 1 else bar.Low <= target
                if stopped:
                    exit_price = stop
                    break
                if hit:
                    exit_price = target
                    break
            rows.append((day, side, entry, exit_price))
        return pd.DataFrame(rows, columns=TRADE_COLUMNS)
