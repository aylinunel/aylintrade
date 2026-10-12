"""Session-aware hourly research features with fail-closed source gates.

The public dashboard is intentionally empty until a source provides a reviewed evidence bundle.
Even a validated overlay is shadow-only and has no dependency on daily paper-account weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from .config import IntradayConfig

SESSION_RULES = {
    "ETF": "America/New_York regular session; no synthetic closed-hour bars.",
    "Futures": "Named contract, documented roll and exchange session required before eligibility.",
    "Crypto": "UTC, 24/7; a bar is eligible only after its close time.",
}


@dataclass(frozen=True)
class HourlyEvidence:
    """Non-secret minimum evidence required before calculating an hourly overlay."""

    market: str
    asset_class: Literal["ETF", "Futures", "Crypto"]
    source_id: str
    source_status: str
    snapshot_sha256: str
    timezone: str
    session_calendar: str
    bar_close_semantics: str
    coverage_start: str
    coverage_end: str
    as_of_utc: str
    continuous_roll_id: str | None = None


def _annualized_volatility(returns: pd.Series) -> float | None:
    clean = returns.dropna()
    if len(clean) < 2:
        return None
    return float(clean.std(ddof=1) * np.sqrt(24 * 365))


def validate_hourly_bars(bars: pd.DataFrame, evidence: HourlyEvidence) -> list[str]:
    """Return every pre-trade data-quality failure; callers must fail closed when nonempty."""
    errors: list[str] = []
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(bars.columns):
        errors.append("OHLC columns are required")
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        errors.append("bar index must be timezone-aware")
    elif str(bars.index.tz) != "UTC":
        errors.append("bar index must be normalized to UTC")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        errors.append("bar timestamps must be unique and strictly increasing")
    if len(bars) and required.issubset(bars.columns):
        high_low = bars["High"] < bars["Low"]
        close_bounds = (bars["Close"] < bars["Low"]) | (bars["Close"] > bars["High"])
        open_bounds = (bars["Open"] < bars["Low"]) | (bars["Open"] > bars["High"])
        if bool((high_low | close_bounds | open_bounds).any()):
            errors.append("OHLC bounds are invalid")
    if evidence.source_status != "approved_research":
        errors.append("source has not passed the approved_research gate")
    if not evidence.snapshot_sha256 or not evidence.source_id:
        errors.append("source snapshot evidence is missing")
    if not evidence.bar_close_semantics or not evidence.session_calendar:
        errors.append("bar-close and session metadata are required")
    try:
        as_of = pd.Timestamp(evidence.as_of_utc)
        if as_of.tzinfo is None:
            errors.append("as_of_utc must include a timezone")
        elif len(bars) and as_of - bars.index[-1] > pd.Timedelta(hours=2):
            errors.append("completed bars are stale relative to the evidence as-of time")
    except (TypeError, ValueError):
        errors.append("as_of_utc is invalid")
    if evidence.asset_class == "Crypto":
        if evidence.timezone != "UTC":
            errors.append("crypto bars must declare UTC timezone")
        if (
            len(bars) > 1
            and not (bars.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()
        ):
            errors.append("crypto hourly bars contain a gap")
    if evidence.asset_class == "ETF" and evidence.timezone != "America/New_York":
        errors.append("ETF source must declare America/New_York session timezone")
    if evidence.asset_class == "ETF" and isinstance(bars.index, pd.DatetimeIndex) and bars.index.tz:
        local = bars.index.tz_convert("America/New_York")
        valid_hours = local.hour.isin(range(10, 17))
        valid_days = local.dayofweek < 5
        if not bool((valid_hours & valid_days).all()):
            errors.append("ETF bars fall outside the documented regular session")
    if evidence.asset_class == "Futures" and not evidence.continuous_roll_id:
        errors.append("futures source needs a continuous-contract roll identifier")
    return errors


def shadow_overlay(
    bars: pd.DataFrame, cfg: IntradayConfig, evidence: HourlyEvidence
) -> dict[str, Any]:
    """Calculate causal features only from a source-gated completed hourly-bar bundle."""
    errors = validate_hourly_bars(bars, evidence)
    if errors:
        return {"status": "data_invalid", "mode": cfg.mode, "errors": errors}
    series = bars["Close"].dropna().astype(float)
    need = max(max(cfg.horizons), max(cfg.vol_windows)) + 1
    if len(series) < need:
        return {
            "status": "data_invalid",
            "reason": f"{len(series)} completed bars; needs {need}",
            "mode": cfg.mode,
        }
    last = float(series.iloc[-1])
    trend = {f"{h}h": float(last / series.iloc[-h - 1] - 1) for h in cfg.horizons}
    returns = series.pct_change(fill_method=None)
    vol = {f"{w}h": _annualized_volatility(returns.tail(w)) for w in cfg.vol_windows}
    positive = sum(value > 0 for value in trend.values())
    score = positive / len(trend)
    regime = "risk_on" if score >= 0.75 else "risk_off" if score <= 0.25 else "neutral"
    return {
        "status": "shadow",
        "mode": cfg.mode,
        "as_of": str(series.index[-1]),
        "source": {"id": evidence.source_id, "snapshot_sha256": evidence.snapshot_sha256},
        "trend": trend,
        "realized_volatility": vol,
        "trend_breadth": score,
        "regime": regime,
        "proposed_timing": "maintain" if regime == "neutral" else "review",
        "limitations": "Shadow-only research context; no effect on paper-account weights.",
    }


def build_intraday_context(cfg: IntradayConfig) -> dict[str, Any]:
    """Return the publishable state while hourly sources remain unapproved."""
    quarantined_reason = (
        "Hourly source is quarantined pending rights, snapshot, coverage and quality review."
    )
    markets = [
        {
            "market": "BTC",
            "asset_class": "Crypto",
            "status": cfg.source_status,
            "session_rule": SESSION_RULES["Crypto"],
            "reason": quarantined_reason,
        },
        {
            "market": "ETH",
            "asset_class": "Crypto",
            "status": cfg.source_status,
            "session_rule": SESSION_RULES["Crypto"],
            "reason": quarantined_reason,
        },
        {
            "market": "ETF basket",
            "asset_class": "ETF",
            "status": "unavailable",
            "session_rule": SESSION_RULES["ETF"],
            "reason": "No approved long-history hourly ETF source is configured.",
        },
        {
            "market": "Futures basket",
            "asset_class": "Futures",
            "status": "quarantined",
            "session_rule": SESSION_RULES["Futures"],
            "reason": "Continuous-contract and roll metadata are not approved.",
        },
    ]
    return {
        "schema_version": "1.1",
        "mode": cfg.mode,
        "status": cfg.source_status,
        "feature_definition": {
            "trend_horizons_hours": list(cfg.horizons),
            "volatility_windows_hours": list(cfg.vol_windows),
            "execution": (
                "completed bars only; a future eligible experiment fills no earlier than the "
                "next market bar"
            ),
        },
        "source_gate": [
            "rights",
            "snapshot",
            "coverage",
            "UTC normalization",
            "session calendar",
            "bar-close semantics",
            "duplicate/gap/OHLC validation",
            "continuous futures roll",
        ],
        "markets": markets,
        "records": [],
        "limitations": [
            "This layer is a separate shadow overlay and cannot alter daily paper weights.",
            "ETF, futures and crypto are not coerced into a shared artificial hourly calendar.",
        ],
    }
