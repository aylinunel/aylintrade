"""The paper account: trades, idempotence, settling agent decisions, and the site data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aylintrade.config import parse_config
from aylintrade.paper import lessons, run_day, settle
from aylintrade.site import build_site_data
from tests.test_agents import FakeClient


def make_cfg(tmp: Path, mode: str = "commentary_shadow"):
    markets = {
        m: {"label": m, "cost_per_side": 0.001, "data": {"1d": {"source": "csv"}}}
        for m in ("SPY", "AAA", "BBB")
    }
    raw = {
        "markets": markets,
        "algorithm": {"start": "2018-01-01"},
        "agents": {"mode": mode},
        "paper": {"capital": 1000},
    }
    return parse_config(raw, base_dir=tmp)


def test_paper_days(tmp_path: Path, prices: pd.DataFrame) -> None:
    cfg = make_cfg(tmp_path)
    cut = {"market": "SPY", "rating": "Underweight", "keep": 0.6, "reason": "event risk"}
    assert run_day(cfg, prices.iloc[:-6], client=FakeClient([cut]))

    paper = cfg.paper_dir
    state = json.loads((paper / "state.json").read_text())
    ledger = pd.read_csv(paper / "ledger.csv")
    assert state["date"] == str(prices.index[-7].date())
    assert ledger["equity"].iloc[-1] == pytest.approx(1000, rel=0.01)  # only costs so far
    latest = json.loads((paper / "latest.json").read_text())
    # The agents ran and recorded a hypothetical cut, but cannot alter paper weights.
    assert latest["review"]["status"] == "ok"
    assert latest["final"]["SPY"] == pytest.approx(latest["target"]["SPY"])
    assert latest["shadow_final"]["SPY"] == pytest.approx(0.6 * latest["target"]["SPY"], abs=1e-4)

    # same data again: nothing happens
    assert run_day(cfg, prices.iloc[:-6], client=FakeClient([cut])) is False
    # five more days, then the decision settles
    for k in range(5, -1, -1):
        run_day(cfg, prices.iloc[: len(prices) - k], use_agents=False)
    decisions = pd.read_csv(paper / "decisions.csv")
    spy = decisions[decisions["market"] == "SPY"].iloc[0]
    assert spy["return_5d"] == pytest.approx(
        prices["SPY"].iloc[-2] / prices["SPY"].iloc[-7] - 1, abs=1e-5
    )
    assert spy["effect"] == pytest.approx(
        (spy["final"] - spy["target"]) * spy["return_5d"], abs=1e-6
    )
    assert spy["shadow_effect"] == pytest.approx(
        (spy["shadow_final"] - spy["target"]) * spy["return_5d"], abs=1e-6
    )
    assert len(pd.read_csv(paper / "ledger.csv")) == 7

    site = json.loads(build_site_data(cfg).read_text())
    assert site["paper"]["agents"]["settled"] >= 1 and len(site["paper"]["dates"]) == 7


def test_commentary_shadow_keeps_the_paper_weight_unchanged(
    tmp_path: Path, prices: pd.DataFrame
) -> None:
    cfg = make_cfg(tmp_path, mode="commentary_shadow")
    cut = {"market": "SPY", "rating": "Underweight", "keep": 0.6, "reason": "event risk"}
    assert run_day(cfg, prices.iloc[:-1], client=FakeClient([cut]))
    latest = json.loads((cfg.paper_dir / "latest.json").read_text())
    assert latest["review"]["mode"] == "commentary_shadow"
    assert latest["final"]["SPY"] == pytest.approx(latest["target"]["SPY"])
    assert latest["shadow_final"]["SPY"] == pytest.approx(0.6 * latest["target"]["SPY"], abs=1e-4)


def test_config_rejects_agent_weight_override(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="commentary_shadow"):
        make_cfg(tmp_path, mode="capped_trim")


def test_settle_waits_for_five_days(prices: pd.DataFrame) -> None:
    d = pd.DataFrame(
        [
            {
                "date": str(prices.index[-3].date()),
                "market": "SPY",
                "target": 0.2,
                "final": 0.1,
                "close": prices["SPY"].iloc[-3],
                "keep": 0.5,
                "rating": "Sell",
                "reason": "x",
                "return_5d": None,
                "effect": None,
            }
        ]
    )
    assert settle(d, prices)["return_5d"].isna().all()
    assert lessons(d) == []
