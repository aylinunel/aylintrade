from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantbt.strategies import available_strategies, create_strategy
from quantbt.strategies.indicators import bollinger_bands, parabolic_sar, wilder_rsi
from quantbt.strategies.pair_trading import engle_granger

BUILT_IN = {
    "buy_and_hold",
    "macd",
    "parabolic_sar",
    "heikin_ashi",
    "bollinger_w",
    "rsi_head_shoulders",
    "shooting_star",
    "dual_thrust",
    "london_breakout",
    "pair_trading",
}


def test_all_built_ins_registered() -> None:
    assert set(available_strategies()) >= BUILT_IN


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown parameter"):
        create_strategy("macd", {"fsat": 3})


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown strategy"):
        create_strategy("does_not_exist")


def test_params_round_trip() -> None:
    s = create_strategy("macd", {"fast": 5, "slow": 30})
    assert s.params() == {"fast": 5, "slow": 30}
    assert create_strategy("macd", s.params()) == s


def test_macd_validates_windows() -> None:
    with pytest.raises(ValueError):
        create_strategy("macd", {"fast": 30, "slow": 10})


@pytest.mark.parametrize(
    "sid", sorted(BUILT_IN - {"pair_trading", "dual_thrust", "london_breakout"})
)
def test_positions_are_bounded(sid: str, daily: pd.DataFrame) -> None:
    pos = create_strategy(sid).positions(daily)
    assert pos.between(-1, 1).all()
    assert not pos.isna().any()


def test_macd_long_in_uptrend_flat_in_downtrend() -> None:
    idx = pd.date_range("2024-01-01", periods=120)
    close = pd.Series(np.r_[np.linspace(100, 160, 60), np.linspace(160, 90, 60)], idx)
    bars = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close}, index=idx)
    pos = create_strategy("macd").positions(bars)
    assert pos.iloc[:20].eq(0).all()  # warm-up: slow average needs 21 bars
    assert pos.iloc[30:60].eq(1).all()  # rising
    assert pos.iloc[-20:].eq(0).all()  # falling


def test_dual_thrust_trades_are_well_formed(daily: pd.DataFrame) -> None:
    t = create_strategy("dual_thrust").trades(daily)
    assert set(t["side"]) <= {-1, 1}
    assert (t["entry"] > 0).all() and (t["exit"] > 0).all()
    assert pd.Timestamp(t["date"].min()) >= daily.index[5]


def test_london_breakout_trades_once_per_day(hourly: pd.DataFrame) -> None:
    t = create_strategy("london_breakout").trades(hourly)
    assert len(t) > 0
    assert t["date"].is_unique


class TestIndicators:
    def test_rsi_bounds(self, daily: pd.DataFrame) -> None:
        r = wilder_rsi(daily["Close"]).dropna()
        assert r.between(0, 100).all()

    def test_bollinger_ordering(self, daily: pd.DataFrame) -> None:
        bb = bollinger_bands(daily["Close"]).dropna()
        assert (bb["lower"] <= bb["mid"]).all() and (bb["mid"] <= bb["upper"]).all()

    def test_sar_below_price_in_steady_uptrend(self) -> None:
        idx = pd.date_range("2024-01-01", periods=60)
        c = pd.Series(np.linspace(100, 200, 60), idx)
        bars = pd.DataFrame({"High": c * 1.01, "Low": c * 0.99, "Close": c}, index=idx)
        sar = parabolic_sar(bars)
        assert sar.iloc[:2].isna().all()
        assert (sar.iloc[2:] < bars["Low"].iloc[2:]).all()


def test_engle_granger_detects_cointegration(cointegrated_pair) -> None:
    a, b = cointegrated_pair
    ok, params, _ = engle_granger(a.to_numpy(), b.to_numpy())
    assert ok and params[1] == pytest.approx(0.9, abs=0.1)


def test_engle_granger_false_positive_rate_is_bounded() -> None:
    """Independent random walks should rarely look cointegrated.

    Correct residual critical values should keep the original optimistic false-positive
    rate down. A 40-case deterministic sample bounds regression behavior, not test size.
    """
    hits = 0
    for seed in range(40):
        walks = np.cumsum(np.random.default_rng(seed).normal(size=(2, 400)), axis=1) + 100
        hits += engle_granger(walks[0], walks[1])[0]
    assert hits / 40 < 0.15
