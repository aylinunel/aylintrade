"""Collect the backtest study and the paper account into ``site/data.json`` for the dashboard."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Config
from .data.provenance import build_provenance
from .intraday import build_intraday_context
from .macro import load_current_context
from .validation import validation_summary


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()


def paper_data(paper_dir: Path, capital: float) -> dict[str, Any] | None:
    ledger = _csv(paper_dir / "ledger.csv")
    if ledger.empty:
        return None
    spy = ledger["spy_close"] / ledger["spy_close"].iloc[0] * capital
    decisions = _csv(paper_dir / "decisions.csv")
    if len(decisions) and "shadow_final" not in decisions:
        decisions["shadow_final"] = decisions["final"]
    if len(decisions) and "shadow_effect" not in decisions:
        decisions["shadow_effect"] = decisions["effect"]
    settled = decisions[decisions["return_5d"].notna()] if len(decisions) else decisions
    by_day = (
        settled.groupby("date")["shadow_effect"].sum().cumsum() if len(settled) else pd.Series()
    )
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
            "shadow_cuts": int((settled["shadow_final"] < settled["target"]).sum())
            if len(settled)
            else 0,
            "shadow_effect_dates": [str(d) for d in by_day.index],
            "shadow_effect": [round(float(v), 6) for v in by_day],
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
    study = json.loads(study_path.read_text()) if study_path.exists() else None
    data = {
        "meta": {
            "schema_version": "1.1",
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "as_of": study.get("as_of") if study else None,
            "data_vintage": "author_reported_unverified",
            "coverage_status": "derived dashboard data; source eligibility is shown per record",
        },
        "study": study,
        "paper": paper_data(cfg.paper_dir, cfg.paper_capital),
        "macro": load_current_context(cfg.data_dir, cfg.macro),
        "intraday": build_intraday_context(cfg.intraday),
        "validation": validation_summary(cfg),
        "provenance": build_provenance(cfg),
        "settings": {
            "max_cut": cfg.agents.max_cut,
            "target_vol": cfg.algorithm.target_vol,
            "trend_floor": cfg.algorithm.trend_floor,
            "agent_mode": cfg.agents.mode,
        },
    }
    out = cfg.site_dir / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_clean(data), separators=(",", ":"), default=str, allow_nan=False)
    out.write_text(payload)
    evidence_out = cfg.site_dir / "evidence.json"
    evidence_source = cfg.results_dir / "evidence.json"
    if evidence_source.exists():
        evidence_out.write_text(evidence_source.read_text())
    else:
        evidence_out.write_text(json.dumps(_clean(study.get("evidence", {}) if study else {})))
    preview_out = Path(__file__).resolve().parents[2] / "web" / "public" / "data.json"
    if preview_out.parent.exists():
        preview_out.write_text(payload)
    return out
