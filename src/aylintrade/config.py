"""Typed configuration loaded from YAML: markets, the algorithm's settings, agents, paper account.

Validation happens here so the rest of the code can trust its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a configuration file is missing fields or inconsistent."""


@dataclass(frozen=True)
class SourceSpec:
    """Where one price series comes from: a registered data source plus its arguments."""

    source: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketConfig:
    id: str
    label: str
    group: str
    cost_per_side: float
    data: dict[str, SourceSpec]
    portfolio: bool = True  # False: tested on its own only, never traded


@dataclass(frozen=True)
class AlgorithmConfig:
    """Settings of the trend portfolio. Horizons and windows count business days."""

    horizons: tuple[int, ...] = (21, 63, 126, 252)
    trend_floor: float = 0.25  # share of each position held whatever the trend; 1 = no filter
    vol_span: int = 60
    cov_window: int = 126
    target_vol: float = 0.10
    max_gross: float = 1.0
    rebalance_band: float = 0.03
    start: str = "2006-01-01"

    def __post_init__(self) -> None:
        if not self.horizons or min(self.horizons) < 2:
            raise ConfigError("algorithm.horizons must be lengths of at least 2 days")
        if not 0 <= self.trend_floor <= 1:
            raise ConfigError("algorithm.trend_floor must be in [0, 1]")
        if not 0 < self.target_vol < 1:
            raise ConfigError("algorithm.target_vol is a fraction, e.g. 0.10 for 10% a year")
        if not 0 < self.max_gross <= 3:
            raise ConfigError("algorithm.max_gross must be in (0, 3]; 1.0 means no leverage")
        if not 0 <= self.rebalance_band < 0.5:
            raise ConfigError("algorithm.rebalance_band must be in [0, 0.5)")

    @property
    def warmup(self) -> int:
        return max(max(self.horizons), self.cov_window)


@dataclass(frozen=True)
class AgentsConfig:
    """The Claude review committee. It runs only when ANTHROPIC_API_KEY is set."""

    enabled: bool = True
    analyst_model: str = "claude-sonnet-5-5"
    manager_model: str = "claude-opus-5-5"
    news_search: bool = True
    max_searches: int = 5
    debate_rounds: int = 1
    max_cut: float = 0.5  # the most the committee may take off a position (0.5 = half)

    def __post_init__(self) -> None:
        if not 0 <= self.max_cut <= 1:
            raise ConfigError("agents.max_cut must be in [0, 1]")
        if self.debate_rounds < 1:
            raise ConfigError("agents.debate_rounds must be at least 1")


@dataclass(frozen=True)
class Config:
    markets: dict[str, MarketConfig]
    algorithm: AlgorithmConfig = field(default_factory=AlgorithmConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    paper_capital: float = 100_000.0
    data_dir: Path = Path("data")
    results_dir: Path = Path("results/latest")
    paper_dir: Path = Path("paper")
    site_dir: Path = Path("site")

    @property
    def portfolio_markets(self) -> list[str]:
        return [m.id for m in self.markets.values() if m.portfolio]

    def costs(self) -> dict[str, float]:
        return {m.id: m.cost_per_side for m in self.markets.values()}


def _require(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise ConfigError(f"{where}: missing required field '{key}'")
    return d[key]


def _parse_market(mid: str, raw: dict[str, Any]) -> MarketConfig:
    where = f"markets.{mid}"
    data_raw = _require(raw, "data", where)
    if not isinstance(data_raw, dict) or "1d" not in data_raw:
        raise ConfigError(f"{where}.data needs a daily ('1d') source")
    data = {}
    for interval, spec in data_raw.items():
        spec = dict(spec)
        data[str(interval)] = SourceSpec(
            source=_require(spec, "source", f"{where}.data.{interval}"),
            params={k: v for k, v in spec.items() if k != "source"},
        )
    cost = float(raw.get("cost_per_side", 0.0))
    if not 0 <= cost < 0.05:
        raise ConfigError(f"{where}.cost_per_side should be a fraction, e.g. 0.0005 for 5 bp")
    return MarketConfig(
        id=mid,
        label=str(raw.get("label", mid)),
        group=str(raw.get("group", "")),
        cost_per_side=cost,
        data=data,
        portfolio=bool(raw.get("portfolio", True)),
    )


def _section(cls: type, raw: Any, name: str) -> Any:
    raw = dict(raw or {})
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError(f"{name}: unknown field(s) {unknown}; allowed: {sorted(known)}")
    if "horizons" in raw:
        raw["horizons"] = tuple(int(h) for h in raw["horizons"])
    if "start" in raw:
        raw["start"] = str(raw["start"])
    return cls(**raw)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> Config:
    """Build a validated :class:`Config` from a plain dict (as loaded from YAML)."""
    markets = {
        str(k): _parse_market(str(k), v) for k, v in _require(raw, "markets", "config").items()
    }
    if not any(m.portfolio for m in markets.values()):
        raise ConfigError("at least one market must have portfolio: true")
    base = base_dir or Path.cwd()
    return Config(
        markets=markets,
        algorithm=_section(AlgorithmConfig, raw.get("algorithm"), "algorithm"),
        agents=_section(AgentsConfig, raw.get("agents"), "agents"),
        paper_capital=float(raw.get("paper", {}).get("capital", 100_000)),
        data_dir=base / raw.get("data_dir", "data"),
        results_dir=base / raw.get("results_dir", "results/latest"),
        paper_dir=base / raw.get("paper_dir", "paper"),
        site_dir=base / raw.get("site_dir", "site"),
    )


def load_config(path: str | Path) -> Config:
    """Load a YAML config. Relative paths resolve from the current directory."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return parse_config(raw)
