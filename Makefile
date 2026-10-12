.PHONY: install lint test fetch backtest daily site preview

install:      ## editable install with dev tools and the agents
	pip install -e ".[dev]"

lint:         ## style, formatting and types
	ruff check src tests
	ruff format --check src tests
	mypy

test:         ## all tests, offline (the agents run against a fake client)
	pytest --cov

fetch:        ## download market data into data/
	aylintrade fetch

backtest:     ## the 20-year study -> results/latest/
	aylintrade backtest

daily:        ## what the GitHub Action runs: fetch, backtest, one paper day, site data
	aylintrade daily

site:         ## rebuild site/data.json from results/ and paper/
	aylintrade site

preview: site ## open the dashboard at http://localhost:8000
	cd site && python -m http.server 8000
