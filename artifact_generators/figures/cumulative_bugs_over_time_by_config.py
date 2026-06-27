"""Generate Figure 3: cumulative bugs detected over time by configuration.

This script compares cumulative bug counts from multiple Layout QuickCheck
result directories and writes the graph used as Figure 3 in the thesis.

Usage:
    python cumulative_bugs_over_time_by_config.py LQC_DIR [LQC_DIR ...]

Optional parameters:
    --output PATH
        Write the PNG to PATH. By default, the script replaces the Figure 3
        image used by the thesis.

    --max-minutes NUMBER
        Plot only the first NUMBER minutes of each run. By default, the graph
        covers the longest supplied run.

Example:
    python cumulative_bugs_over_time_by_config.py \
        D:\\runs\\chromium-no-weights D:\\runs\\chromium-weights \
        --max-minutes 60
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "figures"
    / "cumulative_bugs_detected_over_time_by_configuration.png"
)
SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
HOURS_THRESHOLD_MINUTES = 240
TITLE_FONT_SIZE = 24
LABEL_FONT_SIZE = 22
TICK_FONT_SIZE = 20
LEGEND_FONT_SIZE = 20


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate cumulative bug counts over time for multiple configurations."
    )
    parser.add_argument(
        "lqc_dirs",
        nargs="+",
        type=Path,
        help="Layout QuickCheck result directories to compare.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output PNG path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--max-minutes",
        type=float,
        default=None,
        help="Maximum execution time to plot, in minutes.",
    )
    return parser.parse_args()


def format_run_name(name: str) -> str:
    replacements = {
        "chromium": "Chromium",
        "chrome": "Chrome",
        "firefox": "Firefox",
        "sort": "Sort",
    }
    words = name.replace("-", " ").split()
    return " ".join(replacements.get(word, word.capitalize()) for word in words)


def load_series(summary_dir: Path, max_minutes: float | None) -> dict[str, object]:
    snapshots: list[tuple[int, int]] = []
    for path in summary_dir.glob("run_summary_*s.json"):
        match = SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue

        snapshot_seconds = int(match.group(1))
        if snapshot_seconds % 60 != 0:
            continue

        with path.open(encoding="utf-8") as snapshot_file:
            data = json.load(snapshot_file)
        snapshots.append((snapshot_seconds, int(data["bugs_found"])))

    snapshots.sort()
    if max_minutes is not None:
        snapshots = [
            snapshot
            for snapshot in snapshots
            if snapshot[0] / 60 <= max_minutes
        ]
    if not snapshots:
        raise ValueError(
            f"No run_summary_<seconds>s.json snapshots found in {summary_dir}"
        )

    return {
        "label": format_run_name(summary_dir.name),
        "minutes": [seconds / 60 for seconds, _ in snapshots],
        "bugs": [bugs for _, bugs in snapshots],
    }


def time_axis(max_minutes: float) -> tuple[float, str, float]:
    if max_minutes > HOURS_THRESHOLD_MINUTES:
        return 60, "Execution time (hours)", 1
    return 1, "Execution time (minutes)", 10


def apply_font_sizes(axis) -> None:
    axis.title.set_fontsize(TITLE_FONT_SIZE)
    axis.xaxis.label.set_fontsize(LABEL_FONT_SIZE)
    axis.yaxis.label.set_fontsize(LABEL_FONT_SIZE)
    axis.tick_params(axis="both", which="both", labelsize=TICK_FONT_SIZE)
    for text in axis.get_legend().get_texts():
        text.set_fontsize(LEGEND_FONT_SIZE)


def generate_figure(
    summary_dirs: list[Path],
    output: Path,
    max_minutes: float | None,
) -> None:
    series = [load_series(directory, max_minutes) for directory in summary_dirs]
    plot_minutes = (
        max_minutes
        if max_minutes is not None
        else max(max(item["minutes"]) for item in series)
    )
    scale, x_label, tick_interval = time_axis(plot_minutes)

    figure, axis = plt.subplots(figsize=(11, 6), dpi=140)
    for item in series:
        axis.plot(
            [minute / scale for minute in item["minutes"]],
            item["bugs"],
            marker="o",
            linewidth=2,
            label=item["label"],
        )

    axis.set_title("Cumulative Bugs Detected Over Time by Configuration")
    axis.set_xlabel(x_label)
    axis.set_ylabel("Detected bugs")
    axis.set_xlim(0, plot_minutes / scale)
    axis.set_ylim(0, max(max(item["bugs"]) for item in series) + 2)
    axis.xaxis.set_major_locator(MultipleLocator(tick_interval))
    axis.grid(True, alpha=0.3)
    axis.legend()
    apply_font_sizes(axis)
    figure.tight_layout()

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    print(f"Saved Figure 3 to {output}")


def main() -> None:
    arguments = parse_arguments()
    generate_figure(
        arguments.lqc_dirs,
        arguments.output,
        arguments.max_minutes,
    )


if __name__ == "__main__":
    main()
