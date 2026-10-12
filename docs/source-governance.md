# AylinTrade source-governance memorandum

AylinTrade should treat every repository, paper, data feed and model output in its technical report as a governed research input—not as proof that a strategy is accurate or suitable for use. The product remains long-only, paper-only and non-executing.

## Decisions from the source audit

### Retain as research foundations

| Source family | What is retained | Conditions |
|---|---|---|
| AylinTrade PR #2 | Daily long-only allocator, no-leverage ceiling, drift-aware accounting, causal signal tests, matched benchmarks and paper ledger | Report its performance as an author-reported historical simulation until independently reproduced from pinned data. Keep agent results separate from historical return claims. |
| Time-series momentum literature | Trailing own-return trend as a hypothesis; risk normalization and explicit transaction-cost sensitivity | Academic strategies are commonly long/short. A long-only/cash translation is a new, separately tested rule. Use lagged inputs and next-tradable-bar execution. |
| Risk-parity and volatility-managed literature | Inverse trailing-volatility baseline, covariance-aware risk measurement, capped exposure experiments | Do not use full-sample or ex-post volatility scaling in a live-like test. Include cash return, financing/cost assumptions and walk-forward evaluation. |
| TradingAgents | Evidence-led analyst roles, opposing views, cited sources, uncertainty and run records | Use the structure for commentary and research reporting only. Do not adopt agent trade decisions, sizing or unverified historical backtests. |
| Superior-Trade | Deterministic admission gates, a model cannot validate itself, audit logs and stale-data checks | Keep all live execution, exchange credentials and deployment controls out of scope. A passing validator is not evidence of profitability. |
| Ponytail | Smallest complete change, trace callers/data/tests, preserve validation and disclose skipped checks | Minimal code never replaces domain controls, provenance or risk disclosures. |

### Keep in quarantine or use only as discovery

| Source | Status | Why |
|---|---|---|
| Johnbrick123/sp500-data | **Quarantine for historical claims** | The project itself reports material coverage/survivorship limitations in historical membership data. Its live release is mutable and public access does not settle data-rights or redistribution questions. |
| finom/static-klines | **Quarantine for historical claims** | It is an experimental cache that can lag or differ from revised Binance history; repository metadata does not establish a data license. Use only for clearly labeled exploratory ingestion after snapshot and quality checks. |
| axb0306/cme-futures-ohlc | **Quarantine** | It has short/stale coverage, no documented continuous-roll methodology, unclear redistribution rights and contract metadata gaps. It cannot support a credible futures allocation. |
| EliteQuant and awesome-datascience | **Discovery only** | They are curated resource lists, not validation of linked tools, data or strategy claims. Each downstream source requires independent intake. |
| Anthropic web search | **Current source discovery only** | Search results are mutable and are not a point-in-time historical archive. Record query, retrieval time, sources, tool version and errors; verify material claims at the primary source. |
| Anthropic model documentation | **Tooling reference only** | Model capability and pricing pages are vendor documentation, not market data and not evidence of predictive value. Record date and model identifiers if cited. |

## Required source register

Before a source can appear in a public simulation or chart, add a source-register record containing:

- Canonical URL, owner/provider, source type and intended purpose.
- Rights and display/retention status; an explicit `unknown`, `quarantined`, `approved-research`, or `prohibited` state.
- Data version/commit, snapshot hash, retrieval timestamp and coverage interval.
- Timestamp semantics, timezone, bar-close or publication availability, revision/vintage policy and corporate-action treatment.
- Instrument/universe identity rules, missing-data policy, quality checks and known biases.
- Review owner, approval date and unresolved limitations.

Public code licenses do not license third-party market data, data redistribution, web content or model-provider services. Repository code can be referenced or reused only with its applicable Apache-2.0/MIT notices retained; that does not resolve upstream data rights.

## Required evidence bundle for every result

Every public backtest, macro view or candidate overlay must link to an immutable evidence bundle containing:

1. The data/source register entries and snapshot hashes.
2. As-of cutoff, observation `available_at` timestamps, timezone and session rules.
3. Eligible universe and membership rules at the decision date.
4. Code commit, configuration, feature version and parameter choices.
5. Fill timing, transaction costs, slippage/impact assumption and cash-return treatment.
6. Training/validation/holdout windows, walk-forward fold boundaries and embargo rule.
7. Benchmarks, results, drawdowns, turnover, coverage results, rejected variants and known limitations.
8. Human-review and correction/version history.

A missing timestamp, rights status, coverage check or validation report is not neutral. It blocks the result or labels it `UNVERIFIED`; it is never silently treated as an all-clear.

## Timing rules for macro and intraday data

- Macro observations carry `observed_period`, `released_at`, `retrieved_at`, `available_at` and `vintage_id`. They enter a historical calculation only after the known release timestamp.
- ALFRED/FRED real-time periods are the preferred mechanism for revised U.S. macro series; BLS and New York Fed calendars support release-time metadata. [1] [2] [3] [4]
- Hourly bars use UTC internally, retain source/session metadata, and are usable only after their close time. ETF, futures and crypto calendars are never forward-filled into one artificial hourly grid.
- Signals are formed at decision time and filled no earlier than the next eligible market bar. The test suite mutates all future macro observations and all future bars to prove earlier outputs are unchanged.

## Research conclusion

The report’s strongest contribution is a transparent daily baseline with risk controls, not a demonstrably large alpha. The most credible improvement is therefore a governed research platform that exposes uncertainty, rejects weak data, and tests macro/intraday/LLM ideas outside the baseline before they are allowed to affect paper weights.

## References

[1]: https://fred.stlouisfed.org/docs/api/fred/alfred.html "ALFRED archival vintage-data documentation"
[2]: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html "FRED real-time-period documentation"
[3]: https://www.bls.gov/schedule/news_release/cpi.htm "U.S. Bureau of Labor Statistics CPI release schedule"
[4]: https://www.newyorkfed.org/research/calendars/nationalecon_cal "New York Fed economic indicators calendar"
[5]: https://github.com/aylinunel/aylintrade/pull/2 "AylinTrade PR #2"
[6]: https://doi.org/10.1016/j.jfineco.2011.11.003 "Time Series Momentum"
[7]: https://doi.org/10.3905/jpm.2017.44.1.015 "A Century of Evidence on Trend-Following Investing"
[8]: https://doi.org/10.2469/faj.v68.n1.1 "Leverage Aversion and Risk Parity"
[9]: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513 "Volatility-Managed Portfolios"
[10]: https://github.com/TauricResearch/TradingAgents "TradingAgents"
[11]: https://github.com/Superior-Trade/trading-terminal "Superior-Trade trading terminal"
[12]: https://github.com/Johnbrick123/sp500-data "Johnbrick123 sp500-data"
[13]: https://github.com/finom/static-klines "finom static-klines"
[14]: https://github.com/axb0306/cme-futures-ohlc "axb0306 CME futures OHLC"
