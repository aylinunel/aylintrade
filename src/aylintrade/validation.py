"""Registered-experiment and walk-forward metadata.

The helpers make temporal splits explicit. They deliberately do not choose a winning parameter or
turn a favourable in-sample score into an approved strategy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import Config


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    holdout_start: int
    holdout_end: int
    embargo: int


def expanding_walk_forward(
    observations: int,
    initial_train: int,
    validation: int,
    holdout: int,
    embargo: int,
) -> list[WalkForwardFold]:
    """Create non-overlapping chronological folds with an embargo on both boundaries."""
    if min(observations, initial_train, validation, holdout) <= 0 or embargo < 0:
        raise ValueError("observations and windows must be positive; embargo cannot be negative")
    folds: list[WalkForwardFold] = []
    train_end = initial_train
    while True:
        validation_start = train_end + embargo
        validation_end = validation_start + validation
        holdout_start = validation_end + embargo
        holdout_end = holdout_start + holdout
        if holdout_end > observations:
            break
        folds.append(
            WalkForwardFold(
                train_start=0,
                train_end=train_end,
                validation_start=validation_start,
                validation_end=validation_end,
                holdout_start=holdout_start,
                holdout_end=holdout_end,
                embargo=embargo,
            )
        )
        train_end = holdout_end
    return folds


def validation_summary(cfg: Config) -> dict[str, Any]:
    """Static contract consumed by the dashboard before experiments are admitted."""
    return {
        "schema_version": "1.0",
        "status": "baseline_only",
        "method": {
            "selection": (
                "expanding-window walk-forward; select only inside training and validation windows"
            ),
            "embargo": (
                "An embargo separates training, validation and holdout labels when a future "
                "holding period overlaps."
            ),
            "execution": (
                "Signals use information available at the decision timestamp; fills occur no "
                "earlier than the next eligible bar."
            ),
        },
        "experiments": [
            {
                "id": "daily-baseline",
                "state": "baseline",
                "description": "Existing daily long-only trend/risk-parity allocator.",
            },
            {
                "id": "macro-context",
                "state": "registered_context_only",
                "description": (
                    "Macro regime display with no allocation impact until vintage-aware data is "
                    "approved."
                ),
            },
            {
                "id": "hourly-shadow",
                "state": cfg.intraday.mode,
                "description": "Session-aware hourly overlay with no paper-weight impact.",
            },
            {
                "id": "agent-shadow",
                "state": cfg.agents.mode,
                "description": "Citation-led commentary and hypothetical guard outcomes only.",
            },
        ],
        "required_evidence": [
            "source version and snapshot hash",
            "decision and execution timestamp",
            "universe and missing-data policy",
            "cost, slippage and cash assumptions",
            "all registered variants and rejected results",
        ],
        "sample_fold": [
            asdict(fold)
            for fold in expanding_walk_forward(
                observations=720, initial_train=360, validation=120, holdout=120, embargo=5
            )
        ],
    }
