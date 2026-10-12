"""The backtest study end to end on synthetic data stored like real data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aylintrade.data import DataStore
from aylintrade.research import ALGO, RP_HOLD, SPY_HOLD, run_study, summary_markdown, write_study
from tests.test_paper import make_cfg


def test_study(tmp_path: Path, prices: pd.DataFrame) -> None:
    cfg = make_cfg(tmp_path)
    store = DataStore(cfg.data_dir)
    for m in prices:
        c = prices[m]
        store.save(
            m, "1d", pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 0.0})
        )
    study = run_study(cfg)

    assert list(study["stats"])[:3] == [ALGO, SPY_HOLD, "Equal-weight buy & hold"]
    spy_growth = study["curves"][SPY_HOLD][-1]
    start = pd.Timestamp(study["start"])
    expected = prices["SPY"].iloc[-1] / prices["SPY"][prices.index >= start].iloc[0]
    assert spy_growth == pytest.approx(expected * (1 - 0.001), rel=1e-4)  # one purchase cost
    assert study["stats"][ALGO]["volatility"] < study["stats"][SPY_HOLD]["volatility"]
    assert RP_HOLD in study["stats"]
    tests = {r["test"] for r in study["robustness"]}
    assert {"As configured", "Trading costs", "Core holding", "Sub-period"} <= tests
    assert all(r["status"] == "ok" for r in study["per_market"])

    write_study(study, cfg.results_dir)
    md = (cfg.results_dir / "summary.md").read_text()
    assert md == summary_markdown(study) and "| Aylin trend portfolio |" in md
