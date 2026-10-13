# Quant Agent Studio

The studio adds a runnable research workflow to `quantbt`. It generates a bounded set of
registered strategy specifications, evaluates causal signals, runs independent reviews and
shows the evidence in a local dashboard. Its paper ledger replays historical **spot** trades.
It does not connect to a broker, send orders or maintain a live account.

## Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
quantbt studio
```

Open **http://127.0.0.1:8765** and press **Run research**. The default uses generated prices
and four rule-based reviewer roles, so it needs no API keys or network access. Synthetic results
remain `DEMO ONLY`, regardless of how many reviewers approve.

For the existing GitHub-hosted Binance mirror data:

```bash
quantbt fetch --force -m BTC ETH
quantbt studio --data-dir data
```

Choose **Cached market data** in the dashboard. Completed 1-hour and daily bars are supported.
Four-hour bars are aggregated only from complete sets of four hourly observations. Data
timestamps represent bar open in UTC; incomplete bars are excluded. A run needs at least 600
completed bars. Old caches without provenance can be researched but cannot produce eligible
proposals; refetch with this version to record source metadata. Provenance is an auditable local
record, not cryptographic proof of a venue's data. Never relabel generated data as market data.

Capital, notional and PnL are in **USDT quote units**, not converted EUR. The default paper book
is 5,000 units, with 0.5% planned entry risk, a 2.5% price stop and a 50% exposure ceiling.
Costs are 0.1% per side plus 0.05% adverse fill slippage. These are editable research assumptions,
not quotes for a particular exchange. There is no minimum-lot or exchange-precision adapter yet.

## What the nodes do

| Node | Work and authority |
| --- | --- |
| Data steward | Rejects invalid, missing or non-positive bars; records hash, interval, source and freshness |
| Strategy deviser | Produces nine bounded registered templates and parameter variants |
| Validation | Checks prefix consistency and future perturbation; ranks three chronological validation windows |
| Quant reviewer | Assesses sample count, held-out results, baseline and doubled-cost stress |
| Market reviewer | Assesses the current positive signal and realized volatility |
| Event reviewer | Uses dated event context; abstains if context is absent or rule mode cannot interpret it |
| Risk reviewer | Assesses measured drawdown and planned sizing |
| Portfolio gate | Applies three-approval policy with mandatory quant/risk votes and independent numerical vetoes |
| Paper ledger | Reconciles historical next-open fills, stop/gap exits, costs, cash and closed-trade PnL |

Select a node to inspect its saved evidence. The timeline records actual backend events. The
depth view tilts the same dependency graph; it does not change or imply new relationships.
Green means an agent completed its work, not that it approved. Review cards show the verdict.
Exports contain the immutable review packet, numerical results, selected parameters and
dataset references. They never include session tokens or model credentials.

## Validation and decision rules

The first half of the observations supplies indicator history. The next 30% is divided into
three chronological validation windows. Each template is scored by mean Sharpe plus twice
mean drawdown. Templates with fewer than the configured minimum of validation trades cannot
win selection while a sufficiently sampled alternative exists. If none qualifies, the best
score is still studied but cannot pass the quant gate. The best template is frozen before the last 20% is evaluated. This is a
bounded parameter-selection experiment; it is not a trained ML model or a statistical guarantee.
Only the selected template gets a final test result. Repeating a run does not create a new,
independent test sample, and repeatedly refining against the same test window overfits it.

The spot replay treats a positive strategy signal as an entry condition under uniform risk
sizing. It does not reproduce Heikin-Ashi's fractional scaling, short signals or pair allocations.
A close-derived signal first becomes executable at the next bar's open. Stops are based on the
unadjusted entry reference, fills pay adverse slippage and fees, and gap stops fill at the worse
available open. Evaluation ends flat and charges the final exit fee. Completed trades reconcile
to final cash. The comparator is a **same-risk long-and-stop baseline**, not unrestricted buy
and hold. The existing `quantbt run` research engine is kept separately for its original methods.

A quant pass requires the configured minimum of 10 completed test trades, positive test and
cost-stressed return, better return than that baseline, and positive returns in at least two
validation windows. Risk must also meet the drawdown cap. A proposal needs at least three
distinct approvals across four roles, including quant and risk, and every hard check must pass.
Synthetic input, unrecorded source provenance, stale data, absent positive signal and an
indicative notional below 10 quote units block eligibility. The 10-trade cutoff is an initial
screening heuristic; it is not enough to prove an edge or calibrate probability of profit.

Proposal prices and quantities are references. They require a new executable price and another
risk check before any future execution adapter could use them. A displayed 2R target is
illustrative: this version's replay exits by signal or stop, not by that target.

## Optional language-model reviewers

```bash
export QUANTBT_LLM_BASE_URL=https://api.openai.com/v1
export QUANTBT_LLM_MODEL=your_supported_chat_completion_model
export QUANTBT_LLM_API_KEY=your_key
quantbt studio --reviewer llm
```

Use an HTTPS OpenAI-compatible Chat Completions endpoint that supports JSON-object responses
and `max_tokens`. Provider/model compatibility and paid inference need to be checked with your
chosen service; no model call is made in the default mode. Review calls run in at most four
threads, with 500 requested output tokens, a 25-second socket timeout, no retries and a 64 KiB
response cap. Redirects are refused so Authorization is not forwarded to another provider.

Each reviewer sees the same frozen packet before any peer verdict. Schema and evidence IDs
are checked, but these checks cannot certify every sentence as true. Invalid responses and
provider errors become abstentions. The deterministic eligibility checks remain authoritative.
Shared models and data can produce correlated errors; four roles are not four independent
statistical observations. Agent decision quality is not backtested in this version.

Optional events live in `data/BTC_news.json` or `data/ETH_news.json`:

```json
[
  {
    "title": "An archived event headline",
    "source_url": "https://example.com/original-publication",
    "published_at": "2026-10-12T08:00:00Z",
    "known_at": "2026-10-12T08:03:00Z"
  }
]
```

Both times must have explicit zones and be no later than the analysis cutoff. The last 20
eligible events from 30 days are stored in the review packet. `known_at` is when the information
became available, not an event's economic reference date. News is untrusted text and is never
executed. Rule mode abstains instead of pretending to interpret it.

## Capacity and operational limits

This is a **single-user local research workbench**, not a public trading service. One research
job runs at a time; another request gets HTTP 409. The server bounds simultaneous connections
to 16, request bodies to 16 KiB and research frames to 200,000 rows. The API returns only the
latest 30 runs, event pages of 500 rows and the latest 100 replay fills. SQLite uses WAL,
transactional writes, per-operation connections and an event cursor index. A process-level
database lock prevents a second server from recovering the first one's active runs.

On restart, abandoned runs and active nodes become failed, rather than looking successful.
There is no arbitrary generated-Python execution and no external queue or UI dependency.
The static UI assets are packaged in the Python wheel. SQLite history accumulates on disk:
archive completed databases when retention becomes material. Larger shared deployments need
an authenticated API, durable worker ownership and a central database before exposure to others.

The server binds only to loopback, rejects unknown Host headers and protects writes with a
session token plus same-origin checks. Do not expose it through a public proxy. API keys stay
in server environment variables; `.env` files are ignored by Git.

## Included and deferred methods

The original CLI keeps Bollinger W, SMA crossover, Parabolic SAR, Heikin-Ashi, RSI patterns,
Shooting Star, Dual Thrust, London Breakout and pairs. The registry now also includes true
EMA-based MACD and a positive/rising Awesome Oscillator variant. Pair selection uses correct
Engle–Granger residual inference, fitted hedge quantities and unit gross notional; that is not
a guarantee of market neutrality. Older committed results are legacy snapshots and must be
rerun before quoting them as results of the corrected pair code.

Options/VIX, economic alternative-data studies, graph allocation, reviewer-weight learning,
deep models, reinforcement learning, futures margin/funding/liquidation, live order routing,
exchange-specific precision and portfolio-wide multi-asset optimization remain research
extensions. No placeholder module pretends those are implemented. EliteQuant and
awesome-datascience are catalogs, not engines bundled into this package.

## Engineering sources

The architecture applies ideas from [TradingAgents](https://github.com/TauricResearch/TradingAgents)
and [Superior Trade](https://github.com/Superior-Trade/trading-terminal); it does not clone their
providers, hosted execution backend or fund-moving routes. Quant methods build on the existing
Apache-licensed adaptation of [quant-trading](https://github.com/je-suis-tm/quant-trading).
[EliteQuant](https://github.com/EliteQuant/EliteQuant) and
[awesome-datascience](https://github.com/academic/awesome-datascience) informed the method inventory.
[Ponytail](https://github.com/DietrichGebert/ponytail) informs engineering and review. Its own
benchmark is not evidence of this repository's speed; see [our benchmark](benchmark.md).
