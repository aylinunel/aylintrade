"""Run every configured strategy on every configured market and collect the results.

Work is split by market, so markets run in parallel processes with ``jobs > 1``.
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import Config, MarketConfig
from .data import DataStore, MissingDataError
from .engine import BacktestResult, ProportionalCost, compute_metrics, run
from .strategies import create_strategy
from .strategies.base import IntradayStrategy, PairStrategy, Strategy

log = logging.getLogger(__name__)


@dataclass
class MarketData:
    daily: pd.DataFrame
    hourly: pd.DataFrame | None = None
    partner: pd.DataFrame | None = None
    partner_id: str | None = None


def load_market_data(store: DataStore, market: MarketConfig) -> MarketData:
    hourly = store.load(market.id, "1h") if market.has_interval("1h") else None
    partner = store.load(market.pair_with, "1d") if market.pair_with else None
    return MarketData(store.load(market.id, "1d"), hourly, partner, market.pair_with)


def skip_reason(strategy: Strategy, market: MarketConfig, data: MarketData) -> str | None:
    """Why ``strategy`` cannot run on ``market``, or ``None`` if it can."""
    if isinstance(strategy, IntradayStrategy) and strategy.interval == "1h" and data.hourly is None:
        return "Needs hourly data, which is not configured for this market"
    if isinstance(strategy, PairStrategy):
        if data.partner is None:
            return "No pair partner configured for this market"
        common = data.daily.index.intersection(data.partner.index)
        if len(common) < strategy.warmup() + 120:
            return (
                f"Only {len(common)} overlapping days; needs {strategy.warmup()} to fit "
                "the model plus a test period"
            )
    return None


def benchmark(
    daily: pd.DataFrame, result: BacktestResult, cost: ProportionalCost
) -> BacktestResult:
    """Buy & hold over exactly the strategy's evaluation window."""
    bh = create_strategy("buy_and_hold")
    window = daily.loc[result.start : result.end]
    return run(bh, window, cost)


def weekly_equity(result: BacktestResult) -> pd.Series:
    return result.equity().resample("W").last().dropna()


def evaluate(
    strategy: Strategy, market: MarketConfig, data: MarketData
) -> tuple[dict[str, Any], pd.Series | None]:
    """One results row (and weekly equity curve) for one strategy on one market."""
    row: dict[str, Any] = {
        "market": market.id,
        "market_label": market.label,
        "group": market.group,
        "strategy": strategy.id,
        "strategy_label": strategy.label,
        "description": strategy.description,
        "params": json.dumps(strategy.params()),
    }
    if isinstance(strategy, PairStrategy) and data.partner_id:
        row["description"] = f"{strategy.description} ({market.id} vs {data.partner_id})"
    reason = skip_reason(strategy, market, data)
    if reason:
        return {**row, "status": "skipped", "reason": reason}, None

    cost = ProportionalCost(market.cost_per_side)
    result = run(strategy, data.daily, cost, data.hourly, data.partner)
    m = compute_metrics(result.returns, market.periods_per_year)
    b = compute_metrics(benchmark(data.daily, result, cost).returns, market.periods_per_year)
    row.update(
        status="ok",
        reason="",
        start=result.start.date().isoformat(),
        end=result.end.date().isoformat(),
        trades=result.n_trades,
        time_in_market=result.exposure,
        **m.as_dict(),
        **{k: v for k, v in b.as_dict("bh_").items() if k not in ("bh_periods", "bh_years")},
        sharpe_vs_bh=m.sharpe - b.sharpe,
    )
    return row, weekly_equity(result)


def run_market(config: Config, market_id: str) -> tuple[list[dict[str, Any]], dict[str, pd.Series]]:
    market = config.markets[market_id]
    data = load_market_data(DataStore(config.data_dir), market)
    rows, curves = [], {}
    for sid, params in config.strategies.items():
        strategy = create_strategy(sid, params)
        log.info("%s: %s", market_id, strategy.label)
        row, curve = evaluate(strategy, market, data)
        rows.append(row)
        if curve is not None:
            curves[sid] = curve
    return rows, curves


@dataclass
class RunOutput:
    results: pd.DataFrame
    curves: pd.DataFrame


def run_all(config: Config, jobs: int = 1) -> RunOutput:
    """Backtest all traded markets; ``jobs`` > 1 runs markets in parallel processes."""
    store = DataStore(config.data_dir)
    needed = {m.id for m in config.traded_markets} | {
        m.pair_with for m in config.traded_markets if m.pair_with
    }
    missing = [
        f"{m}_{i}" for m in sorted(needed) for i in config.markets[m].data if not store.exists(m, i)
    ]
    if missing:
        raise MissingDataError(f"missing data for {', '.join(missing)}. Run `quantbt fetch` first.")

    ids = [m.id for m in config.traded_markets]
    if jobs > 1 and len(ids) > 1:
        with ProcessPoolExecutor(
            max_workers=min(jobs, len(ids)), mp_context=mp.get_context("spawn")
        ) as pool:
            outputs = list(pool.map(run_market, [config] * len(ids), ids))
    else:
        outputs = [run_market(config, m) for m in ids]
    return RunOutput(
        _results_frame(r for r, _ in outputs),
        _curves_frame(zip(ids, (c for _, c in outputs), strict=True)),
    )


def _results_frame(chunks: Iterable[list[dict[str, Any]]]) -> pd.DataFrame:
    return pd.DataFrame([row for chunk in chunks for row in chunk])


def _curves_frame(items: Iterable[tuple[str, dict[str, pd.Series]]]) -> pd.DataFrame:
    frames = [
        pd.DataFrame(
            {
                "market": mid,
                "strategy": sid,
                "week": pd.DatetimeIndex(s.index).date,
                "equity": s.to_numpy(),
            }
        )
        for mid, curves in items
        for sid, s in curves.items()
    ]
    return (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["market", "strategy", "week", "equity"])
    )
