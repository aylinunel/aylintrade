.PHONY: install lint test fetch run robustness charts all

install:      ## editable install with dev tools
	pip install -e ".[dev]"

lint:         ## style, formatting and types
	ruff check src tests
	ruff format --check src tests
	mypy

test:         ## unit + end-to-end tests (offline)
	pytest --cov

fetch:        ## download market data into data/
	quantbt fetch

run:          ## backtest everything, 4 markets in parallel, with charts
	quantbt run -j 4 --charts

robustness:   ## parameter / cost / sub-period checks
	quantbt robustness

all: fetch run robustness
