# AylinTrade improvement batch — implementation and design plan

## Product decision

AylinTrade will remain a **long-only, non-executing research and simulated paper-trading system**. It will not connect to a broker, transmit orders, use leverage or short selling, or portray historical research as a forecast or personalized advice.

The initial improvement branch will be based on `rebuild/aylin-trend`, not `main`, so it extends the existing PR #2 rebuild without mixing it with the legacy multi-strategy engine. The working name is `improvement/macro-intraday-research`.

The product will optimize for three complementary outcomes rather than one fitted objective:

1. **Risk-adjusted return and drawdown control** remain the primary evaluation lens.
2. **Raw return subject to drawdown** is shown as a separate, explicit trade-off.
3. **Comparable objective variants** are displayed beside the baseline rather than silently selecting the strongest historical result.

The existing daily portfolio stays the only paper-account allocator in the first release. Macro and hourly work begin as separately measured research layers; they do not alter daily weights until their data and out-of-sample protocol are accepted.

## What remains intact

The current branch already contains valuable controls that should not be diluted:

- Eight-market daily portfolio: SPY, QQQ, IWM, EFA, GLD, TLT, BTC and ETH.
- Long-only, no-leverage allocation with trend score, inverse-volatility sizing, covariance volatility target and rebalance band.
- Drift-aware simulator shared by backtest and paper account.
- Explicit ETF/crypto cost assumptions and matched benchmark accounting.
- Causal tests for the daily signal, deterministic LLM guard, stale-data refusal and paper-account ledger.
- An honest baseline statement: the reported increment above always-invested risk parity is small and may be noise.

The current results remain labeled as **author-reported historical simulations** until a pinned-data reproduction is completed. Agent output remains outside historical performance results.

## Functional design

### 1. Portfolio home — calm summary before density

The first screen answers four questions without scrolling through a wall of tables:

- **What is the current paper portfolio posture?** Equity, gross exposure, cash, realized/target volatility, latest paper return and data freshness.
- **What changed today?** Target versus held weight, rebalance reason, costs, and whether any proposed research overlay was active, shadow-only or unavailable.
- **What risks are visible now?** Correlation concentration, trend breadth, upcoming macro-event window, data-quality status and the confidence boundary around every result.
- **What is the evidence?** A compact statement of the simulation period, as-of date, data vintage, baseline, cost convention and the plain-language trade-off against SPY.

A persistent paper-only label appears in the header and alongside any historical statistic. The home screen never uses “buy”, “sell”, certainty scores, or performance promises.

### 2. Daily allocator — preserve the auditable core

The existing daily trend/risk-parity model is presented as a **baseline model**, with an expandable audit trail for each market:

- Last close, one-month return, annualized volatility and distance from one-year high.
- Eight daily trend votes grouped by 1/3/6/12-month horizon.
- Algorithm target, actual held weight, cash residual and rebalance-band explanation.
- Cost, source, bar timestamp, retrieval timestamp, coverage state and data version.
- Matched comparison with SPY, equal-weight buy-and-hold and always-invested risk parity.

The interface will make the difference between risk-adjusted performance and raw return explicit rather than treating Sharpe as a substitute for return.

### 3. Macro regime layer — factual, release-aware and initially non-executing

The recommended macro families are:

| Family | Initial measures | Frequency / availability rule | Initial role |
|---|---|---|---|
| Rates and curve | 2-year, 10-year, 10Y–2Y slope, real yield where licensed | Daily close; use date/time available to the strategy | Regime context and rate-sensitivity display |
| Inflation | Headline/core CPI, 3- and 12-month change, release/surprise metadata | Monthly; available only after the timestamped release | Event calendar and inflation regime |
| Labor and growth | Payrolls, unemployment, initial claims, industrial production | Mixed weekly/monthly; release-time aligned | Growth regime and event risk |
| Credit and liquidity | Investment-grade/high-yield spread proxies, financial-conditions proxy | Daily/weekly as documented | Stress and cross-asset correlation context |
| Dollar and FX | Broad USD index / USD trend | Daily close | Global-risk and commodity context |
| Volatility | VIX or a licensed equivalent plus realized portfolio volatility | Daily close | Volatility/regime context; never a standalone forecast |

Every observation receives `observed_period`, `released_at`, `retrieved_at`, `available_at`, `source`, `vintage_id`, `units`, and `status`. A backtest can use an observation only when `available_at` is at or before its decision timestamp. Current revised macro data must never be backfilled into a historical decision date.

**Primary macro protocol:** use official release calendars and ALFRED/FRED vintage data where allowed. ALFRED records the real-time periods in which values were originally released and later revised; the BLS and New York Fed calendars provide release dates and times. The research harness will keep release-time metadata even when a series is first displayed only as context. [1] [2] [3] [4]

The first macro display is a transparent regime map, not a fitted prediction model. A fixed, documented ruleset can label conditions such as `inflation pressure`, `growth cooling`, `curve stress`, `credit stress`, `USD strength`, or `volatility stress`; it will also display the underlying values and source timestamps. Any future macro allocation tilt must be a separately registered experiment with its own baseline, holdout result, and cash/cost treatment.

### 4. Hourly research layer — a distinct overlay, never mixed by accident

The hourly design is deliberately separate from daily sizing because the instruments have incompatible trading calendars:

- US ETFs use regular-session rules, with no forward fill across closed hours.
- Futures require a specified contract, roll procedure, session calendar and timezone.
- Crypto runs 24/7 and must retain UTC bar-close semantics.

The hourly system has four states: `unavailable`, `quarantined`, `shadow`, and `eligible`. It is **shadow-only** in the first release: it calculates and logs a candidate intraday risk/entry-timing overlay, but does not change the paper account.

For each eligible market, the overlay uses a small, predeclared set of causal features:

- 4/12/24/72-hour trailing return and price-versus-moving-average trend.
- 24/168-hour realized volatility and volatility percentile.
- Range expansion, gap/session state, liquidity/volume quality where a trustworthy source provides volume.
- Cross-market risk context only from bars closed before the decision timestamp.

The candidate output is deliberately modest: `risk-on`, `neutral`, `risk-off`, or `data-invalid`, plus a proposed **next-session timing state**. It never becomes a price target, a standalone trade instruction, a leverage instruction, or a hidden multiplier on the daily allocator.

Current source constraints are surfaced rather than hidden:

- `finom/static-klines` can provide BTC/ETH hourly candles from 2022 onward but is an experimental cache with revision and rights caveats; it remains quarantined until snapshot, completeness and rights checks pass.
- The report's CME dataset is too short, stale and lacks a documented continuous-roll methodology; it is display/research-only and cannot support a credible futures allocator.
- The available structured Yahoo chart interface supports 60-minute data but has a limited history range; it is useful for current display validation, not for a multi-decade intraday backtest.

No hourly source is approved merely because it is public. The application will require source rights, a pinned snapshot/version, coverage report, session specification, bar-close semantics, duplicate/gap/OHLC validation, and sufficient predeclared training/test history before it can move beyond quarantine.

### 5. Agent analysis — evidence ledger, commentary first

The six-role committee becomes an **audited research commentary system** in the first release. It may summarize source-backed event, macro, correlation and data-quality risks, but it cannot alter weights.

The current deterministic guard remains in code for a future prospective experiment, but operates in shadow mode:

- Every suggested cut is logged as a hypothetical counterfactual with input evidence, model/version, prompt configuration, source citations, timestamp and deterministic guard outcome.
- The daily allocator remains unchanged (`keep = 1`) during shadow evaluation.
- Each suggested intervention is settled after a predeclared horizon; the dashboard shows sample count, net hypothetical effect, confidence caveat and the full list of failures/no-op days.
- Advancement to a capped-trim experiment requires a written, pre-specified gate after sufficient forward observations. It is not triggered by a favorable short run.

Web search and LLM output are allowed only as current-context/source-discovery aids. They are excluded from historical features and backtests unless a point-in-time archive and source rights have been demonstrated. No agent consensus is shown as authoritative without the underlying cited evidence.

### 6. Research and validation library

The site will include a Research workspace that separates **baseline**, **registered candidate**, **validated holdout**, and **rejected/retired** analyses. Every view exposes its evidence bundle:

- Universe and point-in-time membership policy.
- Data source, licence/right status, snapshot hash, source revision and coverage report.
- Decision timestamp, execution timestamp, market session and timezone.
- Feature definitions, missing-data policy, cost/slippage/cash model and code commit.
- Train/validation/test windows, walk-forward folds, embargo/purge rule and parameter grid.
- Benchmarks, results, drawdowns, turnover, factor/regime exposure and failures.

The validation design uses expanding-window walk-forward evaluation. All selection occurs only inside the historical training window; a validation window selects among predeclared variants; a held-out window is untouched until the end. Time-series folds include an embargo around labels/holding periods. Cost multipliers, delayed fills, no-crypto, regime slices and data-coverage failures are reported as first-class results. The site shows uncertainty and negative findings rather than only the best row.

## Technical architecture

### Static delivery model

The system remains a static site so it can be deployed both to GitHub Pages and to the Manus preview without a database, a broker credential, or a server. Python builds versioned static JSON artifacts; a TypeScript/React frontend renders them.

```
source data + metadata
   └─ Python adapters / validators
       ├─ daily study and paper ledger
       ├─ macro vintage + release-calendar store
       ├─ hourly bars + session metadata
       ├─ research-run validator and evidence bundle
       └─ static data builder
            └─ site/public/data/*.json
                    └─ React/Vite static dashboard
                         ├─ Manus preview
                         └─ GitHub Pages artifact
```

The browser never holds external market-data credentials. It reads only already-sanitized static artifacts produced by the research build. Raw market data remains outside the published bundle unless rights explicitly permit display.

### Python modules and data contracts

| Path | Responsibility |
|---|---|
| `src/aylintrade/data/provenance.py` | Source registry, rights/coverage status, snapshot hash, retrieval metadata and manifest validation. |
| `src/aylintrade/data/macro.py` | Macro observation schema, release calendar adapter, vintage-aware cache and `available_at` checks. |
| `src/aylintrade/intraday.py` | Hourly bar alignment, per-instrument session metadata, causal features and shadow-overlay ledger. |
| `src/aylintrade/regimes.py` | Fixed transparent macro-regime labels; no fitted allocation impact in the first release. |
| `src/aylintrade/validation.py` | Walk-forward split construction, embargo rules, coverage gates, results manifest and evidence-bundle writer. |
| `src/aylintrade/research.py` | Existing baseline study plus registered experiment runner; never silently selects the highest historical metric. |
| `src/aylintrade/site.py` | Versioned site contract builder that exports `study`, `paper`, `macro`, `intraday`, `agents`, `validation` and `provenance` sections. |
| `configs/default.yaml` | Existing daily strategy plus explicit `macro`, `intraday`, `agents.mode`, source-status and experiment registrations. |
| `tests/` | Causality, session/DST, release-lag, data-quality, risk limits, evidence-bundle and rendering-contract tests. |

Data contracts will use a `schema_version`, a `generated_at` timestamp, a user-facing `as_of` timestamp, and a separate `data_vintage` / `coverage_status` object. Missing, stale, quarantined or unavailable inputs produce a visible state; they never become zero, an assumed neutral signal, or a silently forward-filled market bar.

### Frontend structure

| Path | Responsibility |
|---|---|
| `site/src/app/` | Static route shell, global state, device theme, reduced-motion support and data-loader error boundary. |
| `site/src/features/posture/` | Current paper posture and daily allocator evidence. |
| `site/src/features/macro/` | Release-aware macro regime map, release clock and provenance drawer. |
| `site/src/features/intraday/` | Hourly shadow-overlay timeline, session badges and source-quality states. |
| `site/src/features/research/` | Walk-forward results, stress tests, objective comparison, evidence bundle and failure table. |
| `site/src/features/agents/` | Citation-led commentary, shadow ledger and model/run metadata. |
| `site/src/components/charts/` | Accessible interactive charts, legends, tooltip, keyboard focus, series toggles and export-ready table equivalents. |
| `site/public/manus-routes.json` | Route manifest for `/`, `/methodology`, `/research`, `/data`, and `/paper`. |

The visual layer is a normal static build. It will provide safe empty and error states for absent data, escape all model-written text, allow only `http`/`https` source links, and maintain a table/formatted-text alternative to every visual chart.

## Design direction

### Design movement

**Evidence-led editorial terminal.** The visual system combines an institutional research terminal’s precision, an editorial memo’s hierarchy and a calm personal dashboard’s low cognitive load. It avoids the current “every block is a card” presentation.

### Core principles

1. **Evidence before assertion:** every result reveals its as-of time, source/vintage, assumption and limitation.
2. **Calm before dense:** one clear posture statement leads; detailed diagnostics appear on demand.
3. **Interaction reveals logic:** hover, focus and drill-down explain a number’s construction rather than add decoration.
4. **Uncertainty is part of the interface:** missing, quarantined and unvalidated are designed states, not errors hidden from the reader.

### Color philosophy

A graphite-and-paper base makes the page feel like a research instrument rather than a retail trading app. A saturated **atlas blue** (`#2A78D6`) is the single signature brand color and marks verified baseline evidence. Warm rust signals drawdown/risk, mineral teal marks validated research context, and muted gold denotes warnings/quarantine. The existing colour-vision-tested portfolio palette is retained for series continuity.

### Layout paradigm

A continuous **evidence spine** replaces a grid of equal cards. At wide sizes, a narrow left rail shows portfolio posture and data freshness while the main column flows from “now” to “why” to “what was tested.” At phone width, the rail becomes a concise sticky status strip and detailed tables use contained horizontal scroll.

### Signature elements

- A compact **A/T compass mark** constructed from an allocation line and a timestamp dot, used in the wordmark and source-status badges.
- **Evidence ribbons** beneath each material chart: `as of`, `vintage`, `source`, `assumption`, and `status` in a single readable line.
- **Regime bands** that extend through time-series charts to show macro/event windows without implying causation.

### Interaction and animation

Interactions favor inspection: chart crosshairs, visible legends, keyboard-operable series toggles, tooltip values and a one-click “show evidence” drawer. The macro release clock expands into timestamped source metadata. Motion is limited to short 160–220 ms opacity/position transitions; respects `prefers-reduced-motion`; never animates prices or imitates a live trading terminal.

### Typography

Use **IBM Plex Sans** for explanatory editorial text and **IBM Plex Mono** for timestamps, prices and metrics. A compact display treatment for headings comes from the sans family’s weight/spacing rather than a decorative finance font. Numbers use tabular figures and labels retain enough contrast for light/dark themes.

### Brand system

- **Essence:** A transparent multi-frequency market-research notebook for people who want to inspect evidence before trusting a model.
- **Personality:** rigorous, composed, candid.
- **Voice:** short, factual and never promotional. Examples: “The daily allocator is unchanged; the hourly overlay is shadow-only.” and “This macro observation was unavailable at the historical decision time and was excluded.”
- **Wordmark:** `AylinTrade` with an A/T compass mark; “Trade” is not visually associated with execution.

## Delivery and branching workflow

1. Start from the open `rebuild/aylin-trend` branch in a new `improvement/macro-intraday-research` branch.
2. Preserve the existing GitHub remote for the user’s public repository; use a separate managed project history for Manus preview checkpoints when appropriate. Do not force-push or rewrite PR #2.
3. Build a static Vite output that works in Manus Preview and in the existing GitHub Pages action.
4. Update the GitHub workflow only after the build, source approvals and test suite are passing.
5. Open a reviewable PR against `rebuild/aylin-trend`; keep public publication separate from branch/PR creation.
6. Ask for final confirmation before enabling or changing the public GitHub Pages deployment.

## Explicit non-goals for this batch

- No real broker/exchange integration, execution endpoint, portfolio credential, payment flow, leverage or short sale.
- No automatic selection of a “best” model from backtest results.
- No macro/news/LLM inputs in a historical result unless point-in-time availability and rights are demonstrated.
- No continuous-futures allocation until a licensed, documented continuous-contract data source and roll methodology pass validation.
- No agent-led sizing or trade recommendation in the initial release.

## Source basis

The plan incorporates the report’s repositories, data sources and academic references, plus a source-governance audit. It corrects two citation identifiers in the report: the verified *Time Series Momentum* DOI is `10.1016/j.jfineco.2011.11.003`, and the verified *Volatility-Managed Portfolios* DOI is `10.1111/jofi.12513`. The accompanying [source-governance memo](docs/source-governance.md) records what is retained, quarantined and excluded.

[1]: https://fred.stlouisfed.org/docs/api/fred/alfred.html "ALFRED archival vintage-data documentation"
[2]: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html "FRED real-time-period documentation"
[3]: https://www.bls.gov/schedule/news_release/cpi.htm "U.S. Bureau of Labor Statistics CPI release schedule"
[4]: https://www.newyorkfed.org/research/calendars/nationalecon_cal "New York Fed economic indicators calendar"
