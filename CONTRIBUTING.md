# Contributing

1. `pip install -e ".[dev]"` and, optionally, `pre-commit install`.
2. Make the smallest change that fully solves the problem, with a test for any new logic
   (the style follows [ponytail](https://github.com/DietrichGebert/ponytail)). Any change to the
   algorithm must keep `tests/test_algorithm.py::test_weights_never_use_future_prices` passing.
3. `make lint test` must pass. CI runs the same checks on Python 3.11–3.13.
4. If a change moves published results, run `aylintrade backtest`, commit `results/latest/`,
   add the variant to the stress tests in `research.py` if it was a design choice, and explain
   the change in the pull request.

Rules and limitations: [docs/methodology.md](docs/methodology.md).
