# Methodology

## Common rules

| Rule | Detail |
|---|---|
| Execution timing | A position decided at the close of bar *t* is held over bar *t+1* and earns its close-to-close return. |
| Costs | A fixed fraction of traded notional per side, booked on the bar the new position starts. Flat → long is one side; long → short is two. |
| Intraday strategies | Each round trip is booked on its own day: `side × (exit / entry − 1) − 2 × cost`. |
| Sizing | 100% of capital per strategy; pair trading puts 50% in each leg. |
| Cash and shorts | Idle cash earns 0%. Shorts pay no borrow or funding fee. |
| Benchmark | Buy & hold over exactly the strategy's evaluation window, with the same cost model. |
| Sharpe / Sortino | Mean return over volatility (downside volatility for Sortino), annualised, zero risk-free rate. |
| Annualisation | 252 periods a year for SPY and futures, 365 for crypto. |

## Look-ahead protection

`tests/test_no_lookahead.py` runs every registered strategy:

1. on the full history and on several truncated histories, and checks that every signal the
   truncated run produced is identical;
2. on a history where every price after a given bar is halved, and checks that nothing before
   that bar changes.

A strategy that reads tomorrow's data fails both tests. Any new strategy registered with
`@register` is picked up by these tests automatically.

## Changes from the original scripts

| Strategy | Original | Here | Why |
|---|---|---|---|
| Shooting Star | Confirms with the next day's high and close, but trades on the star day | Trades on the confirming day | Look-ahead |
| Shooting Star | "Small body" compared with abs(mean signed body), which is about 0 | Compared with the mean absolute body | The rule could never fire |
| Dual Thrust | Range includes the current day | Range uses the previous `lookback` days | Look-ahead |
| Dual Thrust | Minute data | Daily bars; when both thresholds break on one day, the worse order is assumed | Free intraday data is limited |
| Bollinger W | Touch tolerance 0.0001 price units | 1% of price | Units only make sense on GBP/USD |
| Bollinger W | Exit when band std < 0.0001 | Exit when band width falls below its 75-bar average | The original exit never fires outside FX |
| RSI H&S | Tolerance 0.2 price units | 1% of price | Units |
| London Breakout | 0.01 price units, minute data | 0.75% of price, hourly bars; the stop is assumed hit before the target within one bar | Units, data |
| Pair trading | Thresholds at z(start) ± std(residual), on an already normalised z | z = ±1 | Mixed units; this is the documented intent |

## Known limitations

* **Pair trading's cointegration test is optimistic.** Like the original, it applies ordinary
  ADF p-values to regression residuals. About 18% of independent random walks pass at the nominal
  5% level (pinned in `tests/test_strategies.py`). Proper Engle-Granger critical values
  (`statsmodels.tsa.stattools.coint`) would be stricter.
* **Futures history is short** (about one year) and uses front-month data without roll
  adjustment.
* **Shooting Star needs a gap up**, which 24/7 crypto rarely has, so it almost never trades there.
* Daily and hourly bars cannot show the order of events inside a bar; where it matters, the
  pessimistic order is assumed.
* No slippage model beyond the fixed cost, and no capacity or market-impact limits.
