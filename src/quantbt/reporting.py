"""Write results to disk: CSV tables, a Markdown summary and (optionally) PNG charts."""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .pipeline import RunOutput

# Reference palette (validated for colour-vision deficiency); see docs/methodology.md.
INK, INK_MUTED = "#0b0b0b", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834"]
GOOD, BAD, NEUTRAL = "#2a78d6", "#e34948", "#f0efec"


def write_run(
    output: RunOutput, out_dir: Path, config_snapshot: dict[str, Any] | None = None
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    output.results.to_csv(out_dir / "results.csv", index=False, float_format="%.6g")
    output.curves.to_csv(out_dir / "curves.csv", index=False, float_format="%.6g")
    (out_dir / "summary.md").write_text(summary_markdown(output.results))
    meta = {
        "quantbt_version": __version__,
        "python": platform.python_version(),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": config_snapshot or {},
    }
    (out_dir / "run.json").write_text(json.dumps(meta, indent=2, default=str))


def _pct(x: float) -> str:
    return f"{x:+.1%}" if pd.notna(x) else ""


def summary_markdown(results: pd.DataFrame) -> str:
    ok = results[results["status"] == "ok"]
    tested = ok[ok["strategy"] != "buy_and_hold"]
    beat = int((tested["sharpe_vs_bh"] > 0).sum())
    lines = [
        "# Backtest summary",
        "",
        f"{beat} of {len(tested)} strategy-market tests beat buy & hold on Sharpe ratio, "
        "after trading costs.",
        "",
    ]
    for _, g in results.groupby("market", sort=False):
        label = g["market_label"].iloc[0]
        gok = g[g["status"] == "ok"].sort_values("sharpe", ascending=False)
        first = gok.iloc[0] if len(gok) else None
        span = f" ({first['start']} to {first['end']})" if first is not None else ""
        lines += [
            f"## {label}{span}",
            "",
            "| Strategy | Sharpe | vs hold | Per year | Worst drop | Trades | In market |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for _, r in gok.iterrows():
            vs = "" if r["strategy"] == "buy_and_hold" else f"{r['sharpe_vs_bh']:+.2f}"
            lines.append(
                f"| {r['strategy_label']} | {r['sharpe']:.2f} | {vs} | {_pct(r['cagr'])} | "
                f"{r['max_drawdown']:.0%} | {int(r['trades'])} | {r['time_in_market']:.0%} |"
            )
        skipped = g[g["status"] == "skipped"]
        if len(skipped):
            lines += [
                "",
                "Not tested: "
                + "; ".join(
                    f"{r['strategy_label']} ({r['reason'].lower()})" for _, r in skipped.iterrows()
                ),
            ]
        lines.append("")
    lines += [
        "_Past performance does not predict future results. Research only, not financial advice._",
        "",
    ]
    return "\n".join(lines)


def write_robustness(rows: pd.DataFrame, years: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out_dir / "robustness.csv", index=False, float_format="%.6g")
    years.to_csv(out_dir / "yearly_returns.csv", index=False, float_format="%.6g")


# ------------------------------------------------------------------ charts
HEATMAP_LIMIT = 1.5


def _place_end_labels(ax: Any, labels: list[tuple[float, str]], x: Any) -> None:
    """Value labels at the right end of each highlighted line, nudged apart so they never touch."""
    lo, hi = ax.get_ylim()
    span = np.log10(hi) - np.log10(lo)
    gap = 0.045 * span  # minimum distance in log10 units (~ one line of 8pt text)
    placed: list[float] = []
    for value, text in sorted(labels):
        y = np.log10(max(value, lo))
        if placed and y - placed[-1] < gap:
            y = placed[-1] + gap
        placed.append(y)
        ax.annotate(
            text,
            (x, 10**y),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=INK,
            annotation_clip=False,
        )


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_charts(results_dir: Path) -> list[Path]:
    """Equity curve per market plus a strategy x market heatmap. Requires matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
        from matplotlib.ticker import FuncFormatter
    except ImportError as e:  # pragma: no cover - optional dependency
        raise RuntimeError("charts need matplotlib: pip install 'quantbt[plot]'") from e

    results = pd.read_csv(results_dir / "results.csv")
    curves = pd.read_csv(results_dir / "curves.csv", parse_dates=["week"])
    chart_dir = results_dir / "charts"
    chart_dir.mkdir(exist_ok=True)
    written = []
    labels = dict(zip(results["strategy"], results["strategy_label"], strict=False))

    for mid, g in curves.groupby("market", sort=False):
        res = results[(results["market"] == mid) & (results["status"] == "ok")]
        ranked = res[res["strategy"] != "buy_and_hold"].sort_values("sharpe", ascending=False)
        top = list(ranked["strategy"].head(2))
        fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
        fig.patch.set_facecolor(SURFACE)
        _style(ax)
        order = sorted(g["strategy"].unique(), key=lambda s: (s == "buy_and_hold") or s in top)
        end_labels: list[tuple[float, str]] = []
        for sid in order:
            s = g[g["strategy"] == sid]
            if sid == "buy_and_hold":
                color, lw, z = INK, 2.0, 3
            elif sid in top:
                color, lw, z = SERIES[top.index(sid)], 2.0, 3
            else:
                color, lw, z = AXIS, 1.0, 1
            ax.plot(
                s["week"],
                s["equity"].clip(lower=1e-3),
                color=color,
                lw=lw,
                zorder=z,
                solid_capstyle="round",
                label=labels.get(sid, sid) if z == 3 else None,
            )
            if z == 3:
                end_labels.append((float(s["equity"].iloc[-1]), f"${s['equity'].iloc[-1]:,.2f}"))
        ax.set_yscale("log")
        _place_end_labels(ax, end_labels, g["week"].max())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
        ax.set_title(
            f"{res['market_label'].iloc[0]}: growth of $1 after costs",
            loc="left",
            fontsize=11,
            color=INK,
        )
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK)
        ax.text(
            1.0,
            -0.12,
            "Grey: other strategies",
            transform=ax.transAxes,
            ha="right",
            fontsize=8,
            color=INK_MUTED,
        )
        fig.tight_layout()
        path = chart_dir / f"equity_{mid}.png"
        fig.savefig(path, facecolor=SURFACE)
        plt.close(fig)
        written.append(path)

    ok = results[(results["status"] == "ok") & (results["strategy"] != "buy_and_hold")]
    grid = ok.pivot_table(index="strategy_label", columns="market", values="sharpe_vs_bh")
    grid = grid[[m for m in results["market"].unique() if m in grid.columns]]
    grid = grid.loc[grid.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(1.3 * len(grid.columns) + 3, 0.45 * len(grid) + 1.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    cmap = LinearSegmentedColormap.from_list("div", [BAD, NEUTRAL, GOOD]).with_extremes(bad=SURFACE)
    lim = HEATMAP_LIMIT  # clip so one extreme cell doesn't wash out the rest
    values = np.ma.masked_invalid(grid.to_numpy(float).clip(-lim, lim))
    ax.imshow(values, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(len(grid.columns)), grid.columns)
    ax.set_yticks(range(len(grid.index)), grid.index)
    ax.tick_params(colors=INK, labelsize=9, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    for i, row in enumerate(grid.to_numpy(float)):
        for j, v in enumerate(row):
            text, color = (f"{v:+.2f}", INK) if pd.notna(v) else ("n/a", INK_MUTED)
            ax.text(j, i, text, ha="center", va="center", fontsize=8, color=color)
    ax.set_title(
        f"Sharpe ratio minus buy & hold (blue beat holding, red lagged; colour capped at ±{lim})",
        loc="left",
        fontsize=10,
        color=INK,
    )
    fig.tight_layout()
    path = chart_dir / "heatmap_sharpe_vs_hold.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    written.append(path)
    return written
