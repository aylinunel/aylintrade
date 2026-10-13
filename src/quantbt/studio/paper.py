"""Single-asset spot replay with next-open fills, fees, adverse slippage and stops."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Settings


def size_notional(equity: float, settings: Settings, cost_multiplier: float = 1.0) -> float:
    # Both sides' fees and adverse fills consume the planned stop risk budget.
    loss_fraction = settings.stop_fraction + 2 * cost_multiplier * (
        settings.fee + settings.slippage
    )
    return min(equity * settings.risk_fraction / loss_fraction, equity * settings.max_exposure)


@dataclass
class Replay:
    equity: pd.Series
    trades: list[dict]
    fees: float
    quantity: float


def replay(
    bars: pd.DataFrame, signals: pd.Series, settings: Settings, *, cost_multiplier: float = 1.0
) -> Replay:
    """A signal on close t can trade at open t+1. Short signals mean flat in spot mode."""
    if not np.isfinite(cost_multiplier) or not 0 < cost_multiplier <= 2:
        raise ValueError("Cost multiplier must be positive and at most two")
    fee_rate, slippage = settings.fee * cost_multiplier, settings.slippage * cost_multiplier
    signals = signals.reindex(bars.index)
    if signals.isna().any() or not np.isfinite(signals.to_numpy()).all():
        raise ValueError("Signals must be finite and cover every bar")
    cash, units, stop, fees = settings.capital, 0.0, 0.0, 0.0
    entry: dict = {}
    trades: list[dict] = []
    equity = []
    opens, highs, lows, closes = (bars[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    held = signals.shift(1, fill_value=0).to_numpy(float)
    for i, (o, _h, lo, c, want) in enumerate(zip(opens, highs, lows, closes, held, strict=True)):
        timestamp = bars.index[i].isoformat()
        reason, exit_price = "", 0.0
        if units and o <= stop:
            reason, exit_price = "gap stop", o
        elif units and want <= 0:
            reason, exit_price = "signal", o
        if reason:
            fill = exit_price * (1 - slippage)
            fee = units * fill * fee_rate
            cash += units * fill - fee
            fees += fee
            trades.append(
                {
                    **entry,
                    "exit_time": timestamp,
                    "exit": fill,
                    "pnl": units * fill - fee - entry["spent"],
                    "reason": reason,
                }
            )
            units = 0.0
        if not units and want > 0 and not reason:
            fill = o * (1 + slippage)
            notional = min(size_notional(cash, settings, cost_multiplier), cash / (1 + fee_rate))
            units = notional / fill
            fee = notional * fee_rate
            cash -= notional + fee
            fees += fee
            stop = o * (1 - settings.stop_fraction)
            entry = {
                "entry_time": timestamp,
                "entry": fill,
                "quantity": units,
                "spent": notional + fee,
                "stop": stop,
            }
        if units and lo <= stop:
            fill = min(o, stop) * (1 - slippage)
            fee = units * fill * fee_rate
            cash += units * fill - fee
            fees += fee
            trades.append(
                {
                    **entry,
                    "exit_time": timestamp,
                    "exit": fill,
                    "pnl": units * fill - fee - entry["spent"],
                    "reason": "stop",
                }
            )
            units = 0.0
        equity.append(cash + units * c)
        if cash < -1e-7 or not np.isfinite(equity[-1]):
            raise ValueError("Paper ledger failed its cash/equity invariant")
    # The evaluation ends flat; the closing fee belongs to its measured performance.
    if units:
        fill = closes[-1] * (1 - slippage)
        fee = units * fill * fee_rate
        cash += units * fill - fee
        fees += fee
        trades.append(
            {
                **entry,
                "exit_time": bars.index[-1].isoformat(),
                "exit": fill,
                "pnl": units * fill - fee - entry["spent"],
                "reason": "evaluation end",
            }
        )
        units, equity[-1] = 0.0, cash
    if abs(cash - settings.capital - sum(t["pnl"] for t in trades)) > 1e-6 * settings.capital:
        raise ValueError("Paper trade PnL does not reconcile with cash")
    return Replay(pd.Series(equity, index=bars.index), trades, fees, units)


def statistics(result: Replay, capital: float, periods: float) -> dict:
    equity = pd.concat(
        [pd.Series([capital]), result.equity.reset_index(drop=True)], ignore_index=True
    )
    returns = equity.pct_change().dropna()
    sd = float(returns.std())
    return {
        "return": float(equity.iloc[-1] / capital - 1),
        "sharpe": float(returns.mean() / sd * np.sqrt(periods)) if sd > 1e-12 else 0.0,
        "drawdown": float((equity / equity.cummax() - 1).min()),
        "trades": len(result.trades),
        "fees": result.fees,
        "win_rate": sum(t["pnl"] > 0 for t in result.trades) / len(result.trades)
        if result.trades
        else None,
        "final_equity": float(equity.iloc[-1]),
    }
