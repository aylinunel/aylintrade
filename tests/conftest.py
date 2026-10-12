"""Shared synthetic market data. Seeded, so every test run sees identical prices."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_bars(
    n: int,
    freq: str = "D",
    seed: int = 0,
    start: str = "2020-01-01",
    drift: float = 0.0003,
    vol: float = 0.02,
) -> pd.DataFrame:
    """Random-walk OHLCV with realistic candle shapes (High >= max(Open, Close), etc.)."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, vol / 4, n))
    wick = np.abs(rng.normal(0, vol / 2, (2, n)))
    high = np.maximum(open_, close) * (1 + wick[0])
    low = np.minimum(open_, close) * (1 - wick[1])
    idx = pd.date_range(start, periods=n, freq=freq, name="Date")
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": rng.integers(1_000, 10_000, n).astype(float),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def daily() -> pd.DataFrame:
    return make_bars(500, seed=1)


@pytest.fixture(scope="session")
def hourly() -> pd.DataFrame:
    return make_bars(24 * 120, freq="h", seed=2, vol=0.006)


@pytest.fixture(scope="session")
def cointegrated_pair() -> tuple[pd.Series, pd.Series]:
    """Two series sharing a random-walk trend plus a mean-reverting spread."""
    rng = np.random.default_rng(3)
    n = 400
    trend = 100 + np.cumsum(rng.normal(0, 1, n))
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = 0.8 * spread[i - 1] + rng.normal(0, 1)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(trend, idx), pd.Series(0.9 * trend + 10 + spread, idx)
