# Research notes: what was taken from where

The rebuild started from a review of five repositories and one coding guide. This records what
each contributed, and what was left out and why.

## je-suis-tm/quant-trading

The source of version 1, which re-implemented nine of its strategies under one set of rules.
After costs, 6 of 48 strategy-market tests beat buy & hold, and only one idea held up across
markets: **the MACD trend filter** (long while a fast moving average is above a slow one). It
won on Bitcoin and Ethereum and cut drawdowns everywhere.

* **Taken:** the trend filter, generalised to four horizons and two kinds of vote (price above
  its average, positive return), which is the time-series momentum of the academic literature.
* **Left out:** the pattern strategies (Bollinger W, head-and-shoulders, shooting star,
  Heikin-Ashi, Parabolic SAR), the intraday breakouts (Dual Thrust, London Breakout) and pair
  trading. All lost to holding after costs; the intraday ones lost heavily to trading costs.
  The code stays in git history (version 0.1.0).

## TauricResearch/TradingAgents

A LangGraph framework where language-model agents play the roles of a trading firm.

* **Taken:** the roles (market and news analysts, bull and bear researchers, risk debate,
  portfolio manager), the five-tier rating scale, two model tiers (a stronger model for the
  final decision), structured output for the decision, the rule that an unreadable decision is
  flagged rather than read as Hold, and the memory of settled past decisions fed back to the
  manager.
* **Changed:** in TradingAgents the agents *make* the trading decision. Here the tested
  algorithm decides and the agents can only trim it, because the agents cannot be backtested
  honestly (the model knows how history turned out). Four analysts became two (fundamentals and
  social sentiment do not apply to ETFs and coins), and LangGraph became plain function calls on
  the Anthropic SDK: the flow is linear, so a graph library adds a dependency without adding
  behaviour.

## Superior-Trade/trading-terminal

A Next.js terminal where an agent turns chart drawings into Freqtrade strategies.

* **Taken:** its premise that *no model gets a vote on whether its own output is safe*. The
  guard on the agents' decisions is deterministic code with a hard cap, and every generated
  decision is logged with what happened next (their `strategy_log`, our `decisions.csv`).
  Also its "prove it trades" check, which became the stale-data refusal in the daily run.
* **Left out:** the exchange connection, drawing tools and live order routing. You chose
  research, daily signals and paper trading, not real orders.

## EliteQuant/EliteQuant and academic/awesome-datascience

Both are curated lists of links, with no code to adapt.

* **Taken from EliteQuant's pointers:** walk-forward thinking (the sub-period stress tests) and
  pyfolio-style reporting (Sharpe, drawdown, turnover, calendar years) on the dashboard.
* **awesome-datascience** is general data science; its trading entries (ML crypto bots
  claiming 70–85% accuracy) were not used: claims of that kind rarely survive costs and
  look-ahead checks.

## DietrichGebert/ponytail (coding style)

A coding guide for "the smallest change that fully solves the task". Applied as:

* Delete before adding: the ten-strategy engine, intraday and pair code, PNG charts and the
  statsmodels dependency were removed. The rebuild added about 1,700 lines of Python, tests
  included, and removed about 2,300. The data layer and metrics, which worked, were kept as
  they were.
* No new dependencies for a few lines: the dashboard draws its charts in plain SVG, the agents
  call the Anthropic SDK directly, and the Anthropic SDK is optional (`.[agents]`).
* New logic ships with a check: tests for look-ahead, the guard, the paper account, the study
  and the command line, all offline.
