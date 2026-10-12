"""Typed experiment configuration loaded from YAML.

A config describes *what* to test (markets, strategies, robustness checks) and *where* data
and results live. Validation happens here so that the rest of the code can trust its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

INTERVALS = ("1d", "1h")


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
    periods_per_year: int
    cost_per_side: float
    data: dict[str, SourceSpec]
    pair_with: str | None = None
    trade: bool = True

    def has_interval(self, interval: str) -> bool:
        return interval in self.data


@dataclass(frozen=True)
class RobustnessConfig:
    strategy: str
    markets: list[str]
    param_sets: list[dict[str, Any]] = field(default_factory=list)
    cost_multipliers: list[float] = field(default_factory=lambda: [1.0])
    subperiods: int = 2


@dataclass(frozen=True)
class Config:
    markets: dict[str, MarketConfig]
    strategies: dict[str, dict[str, Any]]
    data_dir: Path = Path("data")
    results_dir: Path = Path("results/latest")
    robustness: list[RobustnessConfig] = field(default_factory=list)

    @property
    def traded_markets(self) -> list[MarketConfig]:
        return [m for m in self.markets.values() if m.trade]

    def select(
        self, markets: list[str] | None = None, strategies: list[str] | None = None
    ) -> Config:
        """Return a copy restricted to the given market and strategy ids (partners kept)."""
        mk = dict(self.markets)
        if markets:
            _check_known("market", markets, self.markets)
            keep = set(markets) | {
                self.markets[m].pair_with for m in markets if self.markets[m].pair_with
            }
            mk = {
                k: v if k in markets else replace(v, trade=False)
                for k, v in self.markets.items()
                if k in keep
            }
        st = dict(self.strategies)
        if strategies:
            _check_known("strategy", strategies, self.strategies)
            st = {k: v for k, v in self.strategies.items() if k in strategies}
        return Config(mk, st, self.data_dir, self.results_dir, self.robustness)


def _check_known(kind: str, names: list[str], known: dict[str, Any]) -> None:
    unknown = sorted(set(names) - set(known))
    if unknown:
        raise ConfigError(f"Unknown {kind}(s): {', '.join(unknown)}. Known: {', '.join(known)}")


def _require(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise ConfigError(f"{where}: missing required field '{key}'")
    return d[key]


def _parse_market(mid: str, raw: dict[str, Any]) -> MarketConfig:
    where = f"markets.{mid}"
    data_raw = _require(raw, "data", where)
    if not isinstance(data_raw, dict) or not data_raw:
        raise ConfigError(f"{where}.data must map an interval to a source")
    data: dict[str, SourceSpec] = {}
    for interval, spec in data_raw.items():
        interval = str(interval)
        if interval not in INTERVALS:
            raise ConfigError(f"{where}.data: interval '{interval}' not in {INTERVALS}")
        spec = dict(spec)
        data[interval] = SourceSpec(
            source=_require(spec, "source", f"{where}.data.{interval}"),
            params={k: v for k, v in spec.items() if k != "source"},
        )
    if "1d" not in data:
        raise ConfigError(f"{where}: daily ('1d') data is required")
    cost = float(raw.get("cost_per_side", 0.0))
    if not 0 <= cost < 0.05:
        raise ConfigError(f"{where}.cost_per_side should be a fraction, e.g. 0.0005 for 5 bp")
    return MarketConfig(
        id=mid,
        label=str(raw.get("label", mid)),
        group=str(raw.get("group", "")),
        periods_per_year=int(_require(raw, "periods_per_year", where)),
        cost_per_side=cost,
        data=data,
        pair_with=raw.get("pair_with"),
        trade=bool(raw.get("trade", True)),
    )


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> Config:
    """Build a validated :class:`Config` from a plain dict (as loaded from YAML)."""
    markets = {
        str(k): _parse_market(str(k), v) for k, v in _require(raw, "markets", "config").items()
    }
    for m in markets.values():
        if m.pair_with and m.pair_with not in markets:
            raise ConfigError(f"markets.{m.id}.pair_with refers to unknown market '{m.pair_with}'")
    strategies = {str(k): dict(v or {}) for k, v in _require(raw, "strategies", "config").items()}

    robustness = []
    for i, r in enumerate(raw.get("robustness") or []):
        rc = RobustnessConfig(
            strategy=_require(r, "strategy", f"robustness[{i}]"),
            markets=list(_require(r, "markets", f"robustness[{i}]")),
            param_sets=[dict(p) for p in r.get("param_sets", [])],
            cost_multipliers=[float(c) for c in r.get("cost_multipliers", [1.0])],
            subperiods=int(r.get("subperiods", 2)),
        )
        _check_known("market", rc.markets, markets)
        robustness.append(rc)

    base = base_dir or Path.cwd()
    return Config(
        markets=markets,
        strategies=strategies,
        data_dir=base / raw.get("data_dir", "data"),
        results_dir=base / raw.get("results_dir", "results/latest"),
        robustness=robustness,
    )


def load_config(path: str | Path) -> Config:
    """Load a YAML config. Relative data/results paths resolve from the current directory."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return parse_config(raw)
