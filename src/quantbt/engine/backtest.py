"""Turn strategy output into per-period net returns.

Timing convention (no look-ahead): a position decided at the close of bar *t* is held over
bar *t+1* and earns that bar's close-to-close return. The cost of changing the position is
booked on bar *t+1* as well. Intraday strategies book each round trip on its own day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..strategies.base import IntradayStrategy, PairStrategy, PositionStrategy, Strategy
from .costs import ProportionalCost


@dataclass
class BacktestResult:
    """Net returns of one strategy on one market over its evaluation window."""

    strategy: str
    returns: pd.Series
    n_trades: int
    exposure: float
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def start(self) -> pd.Timestamp:
        return pd.Timestamp(self.returns.index[0])

    @property
    def end(self) -> pd.Timestamp:
        return pd.Timestamp(self.returns.index[-1])

    def equity(self) -> pd.Series:
        return (1 + self.returns).cumprod()


def count_entries(pos: pd.Series) -> int:
    """Number of times a new position is opened (from flat, or flipped to the other side)."""
    side = np.sign(pos.fillna(0.0))
    prev = side.shift(1, fill_value=0.0)
    return int(((side != 0) & (side != prev)).sum())


def returns_from_positions(
    pos: pd.Series, close: pd.Series, cost: ProportionalCost
) -> tuple[pd.Series, pd.Series]:
    """Net returns and the exposure actually held each bar."""
    pos = pos.reindex(close.index).fillna(0.0)
    held = pos.shift(1, fill_value=0.0)
    turnover = pos.diff().fillna(pos)
    net = held * close.pct_change().fillna(0.0) - cost(turnover).shift(1, fill_value=0.0)
    return net, held


def run_position(
    strategy: PositionStrategy, bars: pd.DataFrame, cost: ProportionalCost
) -> BacktestResult:
    pos = strategy.positions(bars)
    net, held = returns_from_positions(pos, bars["Close"], cost)
    return BacktestResult(strategy.id, net, count_entries(pos), float((held != 0).mean()))


def run_intraday(
    strategy: IntradayStrategy,
    bars: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    cost: ProportionalCost,
) -> BacktestResult:
    """``bars`` are the strategy's own bars (daily or hourly); ``calendar`` is the daily index
    returns are reported on. The window starts at the first session the bars cover."""
    trades = strategy.trades(bars)
    if strategy.interval == "1d":
        start = bars.index[min(strategy.warmup(), len(bars) - 1)]
    else:
        start = bars.index[0].normalize()
    days = calendar[calendar >= start]
    if trades.empty:
        daily = pd.Series(0.0, index=days)
    else:
        pnl = trades["side"] * (trades["exit"] / trades["entry"] - 1) - cost.round_trip()
        daily = pnl.groupby(pd.DatetimeIndex(trades["date"])).sum().reindex(days).fillna(0.0)
    traded_days = int((daily != 0).sum())
    return BacktestResult(strategy.id, daily, len(trades), traded_days / max(len(daily), 1))


def run_pair(
    strategy: PairStrategy, a: pd.Series, b: pd.Series, cost: ProportionalCost
) -> BacktestResult:
    """Leg ``a`` is the market under test; ``b`` is its partner. Uses their common dates."""
    idx = a.index.intersection(b.index)
    a, b = a.reindex(idx), b.reindex(idx)
    pos_a, pos_b = strategy.positions(a, b)
    net_a, held_a = returns_from_positions(pos_a, a, cost)
    net_b, _ = returns_from_positions(pos_b, b, cost)
    start = idx[min(strategy.warmup(), len(idx) - 1)]
    net = (net_a + net_b)[start:]
    held = held_a[start:]
    return BacktestResult(strategy.id, net, count_entries(pos_a[start:]), float((held != 0).mean()))


def run(
    strategy: Strategy,
    daily: pd.DataFrame,
    cost: ProportionalCost,
    hourly: pd.DataFrame | None = None,
    partner: pd.DataFrame | None = None,
) -> BacktestResult:
    """Dispatch on strategy kind. Raises ``ValueError`` if required data is missing."""
    if isinstance(strategy, PositionStrategy):
        return run_position(strategy, daily, cost)
    if isinstance(strategy, IntradayStrategy):
        bars = daily if strategy.interval == "1d" else hourly
        if bars is None:
            raise ValueError(f"needs {strategy.interval} data")
        return run_intraday(strategy, bars, pd.DatetimeIndex(daily.index), cost)
    if isinstance(strategy, PairStrategy):
        if partner is None:
            raise ValueError("needs a pair partner (set `pair_with` on the market)")
        return run_pair(strategy, daily["Close"], partner["Close"], cost)
    raise TypeError(f"unsupported strategy type {type(strategy).__name__}")
