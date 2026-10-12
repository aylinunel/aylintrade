"""Source governance metadata for publishable research artifacts.

A source becomes historically eligible only after its cache snapshot, rights status and
point-in-time semantics have been independently reviewed. Until then, results are labeled
``author_reported_unverified`` rather than being treated as an approved performance claim.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..config import Config

SCHEMA_VERSION = "1.1"


def _manifest(cfg: Config, market: str, interval: str) -> dict[str, Any] | None:
    path = cfg.data_dir / f"{market}_{interval}.manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _daily_sources(cfg: Config) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for market in cfg.markets.values():
        for interval, spec in market.data.items():
            manifest = _manifest(cfg, market.id, interval)
            records.append(
                {
                    "id": f"price:{market.id}:{interval}",
                    "purpose": "daily_baseline"
                    if interval == "1d" and market.portfolio
                    else "research_only",
                    "market": market.id,
                    "interval": interval,
                    "provider": spec.source,
                    "status": "author_reported_unverified",
                    "rights_status": (manifest or {}).get("rights_status", "review_required"),
                    "point_in_time_status": "unverified",
                    "snapshot_sha256": (manifest or {}).get("snapshot_sha256"),
                    "retrieved_at": (manifest or {}).get("retrieved_at"),
                    "coverage_start": (manifest or {}).get("coverage_start"),
                    "coverage_end": (manifest or {}).get("coverage_end"),
                    "quality_status": (manifest or {}).get("quality_status", "manifest_missing"),
                    "evidence_status": "manifest_recorded" if manifest else "manifest_missing",
                    "notes": (
                        "Derived metrics are published without raw data. Historical performance "
                        "remains author-reported until a rights-cleared point-in-time reproduction."
                    ),
                }
            )
    return records


def build_provenance(cfg: Config) -> dict[str, Any]:
    """Return browser-safe governance metadata; never include raw provider credentials."""
    records = _daily_sources(cfg)
    records.extend(
        [
            {
                "id": "macro:fred-current",
                "purpose": "current_macro_context",
                "provider": "FRED public graph CSV",
                "status": cfg.macro.source_status,
                "rights_status": "review_required",
                "point_in_time_status": "not_eligible_for_historical_backtest",
                "evidence_status": "current_display_only",
                "notes": "Current context is separate from vintage-aware historical research.",
            },
            {
                "id": "hourly:community-cache",
                "purpose": "hourly_shadow_overlay",
                "provider": "configured community hourly sources",
                "status": cfg.intraday.source_status,
                "rights_status": "review_required",
                "point_in_time_status": "quarantined",
                "evidence_status": "source_gate_not_passed",
                "notes": (
                    "No hourly overlay can influence paper weights until every source gate passes."
                ),
            },
            {
                "id": "agents:web-search",
                "purpose": "current_source_discovery",
                "provider": "configured LLM/web-search provider",
                "status": "commentary_only",
                "rights_status": "review_required",
                "point_in_time_status": "excluded_from_historical_backtest",
                "evidence_status": "commentary_ledger_required",
                "notes": "Generated commentary is citation-led, escaped and non-authoritative.",
            },
        ]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "policy": (
            "Missing governance evidence marks research unverified; it never becomes a "
            "neutral input."
        ),
        "records": records,
    }
