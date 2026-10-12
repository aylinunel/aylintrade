"""A committee of Claude agents that reviews the algorithm's positions once a day.

Roles, adapted from TauricResearch/TradingAgents:

* **Market analyst** reads the numbers: trend votes, volatility, drawdowns.
* **News analyst** searches the web for what moved each market and what is scheduled.
* **Bull and bear researchers** debate the positions, ``debate_rounds`` times.
* **Risk manager** looks for concentration, event risk and anything the data cannot see.
* **Portfolio manager** (the stronger model) gives each market a rating and a ``keep``
  fraction, and reads how its past calls turned out.

The guard rule comes from Superior-Trade's strategy pipeline: no model gets a vote on whether
its own output is safe. :func:`apply_review` is plain code. The committee can only *reduce* a
position, by at most ``max_cut``; it can never open, add or short. A missing or unreadable
decision keeps the algorithm's weight and is flagged ``review``, never silently read as Hold.

This layer is not in the backtest: a language model knows how history turned out, so a
backtest of it would be look-ahead. Its value is measured forward instead, in the paper
account (see :mod:`aylintrade.paper`).
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .algorithm import PERIODS_PER_YEAR, trend_score, volatility
from .config import AgentsConfig, AlgorithmConfig

log = logging.getLogger(__name__)

RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
REVIEW = "review"


# ------------------------------------------------------------------ facts
def market_facts(
    px: pd.DataFrame,
    p: AlgorithmConfig,
    labels: dict[str, str],
    targets: pd.Series,
    current: pd.Series,
) -> list[dict[str, Any]]:
    """What every agent sees about each market on the last day of ``px``."""
    last = px.iloc[-1]
    vol = volatility(px, p.vol_span).iloc[-1]
    score = trend_score(px, p.horizons).iloc[-1]
    high = px.rolling(PERIODS_PER_YEAR, min_periods=1).max().iloc[-1]
    out = []
    for m in px.columns:
        c = px[m].dropna()
        votes = {
            f"{h}d": {
                "above_average": bool(c.iloc[-1] > c.iloc[-h:].mean()),
                "return_positive": bool(len(c) > h and c.iloc[-1] > c.iloc[-h - 1]),
            }
            for h in p.horizons
        }
        out.append(
            {
                "market": m,
                "label": labels.get(m, m),
                "close": round(float(last[m]), 4),
                "returns": {
                    k: _ret(c, n) for k, n in (("1w", 5), ("1m", 21), ("3m", 63), ("12m", 252))
                },
                "trend_score": None if pd.isna(score[m]) else round(float(score[m]), 3),
                "trend_votes": votes,
                "volatility": None if pd.isna(vol[m]) else round(float(vol[m]), 3),
                "from_1y_high": round(float(last[m] / high[m] - 1), 4),
                "target_weight": round(float(targets.get(m, 0.0)), 4),
                "current_weight": round(float(current.get(m, 0.0)), 4),
            }
        )
    return out


def _ret(c: pd.Series, n: int) -> float | None:
    return round(float(c.iloc[-1] / c.iloc[-n - 1] - 1), 4) if len(c) > n else None


# ------------------------------------------------------------------ guard
def apply_review(
    targets: pd.Series, decisions: dict[str, dict[str, Any]], max_cut: float
) -> tuple[pd.Series, dict[str, str]]:
    """Final weights = target x keep, with keep clamped to [1 - max_cut, 1].

    Returns the weights and a status per market: ``ok``, ``clamped`` (the committee asked for
    more than it may) or ``review`` (no readable decision; the target is kept).
    """
    final, status = targets.copy(), {}
    for m, target in targets.items():
        d = decisions.get(str(m))
        keep = d.get("keep") if d else None
        if not isinstance(keep, (int, float)) or isinstance(keep, bool) or np.isnan(keep):
            status[str(m)] = REVIEW
            continue
        allowed = float(np.clip(keep, 1 - max_cut, 1.0))
        status[str(m)] = "ok" if allowed == keep else "clamped"
        final[m] = target * allowed
    return final, status


# ------------------------------------------------------------------ committee
@dataclass
class Review:
    status: str  # "ok", "skipped: ..." or "error: ..."
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    summary: str = ""
    reports: dict[str, str] = field(default_factory=dict)
    sources: list[dict[str, str]] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)


ANALYST_SYSTEM = (
    "You are part of a research committee reviewing a systematic, long-only, multi-market "
    "trend portfolio. The algorithm has already chosen the target weights; it is tested on "
    "20 years of data. Your job is to spot what the data cannot: events, regime breaks, "
    "concentrated risk. Be specific and brief. Never invent numbers or news; say when you "
    "do not know. Dates matter: today is {date}."
)

DECISION_TOOL = {
    "name": "submit_decisions",
    "description": "Record the committee's final decision for every market.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Three to five sentences for the dashboard.",
            },
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "market": {"type": "string"},
                        "rating": {"type": "string", "enum": list(RATINGS)},
                        "keep": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Share of the algorithm's weight to hold; 1 = agree.",
                        },
                        "reason": {"type": "string", "description": "One sentence."},
                    },
                    "required": ["market", "rating", "keep", "reason"],
                },
            },
        },
        "required": ["summary", "decisions"],
    },
}


class Committee:
    def __init__(self, cfg: AgentsConfig, client: Any = None) -> None:
        self.cfg = cfg
        if client is None:
            import anthropic  # optional dependency: pip install "aylintrade[agents]"

            client = anthropic.Anthropic()
        self.client = client
        self.sources: list[dict[str, str]] = []

    def ask(
        self,
        role: str,
        prompt: str,
        date: str,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1500,
    ) -> Any:
        """One agent turn. Returns the text, or the forced tool's input when one is given."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model or self.cfg.analyst_model,
            "max_tokens": max_tokens,
            "system": ANALYST_SYSTEM.format(date=date) + f"\nYour role: {role}.",
        }
        forced = tools and tools[0].get("name") == DECISION_TOOL["name"]
        if tools:
            kwargs["tools"] = tools
        if forced:
            kwargs["tool_choice"] = {"type": "tool", "name": DECISION_TOOL["name"]}
        for _ in range(4):  # a server-side search may pause the turn; resume it
            resp = self.client.messages.create(messages=messages, **kwargs)
            if resp.stop_reason != "pause_turn":
                break
            messages = [*messages, {"role": "assistant", "content": resp.content}]
        texts = []
        for block in resp.content:
            if block.type == "tool_use" and forced:
                return block.input
            if block.type == "text":
                texts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    self.sources.append({"title": c.title or c.url, "url": c.url})
        if forced:
            raise ValueError("the portfolio manager did not submit decisions")
        return "\n".join(texts).strip()

    def run(self, facts: list[dict[str, Any]], lessons: list[str], date: str) -> Review:
        cfg, table = self.cfg, json.dumps(facts, indent=1)
        held = [f["label"] for f in facts if f["target_weight"] > 0]
        jobs = {
            "market": lambda: self.ask(
                "market analyst",
                "Read these per-market facts (weights are fractions of the portfolio; "
                f"returns and volatility are fractions).\n{table}\n\nIn under 250 words: which "
                "trends are strong, which are fading or stretched, and which positions look "
                "most exposed.",
                date,
            ),
        }
        if cfg.news_search:
            search = {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": cfg.max_searches,
            }
            jobs["news"] = lambda: self.ask(
                "news analyst",
                f"The portfolio holds: {', '.join(held) or 'nothing'}. Search for the most "
                "important news of the past week for these markets and for scheduled events in "
                "the next five trading days (central banks, inflation data, earnings, crypto "
                "regulation). In under 250 words, list only what could move them, with dates.",
                date,
                tools=[search],
            )
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {k: pool.submit(f) for k, f in jobs.items()}
            reports = {k: f.result() for k, f in futures.items()}

        context = "\n\n".join(f"## {k.title()} report\n{v}" for k, v in reports.items())
        debate = ""
        for i in range(cfg.debate_rounds):
            for side, stance in (("bull", "for keeping"), ("bear", "against holding")):
                arg = self.ask(
                    f"{side} researcher",
                    f"{context}\n\nFacts:\n{table}\n\nDebate so far:\n{debate or '(none)'}\n\n"
                    f"Argue {stance} the current target positions, market by market where it "
                    "matters. Answer the other side's last points. Under 200 words.",
                    date,
                )
                debate += f"\n\n### {side.title()} (round {i + 1})\n{arg}"
        reports["debate"] = debate.strip()
        reports["risk"] = self.ask(
            "risk manager",
            f"{context}\n\nDebate:\n{debate}\n\nFacts:\n{table}\n\nAs risk manager, in under "
            "200 words: name concrete risks to the portfolio this week (concentration, "
            "correlated positions, event risk) and which positions you would trim.",
            date,
        )
        lesson_text = "\n".join(lessons) or "(no settled decisions yet)"
        decision = self.ask(
            "portfolio manager",
            f"{context}\n\n## Debate{debate}\n\n## Risk manager\n{reports['risk']}\n\n"
            f"## How your past calls turned out\n{lesson_text}\n\n## Facts\n{table}\n\n"
            "Decide, for every market with a target weight above zero, what fraction of the "
            f"algorithm's weight to hold. You may cut at most {cfg.max_cut:.0%}; you can never "
            "add or open a position. Cut only on specific evidence the algorithm cannot see: "
            "the algorithm is tested, your cuts are not. Agreeing (keep = 1) is the default.",
            date,
            model=cfg.manager_model,
            tools=[DECISION_TOOL],
            max_tokens=2500,
        )
        decisions = {
            str(d.get("market")): d for d in decision.get("decisions", []) if isinstance(d, dict)
        }
        return Review(
            status="ok",
            decisions=decisions,
            summary=str(decision.get("summary", "")),
            reports=reports,
            sources=_unique(self.sources),
            models={"analysts": cfg.analyst_model, "manager": cfg.manager_model},
        )


def _unique(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    seen, out = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
    return out


def review(
    facts: list[dict[str, Any]],
    lessons: list[str],
    date: str,
    cfg: AgentsConfig,
    client: Any = None,
) -> Review:
    """Run the committee, or explain why it did not run. Never raises: the algorithm trades
    on its own weights when the committee is off or fails."""
    if not cfg.enabled:
        return Review(status="skipped: agents are disabled in the config")
    if client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        return Review(status="skipped: ANTHROPIC_API_KEY is not set")
    try:
        return Committee(cfg, client).run(facts, lessons, date)
    except Exception as e:  # any API or parsing failure falls back to the algorithm
        log.error("agent committee failed: %s", e)
        return Review(status=f"error: {type(e).__name__}: {e}"[:300])
