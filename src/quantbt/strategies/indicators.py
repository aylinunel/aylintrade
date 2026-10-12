"""Technical indicators shared by the strategies. All are causal: value at t uses data <= t."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder's smoothing (an EMA with alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    std = close.rolling(window).std()
    mid = close.rolling(window).mean()
    return pd.DataFrame(
        {"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std, "std": std}
    )


def heikin_ashi(bars: pd.DataFrame) -> pd.DataFrame:
    """Heikin-Ashi candles: smoothed open/high/low/close."""
    o, h, l, c = (bars[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    ha_close = (o + h + l + c) / 4
    ha_open = np.empty_like(ha_close)
    ha_open[0] = o[0]
    for i in range(1, len(ha_close)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2
    stacked = np.vstack([ha_open, ha_close, l, h])
    ha_high, ha_low = stacked.max(axis=0), stacked.min(axis=0)
    return pd.DataFrame(
        {"open": ha_open, "high": ha_high, "low": ha_low, "close": ha_close}, index=bars.index
    )


def parabolic_sar(
    bars: pd.DataFrame, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2
) -> pd.Series:
    """Welles Wilder's Parabolic Stop-and-Reverse. The first two values are NaN."""
    h, l, c = (bars[k].to_numpy(float) for k in ("High", "Low", "Close"))
    n = len(c)
    sar = np.full(n, np.nan)
    if n < 3:
        return pd.Series(sar, index=bars.index)
    up = c[1] > c[0]
    sar[1] = l[0] if up else h[0]
    ep = h[1] if up else l[1]
    af = af_start
    for i in range(2, n):
        s = sar[i - 1] + af * (ep - sar[i - 1])
        if up:
            s = min(s, l[i - 1], l[i - 2])
            if l[i] < s:
                up, s, ep, af = False, ep, l[i], af_start
            elif h[i] > ep:
                ep, af = h[i], min(af + af_step, af_max)
        else:
            s = max(s, h[i - 1], h[i - 2])
            if h[i] > s:
                up, s, ep, af = True, ep, h[i], af_start
            elif l[i] < ep:
                ep, af = l[i], min(af + af_step, af_max)
        sar[i] = s
    out = pd.Series(sar, index=bars.index)
    out.iloc[1] = np.nan
    return out
