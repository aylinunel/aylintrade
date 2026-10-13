"""Local cache of normalised price data plus fetch-time evidence manifests."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import MarketConfig
from .sources import get_source

log = logging.getLogger(__name__)


class MissingDataError(FileNotFoundError):
    """Raised when a backtest needs data that has not been fetched yet."""


class DataStore:
    """Reads/writes one Parquet cache and one non-secret evidence manifest per source."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path(self, market: str, interval: str) -> Path:
        return self.root / f"{market}_{interval}.parquet"

    def manifest_path(self, market: str, interval: str) -> Path:
        return self.root / f"{market}_{interval}.manifest.json"

    def exists(self, market: str, interval: str) -> bool:
        return self.path(market, interval).exists()

    def load(self, market: str, interval: str) -> pd.DataFrame:
        path = self.path(market, interval)
        if not path.exists():
            raise MissingDataError(f"{path} not found. Run `aylintrade fetch` first.")
        return pd.read_parquet(path)

    def save(self, market: str, interval: str, df: pd.DataFrame) -> Path:
        path = self.path(market, interval)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
        return path

    def _write_manifest(
        self, market: MarketConfig, interval: str, provider: str, path: Path, df: pd.DataFrame
    ) -> Path:
        """Persist only derived cache evidence; raw provider credentials are never recorded."""
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        coverage_start = str(pd.Timestamp(df.index.min()).isoformat()) if len(df) else None
        coverage_end = str(pd.Timestamp(df.index.max()).isoformat()) if len(df) else None
        manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "market": market.id,
            "interval": interval,
            "provider": provider,
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "snapshot_sha256": digest,
            "bar_count": len(df),
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
            "timestamp_semantics": (
                "provider-normalized cache; point-in-time eligibility unverified"
            ),
            "quality_status": "not_independently_validated",
            "rights_status": "review_required",
        }
        out = self.manifest_path(market.id, interval)
        out.write_text(json.dumps(manifest, separators=(",", ":")))
        return out

    def fetch(self, market: MarketConfig, force: bool = False) -> dict[str, pd.DataFrame]:
        """Download every configured interval; cached data is retained with its prior manifest."""
        out: dict[str, pd.DataFrame] = {}
        for interval, spec in market.data.items():
            if self.exists(market.id, interval) and not force:
                log.info("%s %s: cached", market.id, interval)
                out[interval] = self.load(market.id, interval)
                continue
            source = get_source(spec.source, cache_dir=self.root / "raw")
            symbol = spec.params.get("symbol", market.id)
            params = {key: value for key, value in spec.params.items() if key != "symbol"}
            df = source.load(symbol, interval, **params)
            path = self.save(market.id, interval, df)
            self._write_manifest(market, interval, spec.source, path, df)
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
