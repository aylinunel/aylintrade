"""The single OHLCV format every data source must produce."""

from __future__ import annotations

import pandas as pd

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class DataValidationError(ValueError):
    """Raised when price data does not match the OHLCV schema."""


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` in canonical form, or raise :class:`DataValidationError`.

    Canonical form: a tz-naive UTC ``DatetimeIndex`` named ``Date``, sorted and without
    duplicates; float columns ``Open, High, Low, Close, Volume``; no rows with a missing or
    non-positive close.
    """
    rename = {
        c: c.capitalize() for c in df.columns if c.lower() in {x.lower() for x in OHLCV_COLUMNS}
    }
    df = df.rename(columns=rename)
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if "Volume" in missing:
        df = df.assign(Volume=0.0)
        missing.remove("Volume")
    if missing:
        raise DataValidationError(f"missing columns: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataValidationError("index must be a DatetimeIndex")

    out = df[OHLCV_COLUMNS].astype(float)
    idx = out.index
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    out.index = idx.rename("Date")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[out["Close"].notna() & (out["Close"] > 0)]
    if out.empty:
        raise DataValidationError("no valid rows")
    bad = (out["High"] < out[["Open", "Close"]].max(axis=1) - 1e-9) | (
        out["Low"] > out[["Open", "Close"]].min(axis=1) + 1e-9
    )
    if bad.mean() > 0.01:
        raise DataValidationError(f"{bad.sum()} rows have High/Low inconsistent with Open/Close")
    return out
