"""Shared helpers for the analysis notebooks.

* Data only ever comes from a saved query: `load("phase3", "q1_gap_by_distance")` runs
  analysis/queries/phase3/q1_gap_by_distance.sql and saves reports/tables/phase3/<name>.csv
  (the table view of the figure), so every plotted number is reproducible.
* One look for every figure: fixed commodity colours (validated palette, never cycled),
  thin marks, recessive grid, direct labels, title + units + source note on each PNG.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

from mandipulse.config import PROJECT_ROOT
from mandipulse.queries import QUERY_ROOT, TABLE_ROOT, run_sql

FIG_DIR = PROJECT_ROOT / "reports" / "figures"

# Categorical slots 1-3 of the reference palette, in fixed order (validated: all checks pass on
# the light surface; aqua is below 3:1 contrast, so every series is also direct-labelled).
COMMODITY_COLORS = {"Tomato": "#2a78d6", "Onion": "#eb6834", "Potato": "#1baf7a"}
COMMODITIES = list(COMMODITY_COLORS)
# Single-hue sequential ramp (light -> dark) for magnitude heatmaps.
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SOURCE = (
    "Source: Kaggle 'Daily Market Prices of Commodity India' (Agmarknet, GODL-India); "
    "Mandi Pulse analysis, main period 2018-01-01 to 2025-10-31."
)


def load(folder: str, query: str) -> pd.DataFrame:
    """Run analysis/queries/<folder>/<query>.sql, save the CSV, return the DataFrame."""
    df = run_sql((QUERY_ROOT / folder / f"{query}.sql").read_text(encoding="utf-8"))
    out = TABLE_ROOT / folder / f"{query}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


def style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 10,
            "text.color": INK,
            "axes.labelcolor": INK_2,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2,
            "legend.frameon": False,
        }
    )


def header(fig, title: str, subtitle: str) -> None:
    """Title + subtitle at fixed distances (in inches) from the top, whatever the figure height."""
    height = fig.get_figheight()
    fig.suptitle(
        title,
        x=0.01,
        y=1 - 0.12 / height,
        ha="left",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=INK,
    )
    fig.text(0.01, 1 - 0.45 / height, subtitle, ha="left", va="top", fontsize=10, color=INK_2)
    fig._mp_top = 1 - 0.75 / height  # plots start below the header


def figure(title: str, subtitle: str, width: float = 9, height: float = 5):
    style()
    fig, ax = plt.subplots(figsize=(width, height))
    header(fig, title, subtitle)
    return fig, ax


def legend(ax, ncols: int = 3) -> None:
    """Legend in a strip just above the plot area, so it never covers data."""
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.01),
        ncols=ncols,
        borderaxespad=0,
        handlelength=1.6,
        fontsize=9.5,
    )


def save(fig, name: str, note: str = "") -> Path:
    """Add the source note and save reports/figures/<name>.png."""
    text = SOURCE if not note else f"{note}\n{SOURCE}"
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=7.5, color=MUTED)
    bottom = (0.62 if note else 0.4) / fig.get_figheight()
    fig.tight_layout(rect=(0, bottom, 1, getattr(fig, "_mp_top", 0.88)))
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def label_line_ends(
    ax, df: pd.DataFrame, x: str, y: str, by: str, fmt: str = "{:.0f}", min_gap_pt: float = 12
) -> None:
    """Direct-label each series at its last point (ink text; the coloured mark carries identity).
    Labels that would overlap are pushed apart vertically by at least `min_gap_pt` points."""
    ends = []
    for key, g in df.groupby(by):
        last = g.sort_values(x).iloc[-1]
        ends.append((key, last[x], last[y]))
    ax.figure.canvas.draw()  # finalise limits so data -> pixel transforms are correct
    to_px = ax.transData.transform
    placed = sorted(
        (to_px((ax.xaxis.convert_units(xv), float(yv)))[1], key, xv, yv) for key, xv, yv in ends
    )
    px_per_pt = ax.figure.dpi / 72  # offsets in points scale with the saved resolution
    targets = []
    for py, *_ in placed:
        targets.append(max(py, targets[-1] + min_gap_pt * px_per_pt) if targets else py)
    for (py, key, xv, yv), ty in zip(placed, targets, strict=True):
        ax.annotate(
            f"{key}  " + fmt.format(yv),
            (xv, yv),
            xytext=(6, (ty - py) / px_per_pt),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_2,
        )
