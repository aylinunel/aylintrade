# Backtest summary

6 of 48 strategy-market tests beat buy & hold on Sharpe ratio, after trading costs.

## S&P 500 ETF (SPY) (1995-01-03 to 2026-10-08)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| Buy & hold | 0.66 |  | +11.2% | -55% | 1 | 100% |
| MACD oscillator | 0.52 | -0.14 | +5.5% | -28% | 185 | 64% |
| Heikin-Ashi | 0.40 | -0.25 | +3.9% | -32% | 415 | 34% |
| Bollinger Bands W | 0.31 | -0.35 | +0.6% | -9% | 28 | 3% |
| Parabolic SAR | 0.19 | -0.47 | +1.6% | -56% | 398 | 61% |
| Shooting Star | -0.19 | -0.85 | -0.1% | -2% | 2 | 0% |
| RSI pattern (H&S) | -0.20 | -0.85 | -0.9% | -33% | 73 | 3% |
| Pair trading | -0.68 | -1.21 | -0.5% | -14% | 144 | 7% |
| Dual Thrust | -1.11 | -1.76 | -7.4% | -92% | 1816 | 22% |

Not tested: London Breakout (needs hourly data, which is not configured for this market)

## Bitcoin (BTC/USDT) (2017-08-17 to 2026-10-11)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| MACD oscillator | 0.95 | +0.13 | +39.8% | -73% | 85 | 55% |
| Bollinger Bands W | 0.87 | +0.05 | +7.1% | -9% | 10 | 2% |
| Buy & hold | 0.82 |  | +38.3% | -83% | 1 | 100% |
| Parabolic SAR | 0.79 | -0.04 | +28.6% | -71% | 134 | 52% |
| Heikin-Ashi | 0.61 | -0.21 | +16.5% | -50% | 170 | 47% |
| RSI pattern (H&S) | 0.54 | -0.28 | +6.5% | -17% | 39 | 6% |
| Shooting Star | 0.00 | -0.82 | +0.0% | 0% | 0 | 0% |
| Dual Thrust | -0.01 | -0.85 | -6.7% | -73% | 1042 | 31% |
| Pair trading | -0.77 | -1.50 | -5.5% | -39% | 52 | 10% |
| London Breakout | -8.12 | -8.60 | -39.7% | -91% | 1234 | 71% |

## Ethereum (ETH/USDT) (2017-08-17 to 2026-10-11)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| MACD oscillator | 0.95 | +0.25 | +48.9% | -69% | 85 | 51% |
| Buy & hold | 0.71 |  | +26.1% | -94% | 1 | 100% |
| Parabolic SAR | 0.50 | -0.20 | +13.3% | -88% | 127 | 49% |
| Heikin-Ashi | 0.21 | -0.50 | -1.2% | -83% | 153 | 46% |
| Bollinger Bands W | 0.18 | -0.53 | +1.3% | -24% | 3 | 2% |
| Dual Thrust | 0.16 | -0.55 | -3.5% | -72% | 1025 | 30% |
| Shooting Star | 0.00 | -0.71 | +0.0% | 0% | 0 | 0% |
| RSI pattern (H&S) | -0.35 | -1.06 | -5.0% | -46% | 25 | 3% |
| Pair trading | -0.61 | -1.21 | -3.6% | -31% | 54 | 11% |
| London Breakout | -8.32 | -8.54 | -40.5% | -92% | 1220 | 70% |

## S&P 500 E-mini futures (ES) (2025-03-24 to 2026-04-14)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| MACD oscillator | 1.74 | +0.72 | +17.9% | -5% | 6 | 65% |
| Buy & hold | 1.02 |  | +19.0% | -14% | 1 | 100% |
| Parabolic SAR | 0.64 | -0.38 | +6.6% | -11% | 16 | 63% |
| Heikin-Ashi | 0.53 | -0.49 | +6.4% | -10% | 12 | 29% |
| Bollinger Bands W | 0.00 | -1.02 | +0.0% | 0% | 1 | 0% |
| Shooting Star | 0.00 | -1.02 | +0.0% | 0% | 0 | 0% |
| RSI pattern (H&S) | -0.16 | -1.18 | -0.5% | -3% | 1 | 2% |
| Dual Thrust | -1.50 | -2.69 | -14.7% | -21% | 88 | 32% |
| London Breakout | -2.82 | -3.84 | -12.6% | -14% | 202 | 74% |

Not tested: Pair trading (only 270 overlapping days; needs 250 to fit the model plus a test period)

## Gold futures (GC) (2025-03-24 to 2026-04-14)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| Buy & hold | 1.65 |  | +55.6% | -20% | 1 | 100% |
| Parabolic SAR | 1.01 | -0.64 | +21.6% | -11% | 12 | 57% |
| MACD oscillator | 0.85 | -0.81 | +18.3% | -14% | 9 | 63% |
| Heikin-Ashi | 0.57 | -1.09 | +5.6% | -14% | 13 | 33% |
| Dual Thrust | 0.02 | -1.45 | -0.5% | -11% | 51 | 19% |
| Bollinger Bands W | 0.00 | -1.65 | +0.0% | 0% | 0 | 0% |
| Shooting Star | 0.00 | -1.65 | +0.0% | 0% | 0 | 0% |
| RSI pattern (H&S) | -0.64 | -2.30 | -2.9% | -3% | 4 | 6% |

Not tested: London Breakout (needs hourly data, which is not configured for this market); Pair trading (no pair partner configured for this market)

## Crude oil futures (CL) (2025-06-02 to 2026-04-14)

| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |
|---|---:|---:|---:|---:|---:|---:|
| Heikin-Ashi | 2.12 | +0.86 | +22.2% | -6% | 8 | 30% |
| MACD oscillator | 1.47 | +0.20 | +73.3% | -18% | 5 | 44% |
| Buy & hold | 1.26 |  | +69.8% | -27% | 1 | 99% |
| Parabolic SAR | 1.05 | -0.21 | +44.6% | -25% | 7 | 46% |
| RSI pattern (H&S) | 0.63 | -0.63 | +4.7% | -3% | 1 | 1% |
| Shooting Star | 0.00 | -1.26 | +0.0% | 0% | 0 | 0% |
| Bollinger Bands W | -0.60 | -1.86 | -2.9% | -3% | 1 | 4% |
| Dual Thrust | -0.77 | -1.95 | -55.2% | -55% | 61 | 33% |

Not tested: London Breakout (needs hourly data, which is not configured for this market); Pair trading (no pair partner configured for this market)

_Past performance does not predict future results. Research only, not financial advice._
