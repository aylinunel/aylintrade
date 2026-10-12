from __future__ import annotations

from pathlib import Path

import pytest

from aylintrade.config import ConfigError, load_config, parse_config

ROOT = Path(__file__).resolve().parents[1]


def minimal(algorithm=None, agents=None, **market_overrides):
    market = {"cost_per_side": 0.001, "data": {"1d": {"source": "csv"}}}
    market.update(market_overrides)
    return {"markets": {"A": market}, "algorithm": algorithm or {}, "agents": agents or {}}


def test_default_config() -> None:
    cfg = load_config(ROOT / "configs" / "default.yaml")
    assert cfg.portfolio_markets == ["SPY", "QQQ", "IWM", "EFA", "GLD", "TLT", "BTC", "ETH"]
    assert {"ES", "GC", "CL"} <= set(cfg.markets) - set(cfg.portfolio_markets)
    assert cfg.algorithm.max_gross == 1.0 and cfg.algorithm.warmup == 252
    assert 0 < cfg.agents.max_cut <= 1


def test_daily_data_required() -> None:
    with pytest.raises(ConfigError, match="daily"):
        parse_config(minimal(data={"1h": {"source": "csv"}}))


def test_cost_given_in_basis_points_is_caught() -> None:
    with pytest.raises(ConfigError, match="fraction"):
        parse_config(minimal(cost_per_side=5))


@pytest.mark.parametrize(
    ("section", "bad", "match"),
    [
        ("algorithm", {"target_vol": 10}, "target_vol"),
        ("algorithm", {"max_gross": 5}, "max_gross"),
        ("algorithm", {"trend_floor": 2}, "trend_floor"),
        ("algorithm", {"horizons": [1]}, "horizons"),
        ("algorithm", {"tagret_vol": 0.1}, "unknown"),
        ("agents", {"max_cut": 1.5}, "max_cut"),
        ("agents", {"debate_rounds": 0}, "debate_rounds"),
    ],
)
def test_bad_settings_are_rejected(section: str, bad: dict, match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        parse_config(minimal(**{section: bad}))


def test_needs_a_portfolio_market() -> None:
    with pytest.raises(ConfigError, match="portfolio"):
        parse_config(minimal(portfolio=False))
