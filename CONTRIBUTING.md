# Contributing

1. `pip install -e ".[dev]"` and, optionally, `pre-commit install`.
2. Make your change, with a test. New strategies are covered by the look-ahead tests
   automatically; add a test for anything the strategy promises beyond that.
3. `make lint test` must pass. CI runs the same checks on Python 3.10–3.13.
4. If a change moves published results, re-run `quantbt run -j 4 --charts` and
   `quantbt robustness`, commit `results/latest/`, and explain the change in the pull request.

Guides: [docs/extending.md](docs/extending.md) (adding strategies, markets, data sources) and
[docs/methodology.md](docs/methodology.md) (the rules every backtest follows).
