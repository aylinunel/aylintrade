"""Head-and-shoulders top with an RSI-based exit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register
from .indicators import wilder_rsi


@register
@dataclass(frozen=True)
class RSIHeadShoulders(PositionStrategy):
    """Short a head-and-shoulders top at the neckline; cover on an RSI rebound or a time stop.

    Within the last ``lookback`` bars the pattern needs a head (the highest close), a
    neckline level equal to today's close (within ``tolerance``) on both sides of the head,
    and a left shoulder at least ``1.1 x tolerance`` below the head and above the neckline,
    matched by a right shoulder. Exit when RSI rises ``exit_rsi_rise`` points above its
    value at entry, or after ``max_hold`` bars. ``tolerance`` is a fraction of price (the
    original used 0.2 price units).
    """

    rsi_period: int = 14
    lookback: int = 25
    tolerance: float = 0.01
    exit_rsi_rise: float = 4.0
    max_hold: int = 5
    head_ratio: float = 1.1
    shoulder_ratio: float = 1.1

    id = "rsi_head_shoulders"
    label = "RSI pattern (H&S)"
    description = "Short on a head-and-shoulders top, cover on an RSI rebound"

    def warmup(self) -> int:
        return self.lookback + self.rsi_period

    def _pattern(self, c: np.ndarray, i: int) -> bool:
        lb, d = self.lookback, self.tolerance * c[i]
        window = c[i - lb : i]
        if c[i] == window.max():
            return False
        head = i - lb + int(np.argmax(window))
        neck = c[i]
        if abs(c[head] - neck) <= self.head_ratio * d:
            return False
        right_neck = next((x for x in range(head, i) if abs(c[x] - neck) < d), None)
        left_neck = next((x for x in range(head, i - lb + 1, -1) if abs(c[x] - neck) < d), None)
        if right_neck is None or left_neck is None:
            return False
        left_start = next((x for x in range(i - lb, left_neck) if abs(c[x] - neck) < d), None)
        if left_start is None or left_neck <= left_start:
            return False
        shoulder_i = left_start + int(np.argmax(c[left_start:left_neck]))
        shoulder = c[shoulder_i]
        if not (
            shoulder - neck > self.shoulder_ratio * d
            and c[head] - shoulder > self.shoulder_ratio * d
        ):
            return False
        return any(abs(c[x] - shoulder) < d for x in range(right_neck, i))

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        c = bars["Close"].to_numpy(float)
        rsi = wilder_rsi(bars["Close"], self.rsi_period).to_numpy()
        pos = np.zeros(len(c))
        entry_rsi, held = None, 0
        for i in range(self.warmup(), len(c)):
            if entry_rsi is None:
                if self._pattern(c, i):
                    entry_rsi, held = rsi[i], 0
            else:
                held += 1
                if rsi[i] - entry_rsi > self.exit_rsi_rise or held > self.max_hold:
                    entry_rsi = None
            pos[i] = -1.0 if entry_rsi is not None else 0.0
        return pd.Series(pos, index=bars.index)
