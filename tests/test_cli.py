from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from aylintrade.cli import main
from aylintrade.data import DataStore


def write_setup(tmp: Path, prices: pd.DataFrame) -> Path:
    markets = {}
    for m in prices:
        c = prices[m]
        frame = pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c}).rename_axis("Date")
        frame.to_csv(tmp / f"{m}.csv")
        markets[m] = {
            "cost_per_side": 0.001,
            "data": {"1d": {"source": "csv", "path": str(tmp / "{symbol}.csv")}},
        }
    raw = {
        "data_dir": str(tmp / "data"),
        "results_dir": str(tmp / "results"),
        "paper_dir": str(tmp / "paper"),
        "site_dir": str(tmp / "site"),
        "markets": markets,
        "algorithm": {"start": "2018-01-01"},
    }
    path = tmp / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_commands(tmp_path: Path, prices: pd.DataFrame, capsys) -> None:
    cfg = str(write_setup(tmp_path, prices))
    assert main(["-c", cfg, "list"]) == 0
    assert main(["-c", cfg, "fetch"]) == 0
    assert DataStore(tmp_path / "data").exists("SPY", "1d")
    assert main(["-c", cfg, "backtest"]) == 0
    assert "| Aylin trend portfolio |" in capsys.readouterr().out
    # the synthetic prices end years ago: daily refuses to trade on stale data
    assert main(["-c", cfg, "daily", "--no-fetch", "--no-agents"]) == 1
    assert not (tmp_path / "paper").exists()
    assert main(["-c", cfg, "site"]) == 0
    assert main(["-c", str(tmp_path / "missing.yaml"), "list"]) == 2
