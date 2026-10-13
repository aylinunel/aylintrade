"""Run the bounded offline studio benchmark without retaining generated datasets or runs."""

from __future__ import annotations

import json
import platform
import statistics
import tempfile
from pathlib import Path

from quantbt.studio.data import Settings
from quantbt.studio.research import research
from quantbt.studio.store import Store


def main() -> None:
    settings = Settings()
    times = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        store = Store(root / "benchmark.sqlite")
        for _ in range(7):
            result = research(store, store.create(settings.to_dict()), settings, root)
            times.append(result["elapsed_seconds"])
            assert result["proposal"]["status"] == "DEMO ONLY"
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "bars": 1500,
                    "trials": 9,
                    "mode": "rules on synthetic data",
                    "seconds": times,
                    "median_seconds": statistics.median(times),
                    "maximum_seconds": max(times),
                    "events_per_run": [len(store.events(r["id"])) for r in store.runs()],
                    "api_calls": 0,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
