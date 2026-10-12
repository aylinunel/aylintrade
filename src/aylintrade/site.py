"""Collect the backtest study and the paper account into ``site/data.json`` for the dashboard."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Config


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()


def paper_data(paper_dir: Path, capital: float) -> dict[str, Any] | None:
    ledger = _csv(paper_dir / "ledger.csv")
    if ledger.empty:
        return None
    spy = ledger["spy_close"] / ledger["spy_close"].iloc[0] * capital
    decisions = _csv(paper_dir / "decisions.csv")
    settled = decisions[decisions["return_5d"].notna()] if len(decisions) else decisions
    by_day = settled.groupby("date")["effect"].sum().cumsum() if len(settled) else pd.Series()
    trades = _csv(paper_dir / "trades.csv")
    latest = paper_dir / "latest.json"
    return {
        "start": str(ledger["date"].iloc[0]),
        "capital": capital,
        "dates": ledger["date"].astype(str).tolist(),
        "equity": ledger["equity"].round(2).tolist(),
        "spy": spy.round(2).tolist(),
        "agents": {
            "decisions": len(decisions),
            "settled": len(settled),
            "cuts": int((settled["final"] < settled["target"]).sum()) if len(settled) else 0,
            "effect_dates": [str(d) for d in by_day.index],
            "effect": [round(float(v), 6) for v in by_day],
        },
        "trades": trades.tail(30).iloc[::-1].to_dict("records") if len(trades) else [],
        "latest": json.loads(latest.read_text()) if latest.exists() else None,
    }


def _clean(x: Any) -> Any:
    """JSON for browsers: NaN and infinity become null."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def build_site_data(cfg: Config) -> Path:
    study_path = cfg.results_dir / "study.json"
    data = {
        "study": json.loads(study_path.read_text()) if study_path.exists() else None,
        "paper": paper_data(cfg.paper_dir, cfg.paper_capital),
        "settings": {
            "max_cut": cfg.agents.max_cut,
            "target_vol": cfg.algorithm.target_vol,
            "trend_floor": cfg.algorithm.trend_floor,
        },
    }
    out = cfg.site_dir / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_clean(data), separators=(",", ":"), default=str, allow_nan=False))
    return out
