"""The paper account: trades the algorithm (plus the agents' cuts) once a day, with fake money.

Files in ``paper_dir`` (committed by the daily GitHub Action, so the history is public):

* ``state.json`` - cash, units held and the last day traded
* ``ledger.csv`` - equity, cash and weights after each day's trades, plus SPY's close
* ``trades.csv`` - every trade with its cost
* ``decisions.csv`` - every committee decision, settled five trading days later
* ``latest.json`` - today's facts, targets, decisions and reports, for the dashboard

Fills happen at the day's close, as in the backtest. Running twice on the same data is a
no-op, so the schedule can safely fire more than once a day.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from .agents import apply_review, market_facts, review
from .algorithm import raw_weights, rebalance
from .config import Config

log = logging.getLogger(__name__)
SETTLE_DAYS = 5
DECISION_COLUMNS = [
    "date",
    "market",
    "rating",
    "keep",
    "status",
    "target",
    "final",
    "close",
    "reason",
    "return_5d",
    "effect",
]


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists() and path.stat().st_size:
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])


def settle(decisions: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """Fill ``return_5d`` and ``effect`` for decisions whose five trading days have passed.

    ``effect`` is what the committee's change did to the portfolio, as a fraction of equity:
    (final - target) x the market's return. Positive means the cut helped.
    """
    d = decisions.copy()
    for i, row in d[d["return_5d"].isna()].iterrows():
        series = px[row["market"]].dropna() if row["market"] in px else pd.Series(dtype=float)
        after = series[series.index > pd.Timestamp(row["date"])]
        if len(after) >= SETTLE_DAYS:
            ret = after.iloc[SETTLE_DAYS - 1] / row["close"] - 1
            d.loc[i, "return_5d"] = round(float(ret), 5)
            d.loc[i, "effect"] = round(float((row["final"] - row["target"]) * ret), 6)
    return d


def lessons(decisions: pd.DataFrame, n: int = 10) -> list[str]:
    """Plain-language outcomes of the committee's recent settled cuts, for its next meeting."""
    done = decisions[decisions["return_5d"].notna()]
    if done.empty:
        return []
    cuts = done[done["final"] < done["target"]].tail(n)
    out = [
        f"{r.date} {r.market}: held {r.keep:.0%} of target ({r.rating}: {r.reason}). "
        f"Next {SETTLE_DAYS} days {r.return_5d:+.1%}; the cut "
        f"{'helped' if r.effect > 0 else 'cost'} {abs(r.effect):.2%} of the portfolio."
        for r in cuts.itertuples()
    ]
    total = done["effect"].sum()
    out.append(
        f"Overall: {len(done)} settled decisions, {len(done[done['final'] < done['target']])} "
        f"cuts, net effect of all cuts {total:+.2%} of the portfolio."
    )
    return out


def run_day(cfg: Config, px: pd.DataFrame, use_agents: bool = True, client: Any = None) -> bool:
    """Trade one day. Returns False when ``px`` holds no new day since the last run."""
    root = cfg.paper_dir
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    as_of = px.index[-1]
    date = str(as_of.date())
    if state and pd.Timestamp(state["date"]) >= as_of:
        log.info("paper account already traded %s; nothing new", state["date"])
        return False
    state = state or {"start": date, "cash": cfg.paper_capital, "units": {}}

    close = px.iloc[-1]
    units = pd.Series(state["units"], dtype=float).reindex(px.columns).fillna(0.0)
    equity = state["cash"] + float((units * close).sum())
    current = units * close / equity
    target = raw_weights(px, cfg.algorithm).iloc[-1]

    decisions = settle(_read_csv(root / "decisions.csv", DECISION_COLUMNS), px)
    labels = {m: cfg.markets[m].label for m in px.columns}
    facts = market_facts(px, cfg.algorithm, labels, target, current)
    agents_cfg = cfg.agents if use_agents else type(cfg.agents)(enabled=False)
    rev = review(facts, lessons(decisions), date, agents_cfg, client)
    final, status = (
        apply_review(target, rev.decisions, cfg.agents.max_cut)
        if rev.status == "ok"
        else (target, {})
    )
    new = rebalance(final, current, cfg.algorithm.rebalance_band)

    trades, cash = [], state["cash"]
    for m in px.columns:
        value = (new[m] - current[m]) * equity
        if abs(value) < 1e-9:
            continue
        cost = abs(value) * cfg.markets[m].cost_per_side
        cash -= value + cost
        units[m] += value / close[m]
        trades.append(
            {
                "date": date,
                "market": m,
                "side": "buy" if value > 0 else "sell",
                "units": round(value / close[m], 8),
                "price": float(close[m]),
                "value": round(value, 2),
                "cost": round(cost, 2),
            }
        )
    equity_after = cash + float((units * close).sum())

    if rev.status == "ok":
        rows = [
            {
                "date": date,
                "market": m,
                "rating": rev.decisions.get(m, {}).get("rating", ""),
                "keep": float(final[m] / target[m]),
                "status": status.get(m, ""),
                "target": round(float(target[m]), 5),
                "final": round(float(final[m]), 5),
                "close": float(close[m]),
                "reason": rev.decisions.get(m, {}).get("reason", ""),
                "return_5d": None,
                "effect": None,
            }
            for m in px.columns
            if target[m] > 0
        ]
        decisions = pd.concat([decisions, pd.DataFrame(rows)], ignore_index=True)
    decisions.to_csv(root / "decisions.csv", index=False)

    ledger = _read_csv(root / "ledger.csv")
    row = {
        "date": date,
        "equity": round(equity_after, 2),
        "cash": round(cash, 2),
        "spy_close": float(close["SPY"]) if "SPY" in close else None,
        **{f"w_{m}": round(float(new[m]), 5) for m in px.columns},
    }
    pd.concat([ledger, pd.DataFrame([row])], ignore_index=True).to_csv(
        root / "ledger.csv", index=False
    )
    if trades:
        old = _read_csv(root / "trades.csv")
        pd.concat([old, pd.DataFrame(trades)], ignore_index=True).to_csv(
            root / "trades.csv", index=False
        )

    latest = {
        "date": date,
        "equity": equity_after,
        "facts": facts,
        "target": target.round(5).to_dict(),
        "final": final.round(5).to_dict(),
        "held": new.round(5).to_dict(),
        "trades": trades,
        "review": {**asdict(rev), "guard": status},
    }
    (root / "latest.json").write_text(json.dumps(latest, indent=1, default=str))
    state.update(date=date, cash=cash, units={m: float(u) for m, u in units.items() if u})
    state_path.write_text(json.dumps(state, indent=1))
    log.info(
        "paper %s: equity %.2f, %d trades, agents %s", date, equity_after, len(trades), rev.status
    )
    return True
