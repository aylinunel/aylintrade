# AylinTrade

**An evidence-led, long-only market-research baseline with transparent paper accounting, release-aware macro context, and a quarantined hourly research layer.**

[![CI](https://github.com/aylinunel/aylintrade/actions/workflows/ci.yml/badge.svg)](https://github.com/aylinunel/aylintrade/actions/workflows/ci.yml)
[![Daily](https://github.com/aylinunel/aylintrade/actions/workflows/daily.yml/badge.svg)](https://github.com/aylinunel/aylintrade/actions/workflows/daily.yml)
![Python](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

**Dashboard:** https://aylinunel.github.io/aylintrade/ (after GitHub Pages is enabled and the workflow is run)

> **Paper-only research, not financial advice.** AylinTrade does not connect to brokers, transmit orders, use leverage or short selling, or make personalised recommendations. Historical simulations are not forecasts.

## What it does

After the US close, the GitHub Action:

1. refreshes daily data for SPY, QQQ, IWM, EFA, GLD, TLT, BTC and ETH;
2. runs the deterministic long-only daily trend/risk-parity baseline;
3. records one simulated paper-account day with disclosed fixed costs and drift-aware holdings;
4. builds a **current-context-only** macro view from official FRED series;
5. prepares the static React dashboard and deployable GitHub Pages artifact.

The optional committee remains **commentary shadow** by default: it may produce a cited report and a hypothetical capped trim, but it cannot change paper weights. Its hypothetical outcomes are settled separately after five trading days.

## The baseline model

The daily allocation is intentionally simple and auditable:

1. **Trend:** eight votes per market (price above its 1, 3, 6 and 12-month average; positive return over each horizon). A quarter of each position remains held.
2. **Risk parity:** size markets inversely to trailing volatility, then include covariance in portfolio risk scaling.
3. **Volatility target:** aim for 10% expected annualized volatility, never above 100% gross exposure.
4. **Rebalance band:** skip small trades below 3% of the account to avoid unnecessary turnover.

The site shows this model against matched-period SPY buy-and-hold, equal-weight buy-and-hold and always-invested risk parity. It does not automatically select the historical “winner.”

## Reported daily-study results

These are **author-reported historical simulations** over 2006–October 2026 using the repository's current source adapters and fixed cost assumptions; they have not yet been reproduced from a separately pinned, rights-cleared data bundle.

| Portfolio | Per year | Volatility | Sharpe | Worst drawdown |
|---|---:|---:|---:|---:|
| **Aylin trend portfolio** | **8.4%** | **9.5%** | **0.89** | **−22%** |
| S&P 500 (SPY) buy & hold | 11.0% | 19.0% | 0.64 | −55% |
| Equal-weight buy & hold | 13.2% | 17.6% | 0.79 | −40% |
| Risk parity, always invested | 8.4% | 9.9% | 0.87 | −24% |

The daily baseline earns less annualized return than SPY in this simulation, while showing lower volatility and drawdown. The always-invested risk-parity comparison is close, so any claimed incremental trend effect is small and may be noise.

## Macro and hourly research boundaries

### Macro

The dashboard displays rates/curve, inflation, labor/growth, credit, dollar and volatility context. Current FRED graph values are **not** used in historical backtests because they do not establish the historical release vintage and availability timestamp required to prevent revision leakage. ALFRED vintages and official BLS/New York Fed release calendars are the intended approval path. See [the macro/hourly design](docs/macro-intraday-research-design.md).

### Hourly

Hourly features are a separate, **shadow-only** overlay with 4/12/24/72-hour trend and 24/168-hour realized-volatility windows. ETF, futures and crypto each preserve their own session rules. The community hourly datasets in the report remain `quarantined` until rights, snapshot, coverage, timezone, bar-close, roll and data-quality gates are documented. They cannot affect paper weights.

### Agents

Agents and web search are current-context research aids, not historical features or allocation authorities. Each run must retain source citations, model/provider/configuration metadata, input provenance, errors and the deterministic-guard outcome. The default mode stores hypothetical effects; it leaves the paper allocator unchanged.

## Quick start

```bash
git clone https://github.com/aylinunel/aylintrade && cd aylintrade
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
corepack enable
pnpm install

.venv/bin/aylintrade fetch
.venv/bin/aylintrade backtest
.venv/bin/aylintrade macro       # current context; not historical signals
.venv/bin/aylintrade site
pnpm dev                          # interactive preview at http://localhost:3000
```

`aylintrade daily` refreshes the baseline, runs one simulated paper-account day, updates best-effort macro context and builds dashboard data. Use `--no-agents` to skip the commentary run entirely.

## Source governance

Every public result should be attached to an evidence bundle: source and rights status, snapshot hash, retrieval time, coverage, decision and execution time, session/timezone rule, configuration/code version, costs, benchmarks, validation results and unresolved limitations.

- [Source-governance memorandum](docs/source-governance.md)
- [Macro and hourly research architecture](docs/macro-intraday-research-design.md)
- [Implementation and design plan](plan.md)

Community repositories and public URLs are not automatically approved data sources. Their code licenses do not grant rights to redistribute third-party market data, web content or model output.

## Project layout

| Path | Responsibility |
|---|---|
| `configs/default.yaml` | Daily baseline, shadow-mode agents, macro families and hourly research boundaries |
| `src/aylintrade/algorithm.py` | Daily trend/risk-parity allocator and shared simulator |
| `src/aylintrade/macro.py` | Current macro context; explicitly excluded from historical strategy tests |
| `src/aylintrade/intraday.py` | Session-aware hourly shadow-overlay contract |
| `src/aylintrade/validation.py` | Walk-forward split and registered-experiment metadata |
| `src/aylintrade/data/provenance.py` | Browser-safe source registry and governance status |
| `src/aylintrade/paper.py` | Simulated account and settled hypothetical agent ledger |
| `web/` | React/Vite evidence-led dashboard; `site/` is its generated static output |
| `paper/` | Public simulated-account record committed by the daily workflow |
| `docs/` | Methodology, source governance and macro/hourly design |

## GitHub Pages setup

1. Set **Settings → Pages → Source** to **GitHub Actions**.
2. Add `ANTHROPIC_API_KEY` only if commentary shadow runs are desired. Without it the deterministic baseline still works.
3. Run **Actions → Daily → Run workflow** to create a paper record and publish the static artifact.

A change to the public Pages deployment should be reviewed and explicitly approved before merging a workflow that changes it.

## License

Apache-2.0. See [NOTICE](NOTICE) for the projects this builds on.
