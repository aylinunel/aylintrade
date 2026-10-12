from __future__ import annotations

from pathlib import Path

import pytest

from quantbt.config import ConfigError, load_config, parse_config
from quantbt.strategies import create_strategy

ROOT = Path(__file__).resolve().parents[1]


def minimal(**market_overrides):
    market = {"periods_per_year": 252, "cost_per_side": 0.001, "data": {"1d": {"source": "csv"}}}
    market.update(market_overrides)
    return {"markets": {"A": market}, "strategies": {"macd": {}}}


def test_default_config_is_valid_and_strategies_construct() -> None:
    cfg = load_config(ROOT / "configs" / "default.yaml")
    assert {"SPY", "BTC", "ETH", "ES", "GC", "CL"} <= {m.id for m in cfg.traded_markets}
    for sid, params in cfg.strategies.items():
        create_strategy(sid, params)
    for spec in cfg.robustness:
        for params in spec.param_sets:
            create_strategy(spec.strategy, params)


def test_daily_data_required() -> None:
    with pytest.raises(ConfigError, match="daily"):
        parse_config(minimal(data={"1h": {"source": "csv"}}))


def test_unknown_interval() -> None:
    with pytest.raises(ConfigError, match="interval"):
        parse_config(minimal(data={"1d": {"source": "csv"}, "5m": {"source": "csv"}}))


def test_cost_given_in_basis_points_is_caught() -> None:
    with pytest.raises(ConfigError, match="fraction"):
        parse_config(minimal(cost_per_side=5))


def test_unknown_pair_partner() -> None:
    with pytest.raises(ConfigError, match="pair_with"):
        parse_config(minimal(pair_with="Z"))


def test_select_keeps_partner_as_untraded() -> None:
    cfg = load_config(ROOT / "configs" / "default.yaml").select(["SPY"], ["macd"])
    assert [m.id for m in cfg.traded_markets] == ["SPY"]
    assert "DIA" in cfg.markets and not cfg.markets["DIA"].trade
    assert list(cfg.strategies) == ["macd"]
    with pytest.raises(ConfigError, match="Unknown market"):
        cfg.select(["NOPE"])
