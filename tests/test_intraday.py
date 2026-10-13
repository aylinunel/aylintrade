from __future__ import annotations

import numpy as np
import pandas as pd

from aylintrade.config import IntradayConfig
from aylintrade.intraday import (
    HourlyEvidence,
    build_intraday_context,
    shadow_overlay,
    validate_hourly_bars,
)


def valid_evidence(as_of_utc: str = "2024-01-10T23:00:00Z") -> HourlyEvidence:
    return HourlyEvidence(
        market="BTC",
        asset_class="Crypto",
        source_id="fixture:btc-hourly",
        source_status="approved_research",
        snapshot_sha256="a" * 64,
        timezone="UTC",
        session_calendar="24/7 UTC",
        bar_close_semantics="timestamp is the completed hourly close",
        coverage_start="2024-01-01T00:00:00Z",
        coverage_end="2024-01-10T23:00:00Z",
        as_of_utc=as_of_utc,
    )


def hourly_bars(periods: int = 240) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="h", tz="UTC")
    close = np.exp(np.linspace(0, 0.3, len(index)))
    return pd.DataFrame(
        {"Open": close * 0.999, "High": close * 1.001, "Low": close * 0.998, "Close": close},
        index=index,
    )


def test_shadow_overlay_uses_completed_prefix_only() -> None:
    bars = hourly_bars()
    cfg = IntradayConfig()
    evidence = valid_evidence(str(bars.index[199]))
    before = shadow_overlay(bars.iloc[:200], cfg, evidence)
    shocked = bars.copy()
    shocked.iloc[200:] *= 0.1
    after = shadow_overlay(shocked.iloc[:200], cfg, evidence)
    assert before == after
    assert before["mode"] == "shadow"
    assert before["status"] == "shadow"


def test_hourly_validation_rejects_duplicate_bars_and_unapproved_source() -> None:
    bars = hourly_bars(30)
    duplicate = pd.concat([bars, bars.iloc[-1:]]).sort_index()
    errors = validate_hourly_bars(duplicate, valid_evidence())
    assert any("unique" in error for error in errors)
    invalid = shadow_overlay(
        bars,
        IntradayConfig(),
        HourlyEvidence(**{**valid_evidence().__dict__, "source_status": "quarantined"}),
    )
    assert invalid["status"] == "data_invalid"
    assert any("approved_research" in error for error in invalid["errors"])
    stale = HourlyEvidence(**{**valid_evidence().__dict__, "as_of_utc": "2024-01-20T00:00:00Z"})
    assert any("stale" in error for error in validate_hourly_bars(bars, stale))


def test_intraday_context_keeps_quarantined_data_out_of_the_overlay() -> None:
    context = build_intraday_context(IntradayConfig())
    assert context["mode"] == "shadow"
    assert context["records"] == []
    assert "bar-close semantics" in context["source_gate"]
    assert any(market["status"] == "quarantined" for market in context["markets"])
