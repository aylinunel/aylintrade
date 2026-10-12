from __future__ import annotations

from aylintrade.config import parse_config
from aylintrade.data.provenance import build_provenance


def test_provenance_marks_current_macro_and_hourly_inputs_conservatively() -> None:
    cfg = parse_config(
        {
            "markets": {
                "SPY": {
                    "label": "SPY",
                    "group": "US stocks",
                    "cost_per_side": 0.0005,
                    "data": {"1d": {"source": "csv", "path": "prices.csv"}},
                }
            }
        }
    )
    provenance = build_provenance(cfg)
    records = {record["id"]: record for record in provenance["records"]}
    assert (
        records["macro:fred-current"]["point_in_time_status"]
        == "not_eligible_for_historical_backtest"
    )
    assert records["hourly:community-cache"]["status"] == "quarantined"
