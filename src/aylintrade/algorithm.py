"""The Aylin trend portfolio: which markets to hold, and how much of each.

Four steps, each causal (the value on day t uses closes up to day t only):

1. **Trend score** per market, 0 to 1: the share of eight votes that say "up". Four horizons
   (1, 3, 6 and 12 months), each voting twice: is the price above its moving average, and is
   the return over the horizon positive. A ``trend_floor`` of 0.25 keeps a quarter of each
   market's full position as a core holding; the trend decides the other three quarters.
   Long-only: the rest of a market in a downtrend is held as cash.
2. **Risk parity**: each market's weight is proportional to 1 / its volatility, so a calm bond
   fund and a wild coin contribute similar risk. Multiplied by the trend score.
3. **Volatility target**: the whole book is scaled so its expected volatility (from the trailing
   covariance of returns) is ``target_vol``, never above ``max_gross`` (1.0 = no leverage).
4. **Rebalance band**: a weight only moves when the target differs by more than
   ``rebalance_band``, which cuts trading costs; entries from zero and exits to zero
   always go through.

Adapted from the MACD trend filter of je-suis-tm/quant-trading (the only one of its ten
strategies that beat holding after costs), extended to time-series momentum at several
horizons with volatility scaling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import AlgorithmConfig

PERIODS_PER_YEAR = 252  # everything runs on business days


def close_prices(daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Business-day closes, one column per market, up to the last day every market has.

    Crypto trades at weekends; its weekend moves fold into Monday. Gaps (holidays) are
    forward-filled, which books a zero return until the next real close.
    """
    px = pd.DataFrame({m: df["Close"] for m, df in daily.items()})
    last_common = min(df.index[-1] for df in daily.values())
    days = pd.DatetimeIndex(px.index)
    px = px[(days.dayofweek < 5) & (days <= last_common)]
    return px.ffill()


def trend_score(px: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    """Share of up-votes in [0, 1]; NaN until the longest horizon has data."""
    votes = [(px > px.rolling(h).mean()).astype(float) for h in horizons]
    votes += [(px.pct_change(h, fill_method=None) > 0).astype(float) for h in horizons]
    score = sum(votes[1:], votes[0]) / len(votes)
    return score.where(px.rolling(max(horizons)).mean().notna())


def volatility(px: pd.DataFrame, span: int) -> pd.DataFrame:
    """Annualised exponentially weighted volatility of daily returns."""
    return px.pct_change(fill_method=None).ewm(span=span, min_periods=span).std() * np.sqrt(
        PERIODS_PER_YEAR
    )


def raw_weights(px: pd.DataFrame, p: AlgorithmConfig) -> pd.DataFrame:
    """Target weights before the rebalance band (steps 1 to 3)."""
    score = trend_score(px, p.horizons)
    score = p.trend_floor + (1 - p.trend_floor) * score
    inv_vol = (1 / volatility(px, p.vol_span)).where(score.notna())
    w = inv_vol.div(inv_vol.sum(axis=1), axis=0) * score
    rets = px.pct_change(fill_method=None).fillna(0.0).to_numpy()
    out = np.zeros(w.shape)
    wv = w.fillna(0.0).to_numpy()
    for i in range(p.cov_window, len(w)):
        x = wv[i]
        if not x.any():
            continue
        cov = np.cov(rets[i - p.cov_window + 1 : i + 1], rowvar=False).reshape(len(x), len(x))
        port_vol = np.sqrt(max(float(x @ cov @ x), 1e-12) * PERIODS_PER_YEAR)
        x = x * p.target_vol / port_vol
        out[i] = x / max(np.abs(x).sum() / p.max_gross, 1.0)
    return pd.DataFrame(out, index=w.index, columns=w.columns)


def rebalance(target: pd.Series, current: pd.Series, band: float) -> pd.Series:
    """New weights: move a market to its target only when it is off by more than ``band``,
    or when the move opens or closes the position."""
    current = current.reindex(target.index).fillna(0.0)
    move = ((target - current).abs() > band) | (target == 0) | (current == 0)
    return current.where(~move, target)


@dataclass
class Simulation:
    returns: pd.Series  # net daily returns from ``start``
    weights: pd.DataFrame  # weights held after each close's rebalance
    turnover: pd.Series  # traded fraction of equity per day


def simulate(
    px: pd.DataFrame,
    targets: pd.DataFrame,
    costs: dict[str, float],
    band: float,
    start: str | pd.Timestamp,
) -> Simulation:
    """Trade ``targets`` from cash at ``start``, letting holdings drift with prices.

    At each close the drifted weights are compared with the target (step 4) and the
    difference is traded at that close, paying ``costs`` per side. The new weights earn the
    next day's return. This is the same loop the paper account runs once a day.
    """
    px = px[px.index >= pd.Timestamp(start)]
    rets = px.pct_change(fill_method=None).fillna(0.0).to_numpy()
    tgt = targets.reindex(px.index).fillna(0.0).to_numpy()
    per_side = np.array([costs.get(m, 0.0) for m in px.columns])
    n, k = tgt.shape
    held, net, traded = np.zeros((n, k)), np.zeros(n), np.zeros(n)
    w = np.zeros(k)
    for i in range(n):
        if i:
            growth = w * rets[i]
            net[i] = growth.sum()
            w = (w + growth) / (1 + net[i])
        move = (np.abs(tgt[i] - w) > band) | (tgt[i] == 0) | (w == 0)
        new = np.where(move, tgt[i], w)
        traded[i] = np.abs(new - w).sum()
        net[i] -= (np.abs(new - w) * per_side).sum() * (1 + net[i])
        w = new
        held[i] = w
    idx = px.index
    return Simulation(
        pd.Series(net, idx), pd.DataFrame(held, idx, px.columns), pd.Series(traded, idx)
    )
