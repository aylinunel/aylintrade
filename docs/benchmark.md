# Studio benchmark and review

Ponytail's engineering order is correctness, security, expected load, meaningful tests, speed,
then unnecessary code. The studio reuses the existing registry and numerical dependencies,
uses SQLite and Python's HTTP server, and ships a browser UI with no Node build or CDN dependency.

## Measured workload

A local Python 3.12.14 run on 13 October 2026 repeated the full rule-review workflow seven times.
Each run processed 1,500 generated hourly bars, nine templates, three validation windows, one
held-out candidate, a cost-stress replay, four reviewer roles and 27 persisted events.

| Measurement | Observed value |
| --- | ---: |
| Median complete run | 0.110 seconds |
| Slowest observed run | 0.132 seconds |
| External API calls | 0 |
| Persisted events per run | 27 |

These observations include numerical processing and SQLite writes. They exclude browser
rendering, data downloads and language-model calls. Generated data measures runtime behavior,
not profitability. Seven repetitions on one machine do not establish production throughput
or performance on 200,000 bars. No comparison against Ponytail's original agent harness was made.

Run `python scripts/benchmark_studio.py` to measure the same workload on your machine. The script
uses a temporary database and reports all timings rather than just the best one.

## Review boundaries

Tests cover causal signals, invalid candles and timestamps, stale data, next-open fills,
fees, gap stops, risk sizing, vote uniqueness, mandatory vetoes, dated news, LLM schema and
evidence rejection, concurrent event writes, recovery, host/origin checks and job capacity.
The tests never place orders or pay for model calls. Reviewer failures cannot become approvals.

Not benchmarked or certified: live profitability, provider/model compatibility, API latency,
derivative margin behavior, shared/public deployment and Windows locking. More complexity should
follow a demonstrated bottleneck or a validated research need.
