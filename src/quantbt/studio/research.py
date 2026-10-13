"""One bounded research run from immutable bars to independent reviews and a proposal."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .. import __version__
from ..strategies import PositionStrategy, create_strategy
from .data import INTERVALS, Settings, load_bars
from .paper import replay, size_notional, statistics
from .review import ROLES, review
from .store import Store

CANDIDATES = [
    ("macd", {"fast": f, "slow": s}) for f, s in [(5, 20), (10, 21), (12, 26), (20, 50)]
] + [
    (sid, {})
    for sid in ["ema_macd", "awesome_oscillator", "parabolic_sar", "heikin_ashi", "bollinger_w"]
]

CODE_HASH = hashlib.sha256(
    b"".join(p.read_bytes() for p in sorted(Path(__file__).parents[1].rglob("*.py")))
).hexdigest()


def causal_signals(strategy: PositionStrategy, bars: pd.DataFrame) -> pd.Series:
    full = strategy.positions(bars)
    if (
        not full.index.equals(bars.index)
        or not np.isfinite(full.to_numpy()).all()
        or not full.between(-1, 1).all()
    ):
        raise ValueError("Strategy produced invalid exposures")
    for cut in [len(bars) // 2, len(bars) * 3 // 4]:
        part = strategy.positions(bars.iloc[:cut])
        pd.testing.assert_series_equal(part, full.iloc[:cut], check_names=False)
    shocked = bars.copy()
    cut = len(bars) // 2
    shocked.iloc[cut:, :4] *= 0.5
    pd.testing.assert_series_equal(
        strategy.positions(shocked).iloc[:cut], full.iloc[:cut], check_names=False
    )
    return full


def dated_news(root: Path, market: str, cutoff: pd.Timestamp) -> list[dict]:
    path = root / f"{market}_news.json"
    if not path.exists():
        return []
    if path.stat().st_size > 1_000_000:
        raise ValueError("News archive exceeds 1 MB")
    records = json.loads(path.read_text())
    if not isinstance(records, list):
        raise ValueError("News archive must be an array")
    valid = []
    for row in records:
        if not isinstance(row, dict) or any(
            not isinstance(row.get(k), str)
            for k in ("title", "source_url", "known_at", "published_at")
        ):
            raise ValueError("News records require title, source_url and timezone-aware timestamps")
        known, published = (pd.Timestamp(row[k]) for k in ("known_at", "published_at"))
        if known.tz is None or published.tz is None:
            raise ValueError("News timestamps require a timezone")
        if known <= cutoff and published <= cutoff and known >= cutoff - pd.Timedelta(days=30):
            valid.append(
                {k: row[k][:2000] for k in ("title", "source_url", "known_at", "published_at")}
            )
    return sorted(valid, key=lambda x: pd.Timestamp(x["known_at"]))[-20:]


def committee_gate(reviews: list[dict], checks: dict[str, bool]) -> bool:
    votes = {r["role"]: r["verdict"] for r in reviews}
    return (
        len(reviews) == 4
        and set(votes) == set(ROLES)
        and sum(v == "APPROVE" for v in votes.values()) >= 3
        and votes.get("quant") == "APPROVE"
        and votes.get("risk") == "APPROVE"
        and all(checks.values())
    )


def research(
    store: Store, run_id: str, settings: Settings, root: Path, reviewer: str = "rules"
) -> dict:
    started = time.perf_counter()

    def event(agent: str, phase: str, **detail: Any) -> None:
        store.event(run_id, agent, phase, detail)

    event("data", "RUNNING", message="Checking completed candles and source provenance")
    bars, manifest = load_bars(settings, root, pd.Timestamp.now(tz="UTC"))
    event("data", "COMPLETED", **manifest)
    n = len(bars)
    split = n * 4 // 5
    boundaries = np.linspace(n // 2, split, 4, dtype=int)
    periods = pd.Timedelta(days=365) / INTERVALS[settings.interval]
    event(
        "deviser",
        "RUNNING",
        message="Enumerating bounded registered templates",
        trials=len(CANDIDATES),
    )
    trials = []
    event(
        "validation",
        "RUNNING",
        message="Causality checks and three chronological validation windows",
    )
    for sid, params in CANDIDATES:
        strategy = create_strategy(sid, params)
        if not isinstance(strategy, PositionStrategy):
            raise TypeError("Studio requires a position strategy")
        identity = hashlib.sha256(json.dumps([sid, params], sort_keys=True).encode()).hexdigest()[
            :12
        ]
        signals = causal_signals(strategy, bars.iloc[:split])
        folds = []
        for lo, hi in pairwise(boundaries):
            sim = replay(bars.iloc[lo:hi], signals.iloc[lo:hi], settings)
            folds.append(statistics(sim, settings.capital, periods))
        score = float(
            np.mean([m["sharpe"] for m in folds]) + 2 * np.mean([m["drawdown"] for m in folds])
        )
        trial = {
            "id": identity,
            "strategy": sid,
            "params": params,
            "score": score,
            "folds": folds,
            "validation_trades": sum(m["trades"] for m in folds),
            "status": "VALIDATED",
            "selection_eligible": sum(m["trades"] for m in folds) >= settings.min_trades,
        }
        trials.append(trial)
        event("deviser", "PROGRESS", trial=trial)
    qualified = [t for t in trials if t["selection_eligible"]]
    selected = max(qualified or trials, key=lambda t: t["score"])
    event(
        "deviser",
        "COMPLETED",
        selected=selected,
        message="Selected by validation only; no test-window ranking",
    )
    strategy = create_strategy(selected["strategy"], selected["params"])
    assert isinstance(strategy, PositionStrategy)
    signal = causal_signals(strategy, bars)
    test_bars, test_signal = bars.iloc[split:], signal.iloc[split:]
    result = replay(test_bars, test_signal, settings)
    metrics = statistics(result, settings.capital, periods)
    stressed = statistics(
        replay(
            test_bars,
            test_signal,
            settings,
            cost_multiplier=2,
        ),
        settings.capital,
        periods,
    )
    baseline = statistics(
        replay(test_bars, pd.Series(1.0, index=test_bars.index), settings),
        settings.capital,
        periods,
    )
    experiment_id = hashlib.sha256(
        json.dumps(
            [manifest["sha256"], settings.to_dict(), selected["id"], CODE_HASH], sort_keys=True
        ).encode()
    ).hexdigest()[:16]
    evidence = {
        "engine_version": __version__,
        "code_sha256": CODE_HASH,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "id": experiment_id,
        "metrics": metrics,
        "cost_stress": stressed,
        "baseline": baseline,
        "baseline_label": "Same-risk long-and-stop baseline",
        "test_start": test_bars.index[0].isoformat(),
        "test_end": test_bars.index[-1].isoformat(),
        "test_bars": len(test_bars),
        "trials_attempted": len(trials),
        "selected": selected,
        "causal": True,
    }
    event("validation", "COMPLETED", **evidence)
    quant_pass = (
        selected["selection_eligible"]
        and metrics["trades"] >= settings.min_trades
        and metrics["return"] > 0
        and stressed["return"] > 0
        and metrics["return"] > baseline["return"]
        and sum(m["return"] > 0 for m in selected["folds"]) >= 2
    )
    risk_pass = abs(metrics["drawdown"]) <= settings.max_drawdown
    notional = size_notional(settings.capital, settings)
    last_price = float(bars.Close.iloc[-1])
    cutoff = (bars.index[-1] + INTERVALS[settings.interval]).tz_localize("UTC")
    packet = {
        "dataset_id": manifest["id"],
        "experiment_id": experiment_id,
        "market": settings.market,
        "synthetic": manifest["synthetic"],
        "quant_pass": quant_pass,
        "risk_pass": risk_pass,
        "metrics": metrics,
        "cost_stress": stressed,
        "baseline": baseline,
        "signal": float(signal.iloc[-1]),
        "volatility": float(bars.Close.pct_change().tail(30).std()),
        "notional": notional,
        "risk_budget": settings.capital * settings.risk_fraction,
        "news": dated_news(root, settings.market, cutoff),
    }
    packet["evidence_ids"] = [manifest["id"], experiment_id]
    if packet["news"]:
        news_id = hashlib.sha256(json.dumps(packet["news"], sort_keys=True).encode()).hexdigest()[
            :16
        ]
        packet["evidence_ids"].append(news_id)

    def independent(role: str) -> dict:
        event(role, "RUNNING", message="Independent review before seeing peer verdicts")
        try:
            verdict = review(role, packet, reviewer)
            event(role, "COMPLETED", **verdict)
            return verdict
        except Exception as exc:
            # Error types are useful; provider exception messages can contain secrets.
            verdict = {
                "role": role,
                "verdict": "ABSTAIN",
                "reason": f"Review failed: {type(exc).__name__}",
                "evidence": [],
                "provider": reviewer,
                "counterargument": "Missing review cannot support a trade",
            }
            event(role, "FAILED", **verdict)
            return verdict

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="review") as pool:
        reviews = list(pool.map(independent, ROLES))
    event(
        "portfolio",
        "RUNNING",
        message="Applying deterministic gates independently of reviewer votes",
    )
    checks = {
        "market_data": not manifest["synthetic"],
        "source_provenance": manifest["provenance_recorded"],
        "fresh": manifest["fresh"],
        "causal": True,
        "held_out_evidence": quant_pass,
        "drawdown": risk_pass,
        "active_signal": signal.iloc[-1] > 0,
        "minimum_notional": notional >= 10,
    }
    checks = {k: bool(v) for k, v in checks.items()}
    eligible = committee_gate(reviews, checks)
    reasons = [name for name, passed in checks.items() if not passed]
    if sum(r["verdict"] == "APPROVE" for r in reviews) < 3:
        reasons.append("fewer than three approvals")
    proposal = {
        "status": "ELIGIBLE" if eligible else "DEMO ONLY" if manifest["synthetic"] else "NO TRADE",
        "action": "CONDITIONAL LONG" if eligible else "WAIT",
        "checks": checks,
        "reasons": reasons,
        "market": settings.market + "/USDT spot",
        "quote_currency": "USDT",
        "entry_reference": last_price,
        "entry_rule": "Reprice at the next executable observation; never backfill an order",
        "stop_reference": last_price * (1 - settings.stop_fraction),
        "target_reference": last_price * (1 + 2 * settings.stop_fraction),
        "target_note": "Illustrative 2R level; replay exits by signal or stop, not this target",
        "notional": notional if eligible else 0,
        "quantity": notional / last_price if eligible else 0,
        "risk_budget": settings.capital * settings.risk_fraction,
        "expires_at": (cutoff + INTERVALS[settings.interval]).isoformat(),
        "evidence": [manifest["id"], experiment_id],
        "reviews": reviews,
    }
    event("portfolio", "COMPLETED", **proposal)
    event(
        "paper",
        "RUNNING",
        message="Publishing the reconciled historical replay; no exchange orders are sent",
    )
    points = result.equity.iloc[:: max(1, len(result.equity) // 350)]
    report: dict[str, Any] = {
        "manifest": manifest,
        "evidence": evidence,
        "trials": trials,
        "reviews": reviews,
        "proposal": proposal,
        "equity": [{"time": str(k), "value": float(v)} for k, v in points.items()],
        "trades": result.trades[-100:],
        "ledger": {
            "quote_currency": "USDT",
            "capital": settings.capital,
            "final_equity": metrics["final_equity"],
            "fees": result.fees,
            "quantity": result.quantity,
            "completed_trades": len(result.trades),
            "reconciled": True,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "reviewer_mode": reviewer,
        "review_packet": packet,
    }
    event("paper", "COMPLETED", **report["ledger"])
    store.finish(run_id, report)
    return report


def execute(
    store: Store, run_id: str, settings: Settings, root: Path, reviewer: str = "rules"
) -> None:
    try:
        research(store, run_id, settings, root, reviewer)
    except Exception as exc:
        message = (
            f"{type(exc).__name__}: {exc}"
            if reviewer == "rules"
            else f"{type(exc).__name__}: research failed"
        )
        try:
            store.event(run_id, "system", "FAILED", {"message": message})
        finally:
            store.finish(run_id, error=message)
