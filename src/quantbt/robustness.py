"""Robustness checks: does a result survive other parameters, higher costs and other periods?"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from .config import Config, RobustnessConfig
from .data import DataStore
from .engine import ProportionalCost, compute_metrics, run
from .pipeline import MarketData, load_market_data
from .strategies import create_strategy


def _row(
    market: str, strategy: str, test: str, setting: str, r: pd.Series, ppy: int
) -> dict[str, Any]:
    m = compute_metrics(r, ppy)
    return {
        "market": market,
        "strategy": strategy,
        "test": test,
        "setting": setting,
        "cagr": m.cagr,
        "sharpe": m.sharpe,
        "max_drawdown": m.max_drawdown,
        "total_return": m.total_return,
    }


def _returns(
    sid: str, params: dict[str, Any], data: MarketData, cost: ProportionalCost
) -> pd.Series:
    strategy = create_strategy(sid, params)
    return run(strategy, data.daily, cost, data.hourly, data.partner).returns


def check(config: Config, spec: RobustnessConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (robustness rows, calendar-year returns) for one strategy across its markets."""
    store = DataStore(config.data_dir)
    base_params = config.strategies.get(spec.strategy, {})
    rows: list[dict[str, Any]] = []
    years: list[pd.DataFrame] = []
    for mid in spec.markets:
        market = config.markets[mid]
        data = load_market_data(store, market)
        ppy, sid = market.periods_per_year, spec.strategy
        cost = ProportionalCost(market.cost_per_side)

        for params in spec.param_sets:
            label = json.dumps(params) + (" (default)" if params == base_params else "")
            rows.append(_row(mid, sid, "parameters", label, _returns(sid, params, data, cost), ppy))
        for mult in spec.cost_multipliers:
            c = ProportionalCost(market.cost_per_side * mult)
            rows.append(
                _row(
                    mid,
                    sid,
                    "cost per side",
                    f"{c.per_side:.2%}",
                    _returns(sid, base_params, data, c),
                    ppy,
                )
            )

        base = _returns(sid, base_params, data, cost)
        bh = run(create_strategy("buy_and_hold"), data.daily.loc[base.index[0] :], cost).returns
        for chunk in np.array_split(np.arange(len(base)), spec.subperiods):
            r, b = base.iloc[chunk], bh.iloc[chunk]
            period = f"{r.index[0].year}-{r.index[-1].year}"
            rows.append(_row(mid, sid, "subperiod", period, r, ppy))
            rows.append(_row(mid, "buy_and_hold", "subperiod", period, b, ppy))

        yearly = pd.DataFrame(
            {
                "strategy_return": (1 + base).groupby(base.index.year).prod() - 1,
                "bh_return": (1 + bh).groupby(bh.index.year).prod() - 1,
            }
        )
        years.append(yearly.rename_axis("year").reset_index().assign(market=mid, strategy=sid))
    cols = ["market", "strategy", "year", "strategy_return", "bh_return"]
    return pd.DataFrame(rows), pd.concat(years, ignore_index=True)[cols]


def run_robustness(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts = [check(config, spec) for spec in config.robustness]
    if not parts:
        raise ValueError("no `robustness` section in the config")
    return (
        pd.concat([p[0] for p in parts], ignore_index=True),
        pd.concat([p[1] for p in parts], ignore_index=True),
    )
