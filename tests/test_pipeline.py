"""End-to-end: CSV data -> fetch -> run -> results files, on synthetic markets."""

from __future__ import annotations

import pandas as pd
import pytest

from quantbt.cli import main
from quantbt.config import parse_config
from quantbt.data import DataStore, MissingDataError
from quantbt.pipeline import run_all
from quantbt.reporting import write_run
from quantbt.robustness import run_robustness

from .conftest import make_bars


@pytest.fixture()
def config(tmp_path):
    src = tmp_path / "csv"
    src.mkdir()
    make_bars(420, seed=5).to_csv(src / "AAA_1d.csv")
    make_bars(420, seed=6).to_csv(src / "BBB_1d.csv")
    make_bars(24 * 60, freq="h", seed=7, start="2021-01-01").to_csv(src / "AAA_1h.csv")
    path = str(src / "{symbol}_{interval}.csv")
    raw = {
        "data_dir": str(tmp_path / "data"),
        "results_dir": str(tmp_path / "results"),
        "markets": {
            "AAA": {
                "periods_per_year": 252,
                "cost_per_side": 0.0005,
                "pair_with": "BBB",
                "data": {
                    "1d": {"source": "csv", "path": path},
                    "1h": {"source": "csv", "path": path},
                },
            },
            "BBB": {
                "periods_per_year": 252,
                "cost_per_side": 0.0005,
                "trade": False,
                "data": {"1d": {"source": "csv", "path": path}},
            },
            "CCC": {
                "periods_per_year": 365,
                "cost_per_side": 0.001,
                "data": {"1d": {"source": "csv", "path": path.replace("{symbol}", "BBB")}},
            },
        },
        "strategies": {
            "buy_and_hold": {},
            "macd": {},
            "dual_thrust": {},
            "london_breakout": {},
            "pair_trading": {"window": 120},
        },
        "robustness": [
            {
                "strategy": "macd",
                "markets": ["AAA"],
                "param_sets": [{"fast": 5, "slow": 20}],
                "cost_multipliers": [1, 2],
            }
        ],
    }
    return parse_config(raw)


def test_run_requires_fetched_data(config) -> None:
    with pytest.raises(MissingDataError):
        run_all(config)


def test_end_to_end(config, tmp_path) -> None:
    store = DataStore(config.data_dir)
    for m in config.markets.values():
        store.fetch(m)
    out = run_all(config, jobs=1)
    res = out.results.set_index(["market", "strategy"])

    assert set(res.index.get_level_values("market")) == {"AAA", "CCC"}  # BBB is partner-only
    assert res.loc[("AAA", "london_breakout"), "status"] == "ok"
    assert res.loc[("CCC", "london_breakout"), "status"] == "skipped"
    assert res.loc[("CCC", "pair_trading"), "status"] == "skipped"
    assert res.loc[("AAA", "pair_trading"), "start"] > res.loc[("AAA", "macd"), "start"]
    bh = res.loc[("AAA", "buy_and_hold")]
    assert bh["sharpe_vs_bh"] == pytest.approx(0.0, abs=1e-9)

    # parallel run gives identical numbers
    parallel = run_all(config, jobs=2).results
    pd.testing.assert_frame_equal(out.results, parallel)

    write_run(out, config.results_dir)
    for f in ("results.csv", "curves.csv", "summary.md", "run.json"):
        assert (config.results_dir / f).exists()
    assert "beat buy & hold" in (config.results_dir / "summary.md").read_text()

    rows, years = run_robustness(config)
    assert set(rows["test"]) == {"parameters", "cost per side", "subperiod"}
    assert not years.empty


def test_cli_list_and_errors(tmp_path, capsys) -> None:
    assert main(["list", "-c", "configs/default.yaml"]) == 0
    assert "macd" in capsys.readouterr().out
    assert main(["run", "-c", str(tmp_path / "missing.yaml")]) == 2


def test_charts(config) -> None:
    pytest.importorskip("matplotlib")
    from quantbt.reporting import plot_charts

    store = DataStore(config.data_dir)
    for m in config.markets.values():
        store.fetch(m)
    write_run(run_all(config), config.results_dir)
    paths = plot_charts(config.results_dir)
    names = {p.name for p in paths}
    assert {"equity_AAA.png", "equity_CCC.png", "heatmap_sharpe_vs_hold.png"} == names
    assert all(p.stat().st_size > 10_000 for p in paths)
