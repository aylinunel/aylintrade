"""Local cache of normalised price data, one Parquet file per market and interval."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import MarketConfig
from .sources import get_source

log = logging.getLogger(__name__)


class MissingDataError(FileNotFoundError):
    """Raised when a backtest needs data that has not been fetched yet."""


class DataStore:
    """Reads/writes ``<root>/<market>_<interval>.parquet``; raw downloads go in ``<root>/raw``."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path(self, market: str, interval: str) -> Path:
        return self.root / f"{market}_{interval}.parquet"

    def exists(self, market: str, interval: str) -> bool:
        return self.path(market, interval).exists()

    def load(self, market: str, interval: str) -> pd.DataFrame:
        p = self.path(market, interval)
        if not p.exists():
            raise MissingDataError(f"{p} not found. Run `quantbt fetch` first.")
        return pd.read_parquet(p)

    def save(self, market: str, interval: str, df: pd.DataFrame) -> Path:
        p = self.path(market, interval)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p)
        return p

    def fetch(self, market: MarketConfig, force: bool = False) -> dict[str, pd.DataFrame]:
        """Download every interval configured for ``market`` (skips cached ones unless forced)."""
        out = {}
        for interval, spec in market.data.items():
            if self.exists(market.id, interval) and not force:
                log.info("%s %s: cached", market.id, interval)
                out[interval] = self.load(market.id, interval)
                continue
            source = get_source(spec.source, cache_dir=self.root / "raw")
            symbol = spec.params.get("symbol", market.id)
            params = {k: v for k, v in spec.params.items() if k != "symbol"}
            df = source.load(symbol, interval, **params)
            self.save(market.id, interval, df)
            log.info(
                "%s %s: %d bars, %s to %s",
                market.id,
                interval,
                len(df),
                df.index[0].date(),
                df.index[-1].date(),
            )
            out[interval] = df
        return out
