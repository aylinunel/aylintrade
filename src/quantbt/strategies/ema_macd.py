"""Standard EMA MACD and median-price Awesome Oscillator trend templates."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .base import PositionStrategy, register


@register
@dataclass(frozen=True)
class EMAMACD(PositionStrategy):
    fast: int = 12
    slow: int = 26
    signal: int = 9
    id = "ema_macd"
    label = "EMA MACD"
    description = "Long when the EMA MACD is above its EMA signal line"

    def __post_init__(self) -> None:
        if not 0 < self.fast < self.slow or self.signal < 1:
            raise ValueError("Need 0 < fast < slow and positive signal")

    def warmup(self) -> int:
        return 3 * self.slow + self.signal

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["Close"]
        line = (
            close.ewm(span=self.fast, adjust=False).mean()
            - close.ewm(span=self.slow, adjust=False).mean()
        )
        pos = (line > line.ewm(span=self.signal, adjust=False).mean()).astype(float)
        pos.iloc[: self.warmup()] = 0
        return pos


@register
@dataclass(frozen=True)
class AwesomeOscillator(PositionStrategy):
    fast: int = 5
    slow: int = 34
    id = "awesome_oscillator"
    label = "Awesome Oscillator"
    description = "Long on a positive and rising median-price oscillator"

    def __post_init__(self) -> None:
        if not 0 < self.fast < self.slow:
            raise ValueError("Need 0 < fast < slow")

    def warmup(self) -> int:
        return self.slow + 1

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        median = (bars["High"] + bars["Low"]) / 2
        oscillator = median.rolling(self.fast).mean() - median.rolling(self.slow).mean()
        return ((oscillator > 0) & (oscillator > oscillator.shift(1))).astype(float)
