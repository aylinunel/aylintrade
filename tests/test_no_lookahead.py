"""The most important property of a backtest: no strategy may use future data.

Each test computes signals on the full history and on a truncated history, and checks
that every signal the truncated run produced is identical. A strategy that peeks ahead
(e.g. uses tomorrow's high to decide today) fails these tests.
"""

from __future__ import annotations

import pandas as pd
import pytest

from quantbt.strategies import available_strategies, create_strategy, get_strategy_class
from quantbt.strategies.base import IntradayStrategy, PairStrategy, PositionStrategy

# Looser thresholds so pattern strategies actually trade on synthetic data.
ACTIVE_PARAMS = {
    "bollinger_w": {"tolerance": 0.05},
    "rsi_head_shoulders": {"tolerance": 0.03},
    "shooting_star": {"body_size": 2.0, "lower_wick": 1.0},
    "pair_trading": {"window": 60},
}
CUTS = (150, 260, 333, 499)


def _ids(kind: type) -> list[str]:
    return [s for s in available_strategies() if issubclass(get_strategy_class(s), kind)]


@pytest.mark.parametrize("sid", _ids(PositionStrategy))
def test_position_strategies_are_causal(sid: str, daily: pd.DataFrame) -> None:
    strategy = create_strategy(sid, ACTIVE_PARAMS.get(sid))
    full = strategy.positions(daily)
    assert full.index.equals(daily.index)
    for cut in CUTS:
        part = strategy.positions(daily.iloc[:cut])
        pd.testing.assert_series_equal(
            part, full.iloc[:cut], check_names=False, obj=f"{sid} positions up to bar {cut}"
        )


@pytest.mark.parametrize("sid", _ids(IntradayStrategy))
def test_intraday_strategies_are_causal(
    sid: str, daily: pd.DataFrame, hourly: pd.DataFrame
) -> None:
    strategy = create_strategy(sid)
    bars = hourly if strategy.interval == "1h" else daily
    full = strategy.trades(bars)
    assert len(full) > 0, "fixture should produce trades"
    cut_day = bars.index[len(bars) // 2].normalize()
    part = strategy.trades(bars[bars.index < cut_day])
    expected = full[pd.DatetimeIndex(full["date"]) < cut_day].reset_index(drop=True)
    pd.testing.assert_frame_equal(part.reset_index(drop=True), expected, check_dtype=False)


@pytest.mark.parametrize("sid", _ids(PairStrategy))
def test_pair_strategies_are_causal(sid: str, cointegrated_pair) -> None:
    a, b = cointegrated_pair
    strategy = create_strategy(sid, ACTIVE_PARAMS.get(sid))
    full_a, full_b = strategy.positions(a, b)
    assert (full_a != 0).any(), "fixture should produce trades"
    for cut in (120, 250):
        part_a, part_b = strategy.positions(a.iloc[:cut], b.iloc[:cut])
        pd.testing.assert_series_equal(part_a, full_a.iloc[:cut])
        pd.testing.assert_series_equal(part_b, full_b.iloc[:cut])


@pytest.mark.parametrize("sid", _ids(PositionStrategy))
def test_future_shock_does_not_change_past(sid: str, daily: pd.DataFrame) -> None:
    """Crash every price after bar 300; positions up to bar 300 must not move."""
    strategy = create_strategy(sid, ACTIVE_PARAMS.get(sid))
    shocked = daily.copy()
    shocked.iloc[301:, :4] *= 0.5
    pd.testing.assert_series_equal(
        strategy.positions(shocked).iloc[:301], strategy.positions(daily).iloc[:301]
    )
