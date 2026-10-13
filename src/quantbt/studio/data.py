"""Strict completed-bar inputs and reproducible dataset identities."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..data import DataStore
from ..data.schema import OHLCV_COLUMNS

INTERVALS = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1)}


@dataclass(frozen=True)
class Settings:
    market: str = "BTC"
    interval: str = "1h"
    source: str = "demo"
    capital: float = 5000.0
    risk_fraction: float = 0.005
    stop_fraction: float = 0.025
    max_exposure: float = 0.5
    max_drawdown: float = 0.2
    fee: float = 0.001
    slippage: float = 0.0005
    min_trades: int = 10

    def __post_init__(self) -> None:
        if self.market not in {"BTC", "ETH"} or self.interval not in INTERVALS:
            raise ValueError("Choose BTC or ETH and 1h, 4h or 1d bars")
        if self.source not in {"demo", "cache"}:
            raise ValueError("source must be demo or cache")
        limits = {
            "capital": (100.0, 1_000_000.0),
            "risk_fraction": (0.0001, 0.02),
            "stop_fraction": (0.005, 0.2),
            "max_exposure": (0.01, 1.0),
            "max_drawdown": (0.01, 0.8),
            "fee": (0.0, 0.01),
            "slippage": (0.0, 0.01),
        }
        for key, (lo, hi) in limits.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise ValueError(f"{key} must be numeric")
            if not np.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
        if type(self.min_trades) is not int or not 1 <= self.min_trades <= 1000:
            raise ValueError("min_trades must be an integer between 1 and 1000")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def demo_bars(interval: str, now: pd.Timestamp, n: int = 1500) -> pd.DataFrame:
    rng = np.random.default_rng(41)
    t = np.arange(n)
    changes = 0.001 * np.sin(t / 75) + rng.normal(0, 0.004, n)
    close = 30000 * np.exp(np.cumsum(changes))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 0.0004, n))
    wick = rng.uniform(0.0005, 0.006, (2, n))
    delta = INTERVALS[interval]
    end = now.floor(delta) - delta
    return pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) * (1 + wick[0]),
            "Low": np.minimum(open_, close) * (1 - wick[1]),
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=pd.date_range(end=end, periods=n, freq=delta, name="Date"),
    )


def load_bars(settings: Settings, root: Path, now: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    now = pd.Timestamp(now).tz_convert("UTC").tz_localize(None)
    if settings.source == "demo":
        bars = demo_bars(settings.interval, now)
        provenance = {"source": "generated", "synthetic": True}
    else:
        interval = "1h" if settings.interval == "4h" else settings.interval
        bars = DataStore(root).load(settings.market, interval)
        provenance = bars.attrs.get("quantbt_provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("Invalid dataset provenance")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise ValueError("Bars require a DatetimeIndex of UTC bar open times")
    bars = bars.copy()
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is not None:
        bars.index = idx.tz_convert("UTC").tz_localize(None)
    if bars.index.hasnans or not bars.index.is_monotonic_increasing or not bars.index.is_unique:
        raise ValueError("Rejecting duplicate, unsorted or invalid timestamps")
    if any(c not in bars for c in OHLCV_COLUMNS):
        raise ValueError("Input requires Open, High, Low, Close and Volume")
    bars = bars[OHLCV_COLUMNS].astype(float)
    raw = bars.to_numpy()
    if not np.isfinite(raw).all() or (raw[:, :4] <= 0).any() or (raw[:, 4] <= 0).any():
        raise ValueError("Input requires finite positive OHLCV observations")
    if (
        (bars.High < bars[["Open", "Close", "Low"]].max(axis=1))
        | (bars.Low > bars[["Open", "Close", "High"]].min(axis=1))
    ).any():
        raise ValueError("Inconsistent candle geometry")
    if len(bars) > 200_000:
        raise ValueError("Research runs accept at most 200000 bars")
    base_delta = (
        INTERVALS["1h"]
        if settings.interval == "4h" and settings.source == "cache"
        else INTERVALS[settings.interval]
    )
    bars = bars[bars.index + base_delta <= now]
    gaps = not bars.index.to_series().diff().dropna().eq(base_delta).all()
    if gaps:
        raise ValueError("Missing bars: repair the feed before research")
    if settings.interval == "4h" and settings.source == "cache":
        counts = bars.Close.resample("4h").count()
        bars = bars.resample("4h").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        )
        bars = bars[counts == 4]
    if len(bars) < 600:
        raise ValueError("At least 600 completed bars are required")
    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(bars, index=True).to_numpy().tobytes()
    ).hexdigest()
    age = (now - (bars.index[-1] + INTERVALS[settings.interval])).total_seconds()
    manifest = {
        "id": fingerprint[:16],
        "sha256": fingerprint,
        "rows": len(bars),
        "market": settings.market,
        "interval": settings.interval,
        "source": settings.source,
        "synthetic": settings.source == "demo" or provenance.get("synthetic") is True,
        "provenance": provenance,
        "provenance_recorded": (
            provenance.get("source") == "binance_static_klines"
            and provenance.get("symbol") == settings.market + "USDT"
            and provenance.get("synthetic") is False
            and isinstance(provenance.get("retrieved_at"), str)
        ),
        "start": bars.index[0].isoformat(),
        "end": bars.index[-1].isoformat(),
        "as_of": now.isoformat() + "Z",
        "age_seconds": age,
        "fresh": age <= 2 * INTERVALS[settings.interval].total_seconds(),
        "timestamp_convention": "UTC bar open; only completed candles",
    }
    return bars, manifest
