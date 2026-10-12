"""The backtest study: the algorithm against buy & hold, market by market, and stress tests.

Everything the dashboard shows about history comes from :func:`run_study`, written to
``results/latest/study.json`` (plus a Markdown summary for GitHub).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .algorithm import PERIODS_PER_YEAR, Simulation, close_prices, raw_weights, simulate
from .config import AlgorithmConfig, Config
from .data import DataStore
from .metrics import compute_metrics

log = logging.getLogger(__name__)

ALGO = "Aylin trend portfolio"
SPY_HOLD = "S&P 500 (SPY) buy & hold"
EQUAL_HOLD = "Equal-weight buy & hold"
RP_HOLD = "Risk parity, always invested"


def load_daily(cfg: Config, ids: list[str]) -> dict[str, pd.DataFrame]:
    store = DataStore(cfg.data_dir)
    return {m: store.load(m, "1d") for m in ids}


def run_algorithm(
    px: pd.DataFrame, p: AlgorithmConfig, costs: dict[str, float], start: str | pd.Timestamp
) -> Simulation:
    return simulate(px, raw_weights(px, p), costs, p.rebalance_band, start)


def benchmarks(
    px: pd.DataFrame, p: AlgorithmConfig, costs: dict[str, float], start: pd.Timestamp
) -> dict[str, Simulation]:
    available = px.notna() & px.rolling(p.warmup).count().ge(p.warmup)
    equal = available.div(available.sum(axis=1), axis=0).fillna(0.0)
    out = {
        EQUAL_HOLD: simulate(px, equal, costs, p.rebalance_band, start),
        RP_HOLD: run_algorithm(px, replace(p, trend_floor=1.0), costs, start),
    }
    if "SPY" in px:
        spy = pd.DataFrame(0.0, index=px.index, columns=px.columns).assign(SPY=1.0)
        out = {SPY_HOLD: simulate(px, spy, costs, 0.0, start), **out}
    return out


def stats(sim: Simulation) -> dict[str, float]:
    m = compute_metrics(sim.returns, PERIODS_PER_YEAR)
    return {
        "cagr": m.cagr,
        "volatility": m.volatility,
        "sharpe": m.sharpe,
        "sortino": m.sortino,
        "max_drawdown": m.max_drawdown,
        "calmar": m.calmar,
        "total_return": m.total_return,
        "years": m.years,
        "turnover": float(sim.turnover.sum() / m.years),
        "exposure": float(sim.weights.abs().sum(axis=1).mean()),
    }


def _weekly(r: pd.Series) -> pd.Series:
    return (1 + r).cumprod().resample("W-FRI").last().dropna()


def _start(px: pd.DataFrame, p: AlgorithmConfig) -> pd.Timestamp:
    """The configured start, or later if the first market lacks a warm-up year before it."""
    first = int(np.argmax(px.notna().any(axis=1).to_numpy()))
    earliest = px.index[min(first + p.warmup, len(px) - 1)]
    return max(pd.Timestamp(p.start), earliest)


def per_market(cfg: Config) -> list[dict[str, Any]]:
    """The algorithm on each market alone versus holding that market."""
    p, rows = cfg.algorithm, []
    for m in cfg.markets.values():
        row: dict[str, Any] = {"market": m.id, "label": m.label, "group": m.group}
        px = close_prices(load_daily(cfg, [m.id]))
        need = p.warmup + PERIODS_PER_YEAR
        if len(px) < need:
            rows.append(
                {**row, "status": "skipped", "reason": f"{len(px)} days of data; needs {need}"}
            )
            continue
        start = _start(px, p)
        algo = run_algorithm(px, p, cfg.costs(), start)
        hold = simulate(px, pd.DataFrame(1.0, px.index, px.columns), cfg.costs(), 0.0, start)
        a, h = stats(algo), stats(hold)
        rows.append(
            {
                **row,
                "status": "ok",
                "start": str(start.date()),
                "end": str(px.index[-1].date()),
                **a,
                **{f"hold_{k}": v for k, v in h.items()},
            }
        )
    return rows


def robustness(cfg: Config, px: pd.DataFrame, start: pd.Timestamp) -> list[dict[str, Any]]:
    """Does the result survive other settings, higher costs, fewer markets, other periods?"""
    p, costs = cfg.algorithm, cfg.costs()
    crypto = [m.id for m in cfg.markets.values() if m.group == "Crypto" and m.id in px]

    def row(test: str, setting: str, sim: Simulation, spy: Simulation | None) -> dict[str, Any]:
        s = stats(sim)
        out = {"test": test, "setting": setting, **{k: s[k] for k in ("sharpe", "cagr")}}
        out["max_drawdown"] = s["max_drawdown"]
        out["spy_sharpe"] = stats(spy)["sharpe"] if spy is not None else None
        return out

    def run(
        q: AlgorithmConfig = p, c: dict[str, float] = costs, x: pd.DataFrame = px
    ) -> Simulation:
        return run_algorithm(x, q, c, start)

    bench = benchmarks(px, p, costs, start)
    spy = bench.get(SPY_HOLD)
    rows = [row("As configured", _describe(p), run(), spy)]
    for mult in (2, 3):
        rows.append(
            row("Trading costs", f"{mult}x", run(c={k: v * mult for k, v in costs.items()}), spy)
        )
    for floor in (0.0, 0.5, 1.0):
        rows.append(row("Core holding", f"{floor:.0%}", run(replace(p, trend_floor=floor)), spy))
    for tv in (0.08, 0.12, 0.15):
        rows.append(row("Volatility target", f"{tv:.0%}", run(replace(p, target_vol=tv)), spy))
    for band in (0.0, 0.05):
        rows.append(row("Rebalance band", f"{band:.0%}", run(replace(p, rebalance_band=band)), spy))
    for hz in (p.horizons[1:], (max(p.horizons),)):
        label = ", ".join(f"{h}d" for h in hz)
        rows.append(row("Trend horizons", label, run(replace(p, horizons=hz)), spy))
    if crypto:
        rows.append(row("Markets", "without crypto", run(x=px.drop(columns=crypto)), spy))

    full = run()
    for chunk in np.array_split(np.arange(len(full.returns)), 3):
        idx = pd.DatetimeIndex(full.returns.index[chunk])
        period = f"{idx[0].year}-{idx[-1].year}"

        def cut(s: Simulation, idx: pd.Index = idx) -> Simulation:
            return Simulation(s.returns[idx], s.weights.loc[idx], s.turnover[idx])

        rows.append(row("Sub-period", period, cut(full), cut(spy) if spy else None))
    return rows


def _describe(p: AlgorithmConfig) -> str:
    return (
        f"{p.target_vol:.0%} vol target, {p.trend_floor:.0%} core holding, "
        f"{p.rebalance_band:.0%} band, "
        f"horizons {', '.join(str(h) for h in p.horizons)}d"
    )


def run_study(cfg: Config) -> dict[str, Any]:
    """Backtest the portfolio and its benchmarks; return everything as plain JSON data."""
    p, costs = cfg.algorithm, cfg.costs()
    px = close_prices(load_daily(cfg, cfg.portfolio_markets))
    start = _start(px, p)
    algo = run_algorithm(px, p, costs, start)
    sims = {ALGO: algo, **benchmarks(px, p, costs, start)}
    log.info("portfolio %s to %s, %d markets", start.date(), px.index[-1].date(), px.shape[1])

    yearly = pd.DataFrame(
        {
            k: (1 + s.returns).groupby(pd.DatetimeIndex(s.returns.index).year).prod() - 1
            for k, s in sims.items()
        }
    )
    curves = pd.DataFrame({k: _weekly(s.returns) for k, s in sims.items()})
    drawdown = curves / curves.cummax() - 1
    weights = algo.weights.resample("W-FRI").last()
    return {
        "version": __version__,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "as_of": str(px.index[-1].date()),
        "start": str(start.date()),
        "settings": _describe(p),
        "markets": {m: cfg.markets[m].label for m in px.columns},
        "costs": costs,
        "stats": {k: stats(s) for k, s in sims.items()},
        "curves": {"dates": [str(d.date()) for d in curves.index], **_cols(curves)},
        "drawdown": _cols(drawdown),
        "weights": {"dates": [str(d.date()) for d in weights.index], **_cols(weights)},
        "yearly": {"years": [int(y) for y in yearly.index], **_cols(yearly)},
        "per_market": per_market(cfg),
        "robustness": robustness(cfg, px, start),
    }


def _cols(df: pd.DataFrame) -> dict[str, list[float | None]]:
    return {str(c): [None if pd.isna(v) else round(float(v), 5) for v in df[c]] for c in df.columns}


def write_study(study: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "study.json").write_text(json.dumps(study, separators=(",", ":")))
    (out_dir / "summary.md").write_text(summary_markdown(study))


def _pct(x: float | None, sign: bool = False) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{x:+.1%}" if sign else f"{x:.1%}"


def summary_markdown(study: dict[str, Any]) -> str:
    lines = [
        "# Backtest summary",
        "",
        f"{study['start']} to {study['as_of']}, after trading costs. "
        f"Settings: {study['settings']}.",
        "",
        "| Portfolio | Per year | Volatility | Sharpe | Worst drop | Turnover / yr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, s in study["stats"].items():
        lines.append(
            f"| {name} | {_pct(s['cagr'])} | {_pct(s['volatility'])} | {s['sharpe']:.2f} | "
            f"{s['max_drawdown']:.0%} | {s['turnover']:.1f}x |"
        )
    lines += [
        "",
        "## Each market on its own",
        "",
        "| Market | Sharpe | Hold Sharpe | Per year | Hold per year | Worst drop | Hold worst |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    skipped = []
    for r in study["per_market"]:
        if r["status"] != "ok":
            skipped.append(f"{r['label']} ({r['reason']})")
            continue
        lines.append(
            f"| {r['label']} | {r['sharpe']:.2f} | {r['hold_sharpe']:.2f} | {_pct(r['cagr'])} | "
            f"{_pct(r['hold_cagr'])} | {r['max_drawdown']:.0%} | {r['hold_max_drawdown']:.0%} |"
        )
    if skipped:
        lines += ["", "Not tested: " + "; ".join(skipped)]
    lines += [
        "",
        "## Stress tests",
        "",
        "| Test | Setting | Sharpe | Per year | Worst drop | SPY Sharpe |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in study["robustness"]:
        spy = "" if r["spy_sharpe"] is None else f"{r['spy_sharpe']:.2f}"
        lines.append(
            f"| {r['test']} | {r['setting']} | {r['sharpe']:.2f} | {_pct(r['cagr'])} | "
            f"{r['max_drawdown']:.0%} | {spy} |"
        )
    lines += ["", "_Past performance does not predict future results. Not financial advice._", ""]
    return "\n".join(lines)
