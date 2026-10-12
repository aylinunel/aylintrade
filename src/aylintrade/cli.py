"""Command line: ``aylintrade {list,fetch,backtest,daily,site}``.

``aylintrade daily`` is the one the GitHub Action runs: fresh data, backtest, one paper trading
day (with the agent committee when ANTHROPIC_API_KEY is set) and the dashboard data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from . import __version__
from .config import Config, ConfigError, load_config
from .data import DataStore, MissingDataError, available_sources

DEFAULT_CONFIG = "configs/default.yaml"
STALE_DAYS = 7
log = logging.getLogger("aylintrade")


def cmd_list(cfg: Config, args: argparse.Namespace) -> int:
    print("Markets:")
    for m in cfg.markets.values():
        role = "portfolio" if m.portfolio else "tested alone"
        print(f"  {m.id:<4} {m.label:<32} {m.group:<13} {role}")
    print("\nData sources:", ", ".join(available_sources()))
    return 0


def cmd_fetch(cfg: Config, args: argparse.Namespace) -> int:
    store, failed = DataStore(cfg.data_dir), []
    for m in cfg.markets.values():
        try:
            store.fetch(m, force=args.force)
        except Exception as e:  # keep going so one bad source doesn't block the rest
            log.error("%s: %s", m.id, e)
            failed.append(m.id)
    if failed:
        log.error("failed: %s", ", ".join(failed))
    # Only the traded markets are essential.
    return 1 if set(failed) & set(cfg.portfolio_markets) else 0


def cmd_backtest(cfg: Config, args: argparse.Namespace) -> int:
    from .research import run_study, write_study

    study = run_study(cfg)
    write_study(study, cfg.results_dir)
    print((cfg.results_dir / "summary.md").read_text())
    return 0


def cmd_daily(cfg: Config, args: argparse.Namespace) -> int:
    from .algorithm import close_prices
    from .paper import run_day
    from .research import load_daily, run_study, write_study
    from .site import build_site_data

    if not args.no_fetch:
        args.force = True
        if cmd_fetch(cfg, args):
            return 1
    daily = load_daily(cfg, cfg.portfolio_markets)
    stale = [m for m, df in daily.items() if (date.today() - df.index[-1].date()).days > STALE_DAYS]
    if stale:
        log.error("no data for over %d days: %s; not trading on stale prices", STALE_DAYS, stale)
        return 1
    write_study(run_study(cfg), cfg.results_dir)
    run_day(cfg, close_prices(daily), use_agents=not args.no_agents)
    build_site_data(cfg)
    return 0


def cmd_site(cfg: Config, args: argparse.Namespace) -> int:
    from .site import build_site_data

    print(build_site_data(cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aylintrade", description=__doc__)
    p.add_argument("--version", action="version", version=f"aylintrade {__version__}")
    p.add_argument("-c", "--config", default=DEFAULT_CONFIG, help="YAML config path")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show markets and data sources").set_defaults(func=cmd_list)
    sp = sub.add_parser("fetch", help="download and cache price data")
    sp.add_argument("--force", action="store_true", help="re-download cached data")
    sp.set_defaults(func=cmd_fetch)
    sub.add_parser("backtest", help="run the backtest study").set_defaults(func=cmd_backtest)
    sp = sub.add_parser("daily", help="fetch, backtest, trade one paper day, build site data")
    sp.add_argument("--no-agents", action="store_true", help="skip the agent committee")
    sp.add_argument("--no-fetch", action="store_true", help="use the cached data")
    sp.set_defaults(func=cmd_daily)
    sub.add_parser("site", help="build the dashboard's data.json").set_defaults(func=cmd_site)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return int(args.func(load_config(args.config), args))
    except (ConfigError, MissingDataError, KeyError, ValueError) as e:
        log.error("%s", e)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
