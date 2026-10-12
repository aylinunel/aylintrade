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


def make_prices(n: int = 900, seed: int = 4) -> pd.DataFrame:
    """Business-day closes for three markets: a steady riser, a choppy one, a crash-then-recover."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    up = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.01, n)))
    chop = 50 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
    crash = 20 * np.exp(
        np.cumsum(np.r_[rng.normal(-0.002, 0.03, n // 2), rng.normal(0.002, 0.03, n - n // 2)])
    )
    return pd.DataFrame({"SPY": up, "AAA": chop, "BBB": crash}, index=idx)


@pytest.fixture(scope="session")
def prices() -> pd.DataFrame:
    return make_prices()
