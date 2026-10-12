"""Pluggable price-data sources.

Each source turns ``(symbol, interval, **params)`` into an OHLCV frame. Register a new one
with :func:`register_source` and refer to it by name in the config:

.. code-block:: python

    @register_source("my_vendor")
    class MyVendorSource(DataSource):
        def fetch(self, symbol, interval, **params):
            ...

The built-in sources download free datasets hosted on GitHub, so no API keys are needed.
"""

from __future__ import annotations

import io
import json
import logging
import subprocess
import tempfile
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd

from .schema import normalize_ohlcv

log = logging.getLogger(__name__)

_SOURCES: dict[str, type[DataSource]] = {}
USER_AGENT = "aylintrade (+https://github.com/aylinunel/aylintrade)"


class DataSourceError(RuntimeError):
    """Raised when a source cannot provide the requested series."""


class DataSource(ABC):
    """Base class: fetch one symbol at one bar interval as canonical OHLCV."""

    name: ClassVar[str]
    intervals: ClassVar[tuple[str, ...]] = ("1d",)

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (
            Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "aylintrade"
        )

    def load(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        if interval not in self.intervals:
            raise DataSourceError(f"{self.name} does not provide '{interval}' bars")
        return normalize_ohlcv(self.fetch(symbol, interval, **params))

    @abstractmethod
    def fetch(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        """Return raw OHLCV for ``symbol``; normalisation is applied by :meth:`load`."""


def register_source(name: str):
    def deco(cls: type[DataSource]) -> type[DataSource]:
        if name in _SOURCES:
            raise ValueError(f"data source '{name}' already registered")
        cls.name = name
        _SOURCES[name] = cls
        return cls

    return deco


def get_source(name: str, cache_dir: Path | None = None) -> DataSource:
    try:
        return _SOURCES[name](cache_dir=cache_dir)
    except KeyError:
        raise DataSourceError(f"unknown data source '{name}'. Known: {sorted(_SOURCES)}") from None


def available_sources() -> list[str]:
    return sorted(_SOURCES)


# ------------------------------------------------------------------ http helpers
def http_get(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return bytes(resp.read())


def download(url: str, dest: Path, timeout: float = 600.0) -> Path:
    """Download ``url`` to ``dest`` atomically (no half-written files on failure)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    tmp.replace(dest)
    return dest


# ------------------------------------------------------------------ local files
@register_source("csv")
class CsvSource(DataSource):
    """Local CSV with a date column and OHLC(V) columns.

    Params: ``path`` (may contain ``{symbol}`` and ``{interval}``), ``date_column``
    (default ``Date``).
    """

    intervals = ("1d", "1h")

    def fetch(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        path = Path(str(params["path"]).format(symbol=symbol, interval=interval))
        if not path.exists():
            raise DataSourceError(f"CSV not found: {path}")
        date_col = params.get("date_column", "Date")
        df = pd.read_csv(path)
        df.index = pd.DatetimeIndex(pd.to_datetime(df.pop(date_col), utc=True))
        return df


# ------------------------------------------------------------------ S&P 500 + ETFs
@register_source("sp500_data")
class Sp500DataSource(DataSource):
    """Daily US stocks and ETFs from github.com/Johnbrick123/sp500-data (nightly, from 1995).

    Prices are adjusted for dividends and splits using the dataset's ``adj_close``.
    """

    URL = "https://github.com/Johnbrick123/sp500-data/releases/download/data/prices.parquet"

    def fetch(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        path = self.cache_dir / "sp500_data" / "prices.parquet"
        if params.get("refresh") or not path.exists():
            log.info("downloading %s (about 170 MB, cached afterwards)", self.URL)
            download(params.get("url", self.URL), path)
        df = pd.read_parquet(path, filters=[("ticker", "==", symbol)])
        if df.empty:
            raise DataSourceError(f"sp500_data has no ticker '{symbol}'")
        df = df.sort_values("date").set_index("date")
        factor = df["adj_close"] / df["close"]
        out = pd.DataFrame(
            {c.capitalize(): df[c] * factor for c in ("open", "high", "low", "close")}
        )
        out["Volume"] = df["volume"]
        out.index = pd.DatetimeIndex(out.index)
        return out


# ------------------------------------------------------------------ Binance via GitHub
@register_source("binance_static_klines")
class BinanceStaticKlinesSource(DataSource):
    """Binance spot klines mirrored daily at github.com/finom/static-klines.

    Daily files hold two years each (starting on even years); hourly files hold one month.
    Params: ``start`` (ISO date, default 2016-01-01 for daily, 2022-01-01 for hourly).
    """

    intervals = ("1d", "1h")
    BASE = "https://raw.githubusercontent.com/finom/static-klines/main/.klines-cache"

    def _starts(self, interval: str, start: date, end: date) -> list[date]:
        if interval == "1d":
            first = start.year - (start.year % 2)
            return [date(y, 1, 1) for y in range(first, end.year + 1, 2)]
        months = pd.date_range(start.replace(day=1), end, freq="MS")
        return [d.date() for d in months]

    def fetch(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        default = "2016-01-01" if interval == "1d" else "2022-01-01"
        start = pd.Timestamp(params.get("start", default)).date()
        rows: list[list[Any]] = []
        for d in self._starts(interval, start, date.today()):
            url = f"{self.BASE}/{symbol}/{interval}/{d.isoformat()}.json"
            try:
                rows += json.loads(http_get(url))
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
        return parse_klines(rows)


def parse_klines(rows: list[list[Any]]) -> pd.DataFrame:
    """Binance kline arrays -> OHLCV frame indexed by bar open time (UTC)."""
    if not rows:
        raise DataSourceError("no klines returned")
    df = pd.DataFrame(
        [r[:6] for r in rows], columns=["t", *["Open", "High", "Low", "Close", "Volume"]]
    )
    df = df.astype(float)
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("t"), unit="ms", utc=True))
    return df


# ------------------------------------------------------------------ CME futures via GitHub
@register_source("cme_futures_ohlc")
class CmeFuturesSource(DataSource):
    """CME futures bars from github.com/axb0306/cme-futures-ohlc.

    Files are named ``<SYM>/<SYM>_<interval>_<start>_<end>.csv``; the newest matching file is
    used. History is short (roughly one year), so treat results as anecdotal.
    Params: ``file`` to pin an exact path inside the repo.
    """

    intervals = ("1d", "1h")
    REPO = "axb0306/cme-futures-ohlc"
    LABELS: ClassVar[dict[str, str]] = {"1d": "daily", "1h": "1h"}

    def _list_files(self, symbol: str) -> list[str]:
        api = f"https://api.github.com/repos/{self.REPO}/contents/{symbol}"
        try:
            return [item["path"] for item in json.loads(http_get(api, timeout=30))]
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
            log.info("GitHub API listing failed (%s); falling back to git", e)
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "-q",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--no-checkout",
                    f"https://github.com/{self.REPO}",
                    tmp,
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )
            out = subprocess.run(
                ["git", "-C", tmp, "ls-tree", "--name-only", "HEAD", f"{symbol}/"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        return out.split()

    def fetch(self, symbol: str, interval: str, **params: Any) -> pd.DataFrame:
        file = params.get("file")
        if not file:
            prefix = f"{symbol}/{symbol}_{self.LABELS[interval]}_"
            matches = sorted(f for f in self._list_files(symbol) if f.startswith(prefix))
            if not matches:
                raise DataSourceError(f"no {interval} file for {symbol} in {self.REPO}")
            file = matches[-1]
        raw = http_get(f"https://raw.githubusercontent.com/{self.REPO}/main/{file}")
        return parse_cme_csv(raw)


def parse_cme_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("datetime"), utc=True))
    return df[["open", "high", "low", "close", "volume"]]
