from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantbt.engine import ProportionalCost, compute_metrics, run
from quantbt.engine.backtest import count_entries, returns_from_positions, run_intraday
from quantbt.strategies import create_strategy
from quantbt.strategies.base import TRADE_COLUMNS, IntradayStrategy


def test_position_earns_next_bar_return_and_pays_cost() -> None:
    idx = pd.date_range("2024-01-01", periods=5)
    close = pd.Series([100.0, 110.0, 121.0, 108.9, 108.9], idx)
    pos = pd.Series([0.0, 1.0, 1.0, 0.0, 0.0], idx)
    net, held = returns_from_positions(pos, close, ProportionalCost(0.001))
    # long decided at bar 1's close: earns bar 2 (+10%) and pays the entry cost on bar 2.
    # Exit decided at bar 3's close: bar 3's -10% is still held; the exit cost lands on bar 4.
    expected = [0.0, 0.0, 0.10 - 0.001, -0.10, -0.001]
    np.testing.assert_allclose(net.to_numpy(), expected)
    assert held.tolist() == [0.0, 0.0, 1.0, 1.0, 0.0]


def test_flip_costs_two_sides() -> None:
    idx = pd.date_range("2024-01-01", periods=3)
    close = pd.Series(100.0, idx)
    net, _ = returns_from_positions(
        pd.Series([1.0, -1.0, -1.0], idx), close, ProportionalCost(0.01)
    )
    assert net.iloc[2] == pytest.approx(-0.02)


def test_count_entries() -> None:
    assert count_entries(pd.Series([0, 1, 1, 0, -1, 1, 1, 0.0])) == 3


def test_buy_and_hold_matches_price_return(daily: pd.DataFrame) -> None:
    res = run(create_strategy("buy_and_hold"), daily, ProportionalCost(0.0))
    assert res.equity().iloc[-1] == pytest.approx(daily["Close"].iloc[-1] / daily["Close"].iloc[0])
    assert res.n_trades == 1


def test_intraday_pnl_includes_round_trip_cost() -> None:
    class OneTrade(IntradayStrategy):
        id = label = "one"

        def trades(self, bars):
            return pd.DataFrame([(bars.index[1], -1, 100.0, 95.0)], columns=TRADE_COLUMNS)

    idx = pd.date_range("2024-01-01", periods=3)
    bars = pd.DataFrame({"Close": [1.0, 1.0, 1.0]}, index=idx)
    res = run_intraday(OneTrade(), bars, idx, ProportionalCost(0.001))
    assert res.returns.tolist() == pytest.approx([0.0, 0.05 - 0.002, 0.0])
    assert res.n_trades == 1


def test_run_requires_needed_data(daily: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="1h"):
        run(create_strategy("london_breakout"), daily, ProportionalCost(0.0))
    with pytest.raises(ValueError, match="partner"):
        run(create_strategy("pair_trading"), daily, ProportionalCost(0.0))


def test_pair_legs_are_opposite(cointegrated_pair) -> None:
    a, b = cointegrated_pair
    pa, pb = create_strategy("pair_trading", {"window": 60}).positions(a, b)
    assert ((pa * pb) <= 0).all()
    active = pa != 0
    np.testing.assert_allclose((pa.abs() + pb.abs())[active], 1.0)
    assert not pa[active].abs().eq(0.5).all()


class TestMetrics:
    def test_known_values(self) -> None:
        r = pd.Series([0.01] * 252)
        m = compute_metrics(r, 252)
        assert m.cagr == pytest.approx(1.01**252 - 1)
        assert m.max_drawdown == 0.0
        assert m.sharpe == 0.0  # zero volatility

    def test_drawdown(self) -> None:
        m = compute_metrics(pd.Series([0.0, 0.5, -0.5, 0.2]), 252)
        assert m.max_drawdown == pytest.approx(-0.5)

    def test_wipeout(self) -> None:
        assert compute_metrics(pd.Series([0.1, -1.0, 0.0]), 252).cagr == -1.0

    def test_needs_data(self) -> None:
        with pytest.raises(ValueError):
            compute_metrics(pd.Series([0.1]), 252)
