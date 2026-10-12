"""The agent committee, run offline against a fake Claude client."""

from __future__ import annotations

from types import SimpleNamespace as NS
from typing import Any

import pandas as pd
import pytest

from aylintrade.agents import REVIEW, _unique, apply_review, market_facts, review
from aylintrade.config import AgentsConfig, AlgorithmConfig


class FakeClient:
    """Answers like the Messages API: text for analysts, a forced tool call for the manager."""

    def __init__(self, decisions: list[dict[str, Any]] | None = None, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.decisions = decisions or []
        self.fail = fail
        self.messages = self

    def create(self, **kw: Any) -> Any:
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("API down")
        if kw.get("tool_choice"):
            block = NS(type="tool_use", input={"summary": "All good.", "decisions": self.decisions})
            return NS(stop_reason="tool_use", content=[block])
        cite = NS(title="Fed minutes", url="https://example.com/fed")
        role = kw["system"].rsplit("Your role: ", 1)[1]
        return NS(
            stop_reason="end_turn",
            content=[NS(type="text", text=f"{role} says hi", citations=[cite])],
        )


@pytest.fixture
def facts(prices: pd.DataFrame) -> list[dict[str, Any]]:
    t = pd.Series({"SPY": 0.3, "AAA": 0.2, "BBB": 0.0})
    return market_facts(prices, AlgorithmConfig(), {"SPY": "S&P"}, t, t * 0)


def test_facts_describe_each_market(facts: list[dict[str, Any]]) -> None:
    spy = facts[0]
    assert spy["label"] == "S&P" and spy["target_weight"] == 0.3
    assert set(spy["trend_votes"]) == {"21d", "63d", "126d", "252d"}
    assert set(spy["returns"]) == {"1w", "1m", "3m", "12m"}


def test_guard_only_cuts_and_caps_the_cut() -> None:
    target = pd.Series({"A": 0.4, "B": 0.2, "C": 0.1, "D": 0.1, "E": 0.1})
    decisions = {
        "A": {"keep": 0.8},  # allowed
        "B": {"keep": 0.0},  # wants out: capped at the max cut
        "C": {"keep": 1.7},  # wants more: capped at 1
        "D": {"keep": "half"},  # unreadable
    }  # E: missing
    final, status = apply_review(target, decisions, max_cut=0.5)
    assert final.to_dict() == pytest.approx({"A": 0.32, "B": 0.1, "C": 0.1, "D": 0.1, "E": 0.1})
    assert status == {"A": "ok", "B": "clamped", "C": "clamped", "D": REVIEW, "E": REVIEW}
    assert (final <= target).all()


def test_committee_runs_every_role(facts: list[dict[str, Any]]) -> None:
    client = FakeClient([{"market": "SPY", "rating": "Hold", "keep": 1, "reason": "trend intact"}])
    cfg = AgentsConfig(debate_rounds=2)
    rv = review(facts, ["a lesson"], "2026-10-09", cfg, client)
    assert rv.status == "ok"
    roles = [c["system"].rsplit("Your role: ", 1)[1].rstrip(".") for c in client.calls]
    assert sorted(roles[:2]) == ["market analyst", "news analyst"]
    assert roles[2:] == ["bull researcher", "bear researcher"] * 2 + [
        "risk manager",
        "portfolio manager",
    ]
    news = next(c for c in client.calls if "news analyst" in c["system"])
    assert news["tools"][0]["type"].startswith("web_search")
    manager = client.calls[-1]
    assert manager["model"] == cfg.manager_model and "a lesson" in manager["messages"][0]["content"]
    assert rv.decisions["SPY"]["reason"] == "trend intact"
    assert rv.sources == [{"title": "Fed minutes", "url": "https://example.com/fed"}]
    assert rv.run_at and rv.input_hash and rv.configuration["mode"] == "commentary_shadow"
    assert set(rv.reports) == {"market", "news", "debate", "risk"}


def test_citation_filter_excludes_unsafe_urls() -> None:
    sources = _unique(
        [
            {"title": "good", "url": "https://example.com/research"},
            {"title": "bad", "url": "javascript:alert(1)"},
            {"title": "local", "url": "file:///tmp/x"},
        ]
    )
    assert sources == [{"title": "good", "url": "https://example.com/research"}]


def test_no_news_search_when_disabled(facts: list[dict[str, Any]]) -> None:
    client = FakeClient()
    review(facts, [], "2026-10-09", AgentsConfig(news_search=False), client)
    assert not any("news analyst" in c["system"] for c in client.calls)


def test_committee_failure_falls_back(facts: list[dict[str, Any]]) -> None:
    rv = review(facts, [], "2026-10-09", AgentsConfig(), FakeClient(fail=True))
    assert rv.status.startswith("error") and rv.decisions == {}


def test_skipped_without_key_or_when_disabled(facts, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert review(facts, [], "d", AgentsConfig()).status.startswith("skipped: ANTHROPIC")
    assert review(facts, [], "d", AgentsConfig(enabled=False)).status.startswith("skipped")
