# Project status reconciliation

Reviewed 23 October 2026. This is a record of branch contents and local checks, not a
deployment or trading approval. The code revisions below pin the evidence independently
of later documentation commits.

## Which implementation is where

| Change | Verified GitHub state | Scope |
| --- | --- | --- |
| [PR #2](https://github.com/aylinunel/aylintrade/pull/2) | Open; head `d5b74d5a0d123a0967c5b702f115b2ff7b654f7d`, branch `rebuild/aylin-trend` | Eight-market daily trend/risk-parity baseline, simulated daily account, optional Claude commentary, React/Vite dashboard |
| [PR #3](https://github.com/aylinunel/aylintrade/pull/3) | Merged **into the rebuild branch**, merge `d5b74d5a0d123a0967c5b702f115b2ff7b654f7d` | Macro/hourly governance, evidence labels, commentary-only agents and React interface; already included in #2 |
| [PR #4](https://github.com/aylinunel/aylintrade/pull/4) | Merged **into main**, merge `3b9029baef9ee1b847c694aa8bf8707bd32dc50b` | Local `quantbt studio`, BTC/ETH spot historical replay, bounded strategy trials, four reviewer roles, deterministic eligibility gates, SQLite events |

The two dashboards are separate implementations. Closing/merging #3 did not put its
macro/hourly dashboard on `main`; merging #4 did not integrate the trend portfolio.
The studio retains the classic `quantbt` CLI. It does not implement the rebuild's daily
multi-market allocation or public forward paper account.

## Claims that need different wording

| Earlier rebuild claim | Current evidence and accurate status |
| --- | --- |
| Classic strategies are replaced by one algorithm | True only of the rebuild proposal's replacement design. `main` retains the registry and adds the studio. |
| Agents trim the paper portfolio by up to 50% | Superseded by #3: `paper.run_day` uses `final = target`; hypothetical trims are saved separately. Configuration rejects `capped_trim`. Studio reviewer votes are a separate eligibility process, requiring three distinct approvals including quant and risk plus every numerical gate. |
| 8.4% return, 0.89 Sharpe and -22% drawdown prove current performance | Rebuild artifacts are `author_reported_unverified`; price records lack snapshot hashes and retrieval evidence. No independent rights-cleared, point-in-time reproduction was run. Main's classic results are legacy snapshots predating corrected pair inference/sizing. Neither set validates studio profitability. |
| Daily paper trading and Pages dashboard are operating | #2 contains a scheduled workflow with commit and Pages deployment steps, but it remains unmerged. `main` has no `daily.yml`. A successful local static build does not prove hosted routing, automation or publication. |
| 41 offline tests describe current validation | Superseded: the rebuild now has 52 passing tests; `main` has 99, checked separately below. Counts do not combine into an integrated suite. |
| A model committee is live-compatible or production-scale | Fake-client/schema tests and seven synthetic local runs do not establish provider/model compatibility, profitability, shared-service capacity or production throughput. |

Macro values in the rebuild are current-display-only and excluded from historical signals;
hourly sources remain quarantined and cannot change paper weights. This does not certify
the studio's cached data under the rebuild's rights/session/vintage gates. The studio has
its own source/freshness/hash checks; local provenance is not independent proof of data rights
or point-in-time availability.

## Local verification

Python 3.12.14, NumPy 2.3.5, pandas 2.2.3, pytest 9.1.1, Ruff 0.17.2 and mypy 2.4.0.
Each revision was checked in its own worktree after editable dependency installation.

| Revision | Commands/checks | Result |
| --- | --- | --- |
| Main `3b9029b` | `make lint test` | Ruff lint/format and mypy (36 source files) passed; 99 tests passed, 89% total coverage |
| Rebuild `d5b74d5` | `make lint test` | Ruff lint/format and mypy (17 source files) passed; 52 tests passed, 87% total coverage; two pandas concatenation FutureWarnings in paper tests |
| Rebuild `d5b74d5` | `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm build` | Passed with pnpm 11.25.0 and Vite 7.2.6; static output only |
| Rebuild `d5b74d5` | `build_site_data` with temporary output; inspect generated JSON and built route files | Schema 1.1; `author_reported_unverified`; `commentary_shadow`; hourly `quarantined`; no paper record; `/`, `/methodology`, `/research`, `/data`, `/paper` static entry files present |
| Main `3b9029b` | `python -m pip wheel --no-deps .` and ZIP inspection | Built wheel includes studio `index.html`, `app.js`, `style.css` |
| Main `3b9029b` | `python scripts/benchmark_studio.py` | Seven 1,500-bar synthetic rule runs, nine trials, 27 saved events each, zero API calls; all proposals asserted `DEMO ONLY` |

Benchmark elapsed seconds: 0.341564, 0.311221, 0.372157, 0.358513, 0.380026,
0.496289, 0.470063. Median 0.372157; maximum 0.496289. Other local checks ran
concurrently, so this is a workload observation, not an isolated speed comparison with
the earlier 0.110-second measurement in [benchmark.md](benchmark.md).

The first rebuild test attempt preceded completion of its editable install and failed
collection with missing-package imports; the completed-install rerun passed all 52 tests.
A wheel attempt without build isolation lacked Hatchling; the normal isolated build passed.
Neither setup failure required repository code changes.

No fresh market download, historical result regeneration, paid model request, daily workflow,
Pages deployment, live order, browser visual review or Windows-locking check was performed.
Static route-file presence does not verify hosted navigation or rendering. Dependency installation
does not validate the configured Claude model IDs or the provider's request/tool contract.

## Integration boundary

`git merge-tree --write-tree origin/main origin/rebuild/aylin-trend` reports conflicts in
README, methodology, packaging, the quantbt CLI/data store/registry/pair implementation and
engine/strategy tests. The rebuild deletes classic quantbt components that the studio uses;
an automatic merge is not a verified integration. Do not resolve this by accepting the rebuild's
deletions or replacing the studio entry point.

The smallest reconciliation is documentation plus corrected PR #2 metadata. Keep #2 open as
an unintegrated proposal. Any later feature port should preserve the studio and its tests,
separate the daily portfolio from spot replay, and keep scheduling/publication changes explicit.
Live provider checks, data reproduction, hosted deployment and production load validation remain
separate unverified tasks. This reconciliation changes no runtime, credentials, workflows,
paper balances or deployment settings.
