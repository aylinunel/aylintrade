# Extending quantbt

## Add a strategy

Create `src/quantbt/strategies/momentum.py`:

```python
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import PositionStrategy, register


@register
@dataclass(frozen=True)
class Momentum(PositionStrategy):
    """Long when the trailing return over `lookback` bars is positive."""

    lookback: int = 63          # dataclass fields are the tunable parameters

    id = "momentum"
    label = "Time-series momentum"
    description = "Long when the 3-month return is positive, else cash"

    def warmup(self) -> int:
        return self.lookback

    def positions(self, bars: pd.DataFrame) -> pd.Series:
        trailing = bars["Close"].pct_change(self.lookback)
        return pd.Series(np.where(trailing > 0, 1.0, 0.0), index=bars.index)
```

Then:

1. Import the module in `src/quantbt/strategies/__init__.py`.
2. Add it to a config: `momentum: { lookback: 63 }`.
3. Run `pytest`. The look-ahead tests cover the new strategy automatically.

Choose the base class by what the strategy needs:

| Base class | Input | Output |
|---|---|---|
| `PositionStrategy` | OHLCV bars | Target exposure per bar, in [-1, 1] |
| `IntradayStrategy` | Daily or hourly bars (set `interval = "1h"`) | Round trips: `date, side, entry, exit` |
| `PairStrategy` | Two close series | Exposure per leg |

## Add a market

```yaml
markets:
  QQQ:
    label: Nasdaq-100 ETF (QQQ)
    group: Equity ETF
    periods_per_year: 252
    cost_per_side: 0.0005
    data:
      1d: { source: sp500_data, symbol: QQQ }
```

Your own data works through the `csv` source:

```yaml
    data:
      1d: { source: csv, path: "my_data/{symbol}_{interval}.csv", symbol: EURUSD }
```

The CSV needs a `Date` column (or set `date_column`) and Open/High/Low/Close, with Volume optional.

## Add a data source

```python
from quantbt.data import DataSource, register_source


@register_source("my_vendor")
class MyVendorSource(DataSource):
    intervals = ("1d", "1h")

    def fetch(self, symbol, interval, **params):
        ...  # return a DataFrame with a DatetimeIndex and OHLC(V) columns
```

`DataSource.load` normalises the output (sorting, de-duplication, UTC, validation), so `fetch`
only has to return the raw frame. Import the module before loading the config, for example from
`quantbt/data/__init__.py`.

## Add a robustness check

```yaml
robustness:
  - strategy: momentum
    markets: [SPY, BTC]
    param_sets: [{ lookback: 21 }, { lookback: 63 }, { lookback: 126 }]
    cost_multipliers: [1, 2, 3]
    subperiods: 3
```
