"""Create a standalone image of the RQ1 bug-discovery results table.

This artifact generator is independent of the thesis source. It takes exactly
four Layout QuickCheck result directories, calculates the 60-minute metrics,
and writes a PNG that can be viewed directly.

Usage:
    python create_rq1_results_table.py \
        CHROMIUM_NO_WEIGHTS_DIR CHROMIUM_WEIGHTS_DIR \
        FIREFOX_NO_WEIGHTS_DIR FIREFOX_WEIGHTS_DIR

Positional parameters:
    chromium_no_weights_dir
        Layout QuickCheck results for Chromium without property weights.
    chromium_weights_dir
        Layout QuickCheck results for Chromium with property weights.
    firefox_no_weights_dir
        Layout QuickCheck results for Firefox without property weights.
    firefox_weights_dir
        Layout QuickCheck results for Firefox with property weights.

Optional parameters:
    --output PATH
        Output PNG path. Defaults to ``figures/table_3_rq1_results.png``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

import matplotlib.pyplot as plt


SNAPSHOT_SECONDS = 3_600
SNAPSHOT_FILENAME = f"run_summary_{SNAPSHOT_SECONDS}s.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "figures" / "table_3_rq1_results.png"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a viewable RQ1 results table from four LQC runs."
    )
    parser.add_argument("chromium_no_weights_dir", type=Path)
    parser.add_argument("chromium_weights_dir", type=Path)
    parser.add_argument("firefox_no_weights_dir", type=Path)
    parser.add_argument("firefox_weights_dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output PNG path (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def load_metrics(run_dir: Path) -> tuple[str, str, str]:
    snapshot_path = run_dir / SNAPSHOT_FILENAME
    try:
        summary: Mapping[str, object] = json.loads(
            snapshot_path.read_text(encoding="utf-8")
        )
        tests_run = int(summary["tests_run"])
        bugs_found = int(summary["bugs_found"])
    except FileNotFoundError as error:
        raise SystemExit(f"Layout QuickCheck snapshot not found: {snapshot_path}") from error
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"Invalid Layout QuickCheck results in {snapshot_path}") from error

    if tests_run <= 0 or bugs_found < 0:
        raise SystemExit(f"Invalid counts in {snapshot_path}")

    speed = tests_run / (SNAPSHOT_SECONDS / 60)
    rate = bugs_found / tests_run * 100
    return f"{speed:.1f}", str(bugs_found), f"{rate:.3f}%"


def create_table(
    chromium_no_weights: tuple[str, str, str],
    chromium_weights: tuple[str, str, str],
    firefox_no_weights: tuple[str, str, str],
    firefox_weights: tuple[str, str, str],
    output: Path,
) -> None:
    columns = [
        "Browser",
        "No weights\nSpeed",
        "No weights\nBugs",
        "No weights\nRate",
        "Weights\nSpeed",
        "Weights\nBugs",
        "Weights\nRate",
    ]
    rows = [
        ["Chromium", *chromium_no_weights, *chromium_weights],
        ["Firefox", *firefox_no_weights, *firefox_weights],
    ]

    figure, axis = plt.subplots(figsize=(12, 3.2), dpi=160)
    axis.axis("off")
    table = axis.table(
        cellText=rows,
        colLabels=columns,
        cellLoc="center",
        colLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(14)
    table.scale(1, 1.8)

    for column in range(len(columns)):
        header = table[(0, column)]
        header.set_text_props(weight="bold", fontsize=12)
        header.set_facecolor("#e6e6e6")
        header.set_height(0.22)
    for row in range(1, len(rows) + 1):
        for column in range(len(columns)):
            table[(row, column)].set_height(0.14)
        table[(row, 0)].set_text_props(weight="bold")

    figure.suptitle(
        "Bug-discovery results across browser configurations",
        fontsize=18,
        y=0.94,
    )
    figure.text(
        0.5,
        0.06,
        "Runs use a 60-minute execution window. Speed is tests per minute; "
        "rate is bugs divided by executed tests.",
        ha="center",
        fontsize=11,
        style="italic",
    )
    figure.tight_layout(rect=(0.02, 0.10, 0.98, 0.90))

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved standalone table to {output}")


def main() -> None:
    arguments = parse_arguments()
    create_table(
        load_metrics(arguments.chromium_no_weights_dir),
        load_metrics(arguments.chromium_weights_dir),
        load_metrics(arguments.firefox_no_weights_dir),
        load_metrics(arguments.firefox_weights_dir),
        arguments.output,
    )


if __name__ == "__main__":
    main()
