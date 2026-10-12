from __future__ import annotations

import pandas as pd
import pytest

from quantbt.config import MarketConfig, SourceSpec
from quantbt.data import (
    DataSourceError,
    DataStore,
    DataValidationError,
    MissingDataError,
    available_sources,
    get_source,
    normalize_ohlcv,
)
from quantbt.data.sources import parse_cme_csv, parse_klines


def test_built_in_sources() -> None:
    assert {"csv", "sp500_data", "binance_static_klines", "cme_futures_ohlc"} <= set(
        available_sources()
    )
    with pytest.raises(DataSourceError):
        get_source("nope")


def test_normalize_sorts_dedupes_and_strips_timezone() -> None:
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-01", "2024-01-01"], tz="UTC")
    df = pd.DataFrame(
        {"open": [2, 1, 1], "high": [2, 1, 1], "low": [2, 1, 1], "close": [2, 1, 1]}, idx
    )
    out = normalize_ohlcv(df)
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert out.index.is_monotonic_increasing and out.index.is_unique and out.index.tz is None
    assert (out["Volume"] == 0).all()


def test_normalize_rejects_bad_input() -> None:
    with pytest.raises(DataValidationError, match="missing"):
        normalize_ohlcv(pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"])))
    with pytest.raises(DataValidationError, match="DatetimeIndex"):
        normalize_ohlcv(pd.DataFrame({"Open": [1], "High": [1], "Low": [1], "Close": [1]}))


def test_parse_klines() -> None:
    rows = [
        [1640995200000, "46216.9", "46731.3", "46208.3", "46656.1", "1503.3", 0, "x"],
        [1640998800000, "46656.1", "46949.9", "46574.0", "46778.1", "943.8", 0, "x"],
    ]
    df = normalize_ohlcv(parse_klines(rows))
    assert df.index[0] == pd.Timestamp("2022-01-01 00:00") and df.index[1].hour == 1
    assert df["Close"].iloc[-1] == pytest.approx(46778.1)


def test_parse_cme_csv() -> None:
    raw = b"datetime,open,high,low,close,volume\n2025-03-24,5740,5825.5,5739,5813,1338644\n"
    df = normalize_ohlcv(parse_cme_csv(raw))
    assert df.loc["2025-03-24", "Close"] == 5813


def test_csv_source_and_store_round_trip(tmp_path, daily: pd.DataFrame) -> None:
    daily.to_csv(tmp_path / "XYZ_1d.csv")
    market = MarketConfig(
        id="XYZ",
        label="XYZ",
        group="",
        periods_per_year=252,
        cost_per_side=0.0,
        data={"1d": SourceSpec("csv", {"path": str(tmp_path / "{symbol}_{interval}.csv")})},
    )
    store = DataStore(tmp_path / "data")
    with pytest.raises(MissingDataError):
        store.load("XYZ", "1d")
    store.fetch(market)
    loaded = store.load("XYZ", "1d")
    pd.testing.assert_frame_equal(loaded, daily, check_freq=False)


def test_binance_source_skips_missing_files(monkeypatch) -> None:
    from quantbt.data import sources

    def fake_get(url: str, timeout: float = 60.0) -> bytes:
        if url.endswith("2018-01-01.json"):
            return b'[[1514764800000, "1", "2", "0.5", "1.5", "10"]]'
        raise sources.urllib.error.HTTPError(url, 404, "missing", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(sources, "http_get", fake_get)
    df = get_source("binance_static_klines").load("BTCUSDT", "1d", start="2018-01-01")
    assert len(df) == 1 and df["Close"].iloc[0] == 1.5


def test_cme_source_picks_newest_matching_file(monkeypatch) -> None:
    from quantbt.data import sources

    src = get_source("cme_futures_ohlc")
    files = [
        "ES/ES_1h_20250101_20250301.csv",
        "ES/ES_daily_20250101_20250301.csv",
        "ES/ES_daily_20250101_20260414.csv",
    ]
    monkeypatch.setattr(type(src), "_list_files", lambda self, symbol: files)
    seen = []

    def fake_get(url: str, timeout: float = 60.0) -> bytes:
        seen.append(url)
        return b"datetime,open,high,low,close,volume\n2025-03-24,1,2,0.5,1.5,10\n"

    monkeypatch.setattr(sources, "http_get", fake_get)
    df = src.load("ES", "1d")
    assert seen[0].endswith("ES/ES_daily_20250101_20260414.csv")
    assert df["Close"].iloc[0] == 1.5
    with pytest.raises(DataSourceError, match="does not provide"):
        get_source("sp500_data").load("SPY", "1h")
