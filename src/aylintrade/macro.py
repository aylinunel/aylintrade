"""Current macro context with an explicit point-in-time boundary.

The public FRED graph CSV endpoint is convenient for current display. It does not supply the
release-vintage evidence required for a historical macro backtest, so this module labels every
output as current-context-only. A future ALFRED adapter can promote a series only after it
supplies a release timestamp and a documented vintage identifier.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from .config import MacroConfig
from .data.sources import http_get

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES: dict[str, dict[str, str]] = {
    "DGS2": {"label": "2-year Treasury yield", "family": "Rates", "units": "percent"},
    "DGS10": {"label": "10-year Treasury yield", "family": "Rates", "units": "percent"},
    "T10Y2Y": {"label": "10Y-2Y Treasury spread", "family": "Rates", "units": "percent"},
    "DFII10": {"label": "10-year real yield", "family": "Rates", "units": "percent"},
    "CPIAUCSL": {"label": "Headline CPI", "family": "Inflation", "units": "index"},
    "CPILFESL": {"label": "Core CPI", "family": "Inflation", "units": "index"},
    "PAYEMS": {"label": "Nonfarm payrolls", "family": "Labor & growth", "units": "thousands"},
    "UNRATE": {"label": "Unemployment rate", "family": "Labor & growth", "units": "percent"},
    "ICSA": {"label": "Initial jobless claims", "family": "Labor & growth", "units": "claims"},
    "INDPRO": {"label": "Industrial production", "family": "Labor & growth", "units": "index"},
    "BAMLH0A0HYM2": {
        "label": "High-yield option-adjusted spread",
        "family": "Credit",
        "units": "percent",
    },
    "DTWEXBGS": {"label": "Broad U.S. dollar index", "family": "Dollar", "units": "index"},
    "VIXCLS": {"label": "CBOE VIX", "family": "Volatility", "units": "index"},
}


def _parse_fred_csv(raw: bytes, series_id: str) -> pd.Series:
    df = pd.read_csv(io.BytesIO(raw))
    if "observation_date" not in df or series_id not in df:
        raise ValueError(f"FRED response for {series_id} has an unexpected schema")
    values = pd.to_numeric(df[series_id], errors="coerce")
    index = pd.to_datetime(df["observation_date"], errors="coerce")
    out = pd.Series(values.to_numpy(), index=index, name=series_id).dropna()
    if out.empty:
        raise ValueError(f"FRED response for {series_id} contains no numeric observations")
    return out.sort_index()


def _series_payload(series_id: str, values: pd.Series, retrieved_at: str) -> dict[str, Any]:
    meta = SERIES.get(series_id, {"label": series_id, "family": "Other", "units": "unknown"})
    tail = values.tail(180)
    dates = cast(pd.DatetimeIndex, tail.index)
    latest = float(tail.iloc[-1])
    previous = float(tail.iloc[-2]) if len(tail) > 1 else None
    return {
        "id": series_id,
        **meta,
        "latest": latest,
        "previous": previous,
        "change": None if previous is None else latest - previous,
        "observation_date": str(tail.index[-1].date()),
        "observed_period": str(tail.index[-1].date()),
        "retrieved_at": retrieved_at,
        "released_at": None,
        "available_at": None,
        "vintage_id": None,
        "unavailable_fields_reason": (
            "FRED graph CSV provides current display values, not release vintages."
        ),
        "eligibility": "current_context_only",
        "values": [
            {
                "date": str(observation_date.date()),
                "observed_period": str(observation_date.date()),
                "value": float(value),
                "retrieved_at": retrieved_at,
                "released_at": None,
                "available_at": None,
                "vintage_id": None,
            }
            for observation_date, value in zip(dates, tail, strict=True)
        ],
    }


def _labels(payloads: list[dict[str, Any]]) -> list[dict[str, str]]:
    latest = {p["id"]: p["latest"] for p in payloads}
    labels: list[dict[str, str]] = []
    if latest.get("T10Y2Y") is not None:
        labels.append(
            {
                "name": "curve",
                "state": "inverted" if latest["T10Y2Y"] < 0 else "positive",
                "rule": (
                    "10Y-2Y spread below 0 is labeled inverted; this is descriptive, not "
                    "predictive."
                ),
            }
        )
    if latest.get("VIXCLS") is not None:
        labels.append(
            {
                "name": "implied_volatility",
                "state": "elevated" if latest["VIXCLS"] >= 25 else "contained",
                "rule": (
                    "VIX at or above 25 is labeled elevated; this is descriptive, not a "
                    "trade trigger."
                ),
            }
        )
    return labels


def fetch_current_context(data_dir: Path, cfg: MacroConfig) -> dict[str, Any]:
    """Download current observations and cache a browser-safe context document.

    Network errors are recorded per series. This function intentionally does not raise for a
    missing display-only series, because a paper-account run must not trade on macro fetch status.
    """
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    payloads: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for series_id in cfg.series:
        try:
            raw = http_get(FRED_GRAPH_URL.format(series_id=series_id), timeout=30)
            payloads.append(
                _series_payload(series_id, _parse_fred_csv(raw, series_id), retrieved_at)
            )
        except Exception as exc:  # display context is best-effort; details are visible to readers
            errors.append({"series_id": series_id, "error": f"{type(exc).__name__}: {exc}"[:240]})
    status = "current_context_only" if payloads else "unavailable"
    out = {
        "schema_version": "1.0",
        "generated_at": retrieved_at,
        "status": status,
        "source": {
            "provider": "FRED public graph CSV",
            "url": "https://fred.stlouisfed.org/",
            "vintage_policy": (
                "Current values only; excluded from historical strategy tests without ALFRED "
                "release vintages."
            ),
            "coverage_status": "current_display_only",
        },
        "series": payloads,
        "regimes": _labels(payloads),
        "errors": errors,
        "limitations": [
            "Values are current-context display data and can be revised.",
            (
                "A historical macro backtest requires vintage observations and timestamped "
                "release availability."
            ),
        ],
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "macro_current.json").write_text(json.dumps(out, separators=(",", ":")))
    return out


def load_current_context(data_dir: Path, cfg: MacroConfig) -> dict[str, Any]:
    """Load cached macro context or return a clear safe empty state."""
    path = data_dir / "macro_current.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "schema_version": "1.0",
        "status": "unavailable" if cfg.enabled else "disabled",
        "series": [],
        "regimes": [],
        "errors": [],
        "limitations": ["Run `aylintrade macro` to build current macro context."],
    }
