# Backtest summary

2006-01-01 to 2026-10-09, after trading costs. Settings: 10% vol target, 25% core holding, 3% band, horizons 21, 63, 126, 252d.

| Portfolio | Per year | Volatility | Sharpe | Worst drop | Turnover / yr |
|---|---:|---:|---:|---:|---:|
| Aylin trend portfolio | 8.4% | 9.5% | 0.89 | -22% | 5.8x |
| S&P 500 (SPY) buy & hold | 11.0% | 19.0% | 0.64 | -55% | 0.0x |
| Equal-weight buy & hold | 13.2% | 17.6% | 0.79 | -40% | 0.3x |
| Risk parity, always invested | 8.4% | 9.9% | 0.87 | -24% | 0.7x |

## Each market on its own

| Market | Sharpe | Hold Sharpe | Per year | Hold per year | Worst drop | Hold worst |
|---|---:|---:|---:|---:|---:|---:|
| S&P 500 (SPY) | 0.70 | 0.65 | 7.1% | 11.2% | -24% | -55% |
| Nasdaq-100 (QQQ) | 0.80 | 0.78 | 8.3% | 15.9% | -23% | -53% |
| Russell 2000 (IWM) | 0.38 | 0.46 | 3.5% | 8.5% | -27% | -59% |
| Developed ex-US (EFA) | 0.33 | 0.36 | 3.0% | 5.6% | -27% | -61% |
| Gold (GLD) | 0.68 | 0.61 | 6.8% | 10.0% | -34% | -46% |
| US Treasuries 20y+ (TLT) | 0.32 | 0.24 | 2.8% | 2.5% | -34% | -48% |
| Bitcoin (BTC) | 0.82 | 0.79 | 8.3% | 34.0% | -18% | -77% |
| Ethereum (ETH) | 0.64 | 0.67 | 6.2% | 23.9% | -16% | -79% |

Not tested: S&P 500 E-mini futures (ES) (270 days of data; needs 504); Gold futures (GC) (269 days of data; needs 504); Crude oil futures (CL) (180 days of data; needs 504)

## Stress tests

| Test | Setting | Sharpe | Per year | Worst drop | SPY Sharpe |
|---|---|---:|---:|---:|---:|
| As configured | 10% vol target, 25% core holding, 3% band, horizons 21, 63, 126, 252d | 0.89 | 8.4% | -22% | 0.64 |
| Trading costs | 2x | 0.86 | 8.1% | -23% | 0.64 |
| Trading costs | 3x | 0.83 | 7.7% | -23% | 0.64 |
| Core holding | 0% | 0.81 | 7.4% | -26% | 0.64 |
| Core holding | 50% | 0.86 | 8.2% | -23% | 0.64 |
| Core holding | 100% | 0.87 | 8.4% | -24% | 0.64 |
| Volatility target | 8% | 0.91 | 7.2% | -19% | 0.64 |
| Volatility target | 12% | 0.90 | 9.2% | -26% | 0.64 |
| Volatility target | 15% | 0.95 | 10.4% | -29% | 0.64 |
| Rebalance band | 0% | 0.84 | 7.7% | -23% | 0.64 |
| Rebalance band | 5% | 0.91 | 8.8% | -25% | 0.64 |
| Trend horizons | 63d, 126d, 252d | 0.92 | 8.7% | -21% | 0.64 |
| Trend horizons | 252d | 0.84 | 8.0% | -24% | 0.64 |
| Markets | without crypto | 0.86 | 7.7% | -21% | 0.64 |
| Sub-period | 2006-2013 | 0.82 | 7.5% | -20% | 0.30 |
| Sub-period | 2013-2019 | 1.03 | 8.3% | -15% | 1.10 |
| Sub-period | 2019-2026 | 0.87 | 9.3% | -22% | 0.81 |

_Past performance does not predict future results. Not financial advice._
