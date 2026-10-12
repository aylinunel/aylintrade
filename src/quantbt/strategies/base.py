"""Strategy interfaces and the strategy registry.

There are three kinds of strategy, because they need different inputs and produce
different outputs:

* :class:`PositionStrategy` - one series of bars in, a target exposure per bar out
  (e.g. ``+1`` long, ``0`` flat, ``-1`` short). The engine trades it at the next bar.
* :class:`IntradayStrategy` - bars in, a table of same-day round trips out. Used where
  the entry and exit happen inside one day (opening-range breakouts).
* :class:`PairStrategy` - two close series in, one exposure series per leg out.

Concrete strategies are frozen dataclasses: their fields are the tunable parameters, so a
YAML mapping like ``macd: {fast: 10, slow: 21}`` becomes ``MACD(fast=10, slow=21)``.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal, TypeVar

import pandas as pd

StrategyKind = Literal["position", "intraday", "pair"]
TRADE_COLUMNS = ["date", "side", "entry", "exit"]


class Strategy(ABC):
    """Common metadata. Subclasses set the class variables and are dataclasses."""

    id: ClassVar[str]
    label: ClassVar[str]
    kind: ClassVar[StrategyKind]
    description: ClassVar[str] = ""
    interval: ClassVar[str] = "1d"

    def params(self) -> dict[str, Any]:
        return dataclasses.asdict(self) if dataclasses.is_dataclass(self) else {}

    def warmup(self) -> int:
        """Bars needed before the first valid signal (used to start the evaluation window)."""
        return 0


class PositionStrategy(Strategy):
    kind: ClassVar[StrategyKind] = "position"

    @abstractmethod
    def positions(self, bars: pd.DataFrame) -> pd.Series:
        """Target exposure decided at each bar's close, using only data up to that close."""


class IntradayStrategy(Strategy):
    kind: ClassVar[StrategyKind] = "intraday"

    @abstractmethod
    def trades(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Round trips as rows of ``date`` (session day), ``side`` (+1/-1), ``entry``, ``exit``."""


class PairStrategy(Strategy):
    kind: ClassVar[StrategyKind] = "pair"

    @abstractmethod
    def positions(self, a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
        """Exposure for leg ``a`` and leg ``b`` (fractions of capital), decided at each close."""


def empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLUMNS)


# ------------------------------------------------------------------ registry
_REGISTRY: dict[str, type[Strategy]] = {}
S = TypeVar("S", bound=type[Strategy])


def register(cls: S) -> S:
    """Class decorator that makes a strategy available by its ``id``."""
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls.__name__} must be a dataclass")
    if cls.id in _REGISTRY:
        raise ValueError(f"strategy id '{cls.id}' already registered")
    _REGISTRY[cls.id] = cls
    return cls


def available_strategies() -> list[str]:
    return list(_REGISTRY)


def get_strategy_class(strategy_id: str) -> type[Strategy]:
    try:
        return _REGISTRY[strategy_id]
    except KeyError:
        raise KeyError(f"unknown strategy '{strategy_id}'. Known: {', '.join(_REGISTRY)}") from None


def create_strategy(strategy_id: str, params: dict[str, Any] | None = None) -> Strategy:
    """Instantiate a registered strategy, rejecting unknown parameters with a clear message."""
    cls = get_strategy_class(strategy_id)
    params = dict(params or {})
    allowed = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(
            f"{strategy_id}: unknown parameter(s) {unknown}; allowed: {sorted(allowed)}"
        )
    return cls(**params)
