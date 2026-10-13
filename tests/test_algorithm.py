"""The algorithm's guarantees: no look-ahead, limits respected, accounting right."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from aylintrade.algorithm import (
    close_prices,
    raw_weights,
    rebalance,
    simulate,
    trend_score,
)
from aylintrade.config import AlgorithmConfig, ConfigError

P = AlgorithmConfig(start="2018-01-01")


@pytest.mark.parametrize("cut", [300, 451, 700])
def test_weights_never_use_future_prices(prices: pd.DataFrame, cut: int) -> None:
    """Same weights on a truncated history, and after every later price is halved."""
    full = raw_weights(prices, P)
    pd.testing.assert_frame_equal(raw_weights(prices.iloc[:cut], P), full.iloc[:cut])
    shocked = prices.copy()
    shocked.iloc[cut:] *= 0.5
    pd.testing.assert_frame_equal(raw_weights(shocked, P).iloc[:cut], full.iloc[:cut])


def test_weights_respect_limits(prices: pd.DataFrame) -> None:
    w = raw_weights(prices, P)
    assert (w >= 0).all().all(), "long-only"
    assert (w.sum(axis=1) <= P.max_gross + 1e-9).all(), "no leverage"
    assert (w.iloc[: P.warmup - 1] == 0).all().all(), "nothing before a full year of data"
    assert (w.iloc[P.warmup + 10 :].sum(axis=1) > 0).all()


def test_trend_score_follows_the_trend(prices: pd.DataFrame) -> None:
    s = trend_score(prices, P.horizons)
    assert s.min().min() >= 0 and s.max().max() <= 1
    assert s["SPY"].iloc[-200:].mean() > 0.6  # noisy steady riser
    t = np.arange(600)
    smooth = pd.DataFrame({"V": np.exp(np.where(t < 400, -0.002 * t, -0.8 + 0.004 * (t - 400)))})
    v = trend_score(smooth, P.horizons)["V"]
    assert v.iloc[399] == 0 and v.iloc[-1] == 1  # bottom of a decline; after a long rise


def test_trend_floor_keeps_a_core_position(prices: pd.DataFrame) -> None:
    no_core = raw_weights(prices, replace(P, trend_floor=0.0))
    core = raw_weights(prices, replace(P, trend_floor=0.5))
    late = slice(P.warmup + 5, None)
    assert (no_core.iloc[late] == 0).any().any(), "a full downtrend goes to cash without a core"
    assert (core.iloc[late] > 0).all().all(), "with a core every market stays held"


def test_config_rejects_leverage() -> None:
    with pytest.raises(ConfigError, match="leverage"):
        AlgorithmConfig(max_gross=1.01)


def test_simulate_buy_and_hold_matches_price(prices: pd.DataFrame) -> None:
    target = pd.DataFrame(0.0, prices.index, prices.columns).assign(SPY=1.0)
    sim = simulate(prices, target, {"SPY": 0.0}, 0.0, prices.index[0])
    growth = float((1 + sim.returns).prod())
    assert growth == pytest.approx(prices["SPY"].iloc[-1] / prices["SPY"].iloc[0])
    assert sim.turnover.sum() == pytest.approx(1.0)  # one purchase, then holdings drift


def test_simulate_charges_costs_per_side(prices: pd.DataFrame) -> None:
    target = pd.DataFrame(0.5, prices.index, prices.columns)
    free = simulate(prices, target, {}, 0.0, prices.index[0])
    paid = simulate(prices, target, {m: 0.001 for m in prices}, 0.0, prices.index[0])
    lost = float((1 + free.returns).prod() - (1 + paid.returns).prod())
    assert lost > 0
    assert paid.returns.iloc[0] == pytest.approx(-1.5 * 0.001)  # 150% bought on day one


def test_band_skips_small_trades_but_always_enters_and_exits() -> None:
    cur = pd.Series({"A": 0.20, "B": 0.10, "C": 0.05, "D": 0.0})
    tgt = pd.Series({"A": 0.21, "B": 0.20, "C": 0.0, "D": 0.01})
    new = rebalance(tgt, cur, band=0.03)
    assert new.to_dict() == {"A": 0.20, "B": 0.20, "C": 0.0, "D": 0.01}


def test_simulate_and_rebalance_agree(prices: pd.DataFrame) -> None:
    """The backtest loop and the paper account's rebalance apply the same band rule."""
    targets = raw_weights(prices, P)
    start = prices.index[P.warmup]
    sim = simulate(prices, targets, {}, P.rebalance_band, start)
    i = sim.weights.index.get_loc(sim.weights.index[-1])
    rets = prices.pct_change().iloc[-1]
    drifted = sim.weights.iloc[i - 1] * (1 + rets)
    drifted /= 1 + (sim.weights.iloc[i - 1] * rets).sum()
    expected = rebalance(targets.iloc[-1], drifted, P.rebalance_band)
    np.testing.assert_allclose(sim.weights.iloc[-1], expected, atol=1e-12)


def test_close_prices_uses_business_days_up_to_the_common_end() -> None:
    days = pd.date_range("2024-01-01", "2024-01-14")  # includes two weekends
    coin = pd.DataFrame({"Close": np.arange(len(days), dtype=float) + 1}, index=days)
    fund = coin[coin.index.dayofweek < 5].iloc[:-1]  # misses its last day
    px = close_prices({"COIN": coin, "FUND": fund})
    assert (px.index.dayofweek < 5).all()
    assert px.index[-1] == fund.index[-1]
    assert px.loc["2024-01-08", "COIN"] == 8  # Monday carries the weekend move
