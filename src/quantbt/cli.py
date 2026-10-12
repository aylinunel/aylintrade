"""Command-line interface: ``quantbt {list,fetch,run,robustness,report}``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .config import Config, ConfigError, load_config
from .data import DataStore, MissingDataError, available_sources

DEFAULT_CONFIG = "configs/default.yaml"
log = logging.getLogger("quantbt")


def _config(args: argparse.Namespace) -> Config:
    cfg = load_config(args.config)
    return cfg.select(getattr(args, "markets", None), getattr(args, "strategies", None))


def cmd_list(args: argparse.Namespace) -> int:
    from .strategies import available_strategies, get_strategy_class

    print("Strategies:")
    for sid in available_strategies():
        cls = get_strategy_class(sid)
        print(f"  {sid:<20} {cls.kind:<9} {cls.description}")
    print("\nData sources:", ", ".join(available_sources()))
    if Path(args.config).exists():
        cfg = load_config(args.config)
        print(f"\nMarkets in {args.config}:")
        for m in cfg.markets.values():
            flag = "" if m.trade else "  (pair partner only)"
            print(f"  {m.id:<5} {m.label:<32} {', '.join(m.data)}{flag}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    cfg = _config(args)
    store = DataStore(cfg.data_dir)
    failed = []
    for m in cfg.markets.values():
        try:
            store.fetch(m, force=args.force)
        except Exception as e:  # keep going so one bad source doesn't block the rest
            log.error("%s: %s", m.id, e)
            failed.append(m.id)
    if failed:
        log.error("failed: %s", ", ".join(failed))
        return 1
    log.info("data ready in %s", store.root)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_all
    from .reporting import plot_charts, write_run

    cfg = _config(args)
    out = Path(args.out) if args.out else cfg.results_dir
    t0 = time.time()
    output = run_all(cfg, jobs=args.jobs)
    snapshot = {"markets": list(cfg.markets), "strategies": cfg.strategies}
    write_run(output, out, snapshot)
    log.info("%d results in %.0fs -> %s", len(output.results), time.time() - t0, out)
    if args.charts:
        for p in plot_charts(out):
            log.info("chart: %s", p)
    print((out / "summary.md").read_text())
    return 0


def cmd_robustness(args: argparse.Namespace) -> int:
    from .reporting import write_robustness
    from .robustness import run_robustness

    cfg = load_config(args.config)
    out = Path(args.out) if args.out else cfg.results_dir
    rows, years = run_robustness(cfg)
    write_robustness(rows, years, out)
    print(rows.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .reporting import plot_charts

    for p in plot_charts(Path(args.results)):
        print(p)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quantbt", description=__doc__)
    p.add_argument("--version", action="version", version=f"quantbt {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser, select: bool = True) -> None:
        sp.add_argument("-c", "--config", default=DEFAULT_CONFIG, help="YAML config path")
        if select:
            sp.add_argument("-m", "--markets", nargs="+", help="only these market ids")

    sp = sub.add_parser("list", help="show strategies, data sources and markets")
    common(sp, select=False)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("fetch", help="download and cache price data")
    common(sp)
    sp.add_argument("--force", action="store_true", help="re-download cached data")
    sp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser("run", help="backtest strategies and write results")
    common(sp)
    sp.add_argument("-s", "--strategies", nargs="+", help="only these strategy ids")
    sp.add_argument("-j", "--jobs", type=int, default=1, help="markets to run in parallel")
    sp.add_argument("-o", "--out", help="output directory (default: results_dir in config)")
    sp.add_argument("--charts", action="store_true", help="also write PNG charts")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("robustness", help="parameter, cost and sub-period checks")
    common(sp, select=False)
    sp.add_argument("-o", "--out", help="output directory")
    sp.set_defaults(func=cmd_robustness)

    sp = sub.add_parser("report", help="draw charts for an existing results directory")
    sp.add_argument("results", nargs="?", default="results/latest")
    sp.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return int(args.func(args))
    except (ConfigError, MissingDataError, KeyError, ValueError) as e:
        log.error("%s", e)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
