# AylinTrade

**A multi-market trend portfolio, reviewed every day by a committee of Claude agents, paper
traded in public, with a live dashboard.**

[![CI](https://github.com/aylinunel/aylintrade/actions/workflows/ci.yml/badge.svg)](https://github.com/aylinunel/aylintrade/actions/workflows/ci.yml)
[![Daily](https://github.com/aylinunel/aylintrade/actions/workflows/daily.yml/badge.svg)](https://github.com/aylinunel/aylintrade/actions/workflows/daily.yml)
![Python](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

**Dashboard:** https://aylinunel.github.io/aylintrade/ (after the one-time setup below)

> Research and paper trading with simulated money. Not financial advice.

## What it does

Every weekday after the US close, a GitHub Action:

1. downloads fresh prices for eight markets: US stocks (SPY, QQQ, IWM), developed-market stocks
   (EFA), gold (GLD), long US Treasuries (TLT), Bitcoin and Ethereum;
2. **runs the algorithm**, which decides how much of each to hold;
3. **convenes the agent committee** (market analyst, news analyst with web search, bull and
   bear researchers, risk manager, portfolio manager), which may trim positions it has specific
   reasons to distrust;
4. **trades the paper account** ($100,000 of simulated money) and commits the record to `paper/`;
5. re-runs the 20-year backtest and **publishes the dashboard**.

## The algorithm

Four steps, all in [`algorithm.py`](src/aylintrade/algorithm.py):

1. **Trend:** eight votes per market (price above its 1, 3, 6 and 12-month average; positive
   return over each). A quarter of each position is always held; the votes decide the rest.
2. **Risk parity:** size each market by 1 / its volatility, so bonds and Bitcoin carry similar
   risk.
3. **Volatility target:** scale the whole portfolio to about 10% expected volatility a year,
   never more than 100% invested.
4. **Rebalance band:** skip trades under 3% of the account, to save costs.

## Results (2006 to October 2026, after trading costs)

| Portfolio | Per year | Volatility | Sharpe | Worst drop |
|---|---:|---:|---:|---:|
| **Aylin trend portfolio** | **8.4%** | **9.5%** | **0.89** | **−22%** |
| S&P 500 (SPY) buy & hold | 11.0% | 19.0% | 0.64 | −55% |
| Equal-weight buy & hold | 13.2% | 17.6% | 0.79 | −40% |
| Risk parity, always invested | 8.4% | 9.9% | 0.87 | −24% |

Read honestly:

* It earns **less per year than the S&P 500**, with **half the volatility** and **less than
  half the worst loss**. The goal is a portfolio you can stick with, not one that beats the
  index on raw return.
* **Most of the improvement comes from diversification and risk-based sizing.** The always-
  invested risk-parity benchmark scores almost the same; the trend tilt adds a little, mostly in
  long bear markets (2008: −6% against −15% for risk parity and −37% for SPY). It did not help
  in 2022, when stocks and bonds fell together (−17%).
* It holds up under 2–3× trading costs, other settings, without crypto, and in each third of
  the period. Every variant tried while designing it is in the stress-test table, losers
  included: [`results/latest/summary.md`](results/latest/summary.md).

The agent committee is **not** in these numbers: a language model knows how history turned
out, so it cannot be backtested honestly. Its effect is measured forward in the paper account,
and shown on the dashboard.

## Quick start

```bash
git clone https://github.com/aylinunel/aylintrade && cd aylintrade
pip install -e ".[agents]"      # Python 3.11+

aylintrade fetch                # download prices into data/ (~200 MB, cached)
aylintrade backtest             # the 20-year study -> results/latest/
aylintrade daily                # one paper trading day, as the GitHub Action does
make preview                    # dashboard at http://localhost:8000
```

`aylintrade daily` uses the agents when `ANTHROPIC_API_KEY` is set and trades on the algorithm
alone when it is not (or with `--no-agents`).

## One-time setup on GitHub

1. **Settings → Pages → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions → New repository secret:**
   `ANTHROPIC_API_KEY` (from https://console.anthropic.com). Without it the account trades on
   the algorithm alone. The committee costs a few dollars a month.
3. **Actions → Daily → Run workflow** to start the paper account today. After that it runs by
   itself at 06:17 UTC, Tuesday to Saturday.

## The agents' limits

From [`agents.py`](src/aylintrade/agents.py), enforced by plain code after the models answer:

* They can only **reduce** a position, by at most **50%** (`agents.max_cut`). Never open, add
  or short.
* A missing or unreadable decision keeps the algorithm's weight.
* If the API fails, the algorithm trades alone that day.
* Every decision is logged in `paper/decisions.csv` and scored five trading days later; the
  portfolio manager reads those scores before each meeting.

## Project layout

| Path | What it is |
|---|---|
| `configs/default.yaml` | Markets, algorithm settings, agent models and limits, paper capital |
| `src/aylintrade/algorithm.py` | The four steps, and the simulator shared by backtest and paper account |
| `src/aylintrade/research.py` | Backtest, benchmarks, per-market tests, stress tests |
| `src/aylintrade/agents.py` | The committee and its guard |
| `src/aylintrade/paper.py` | The paper account |
| `src/aylintrade/data/` | Price sources (free datasets on GitHub, no keys) and the local cache |
| `site/index.html` | The dashboard (one file, plain SVG charts); `aylintrade site` builds its data |
| `paper/` | The paper account's history, committed daily |
| `docs/methodology.md` | Every rule, and the known limitations |
| `docs/research-notes.md` | What was taken from each reference project, and why |

## Development

```bash
pip install -e ".[dev]"
make lint test     # ruff, mypy, and offline tests (the agents run against a fake client)
```

## Data

| Markets | Source | From |
|---|---|---|
| SPY, QQQ, IWM, EFA, GLD, TLT | [Johnbrick123/sp500-data](https://github.com/Johnbrick123/sp500-data), dividend-adjusted | 1999–2004, by fund |
| BTC, ETH | [finom/static-klines](https://github.com/finom/static-klines) (Binance) | 2017 |
| ES, GC, CL futures | [axb0306/cme-futures-ohlc](https://github.com/axb0306/cme-futures-ohlc) | 2025; too short to test yet |

## License

Apache-2.0. See [NOTICE](NOTICE) for the projects this builds on.
