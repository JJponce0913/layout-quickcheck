"""Create a standalone post-processing-time-over-time figure.

The script takes one or more Layout QuickCheck result directories. Each
directory must contain ``run_summary_<seconds>s.json`` snapshots.

Usage:
    python post_processing_time_over_time.py LQC_DIR [LQC_DIR ...]

Optional parameters:
    --output PATH
        Output PNG path. Defaults to
        ``figures/combined_minimization_and_clustering_time_over_time.png``.
    --max-minutes MINUTES
        Ignore snapshots after this execution time.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "figures"
    / "combined_minimization_and_clustering_time_over_time.png"
)


def display_name(path: Path) -> str:
    replacements = {"chromium": "Chromium", "firefox": "Firefox", "sort": "Sort"}
    return " ".join(
        replacements.get(word, word.capitalize())
        for word in path.name.replace("-", " ").split()
    )


def load_series(directory: Path, max_minutes: float | None) -> tuple[list[float], list[float]]:
    samples: list[tuple[int, float]] = []
    for path in directory.glob("run_summary_*s.json"):
        match = SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue
        seconds = int(match.group(1))
        if seconds % 60:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            processing_seconds = float(data["true_minification_seconds"]) + float(
                data["sorting_seconds"]
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"Invalid Layout QuickCheck snapshot: {path}: {error}") from error
        minutes = seconds / 60
        if max_minutes is None or minutes <= max_minutes:
            samples.append((seconds, processing_seconds))

    if not samples:
        raise SystemExit(f"No usable Layout QuickCheck snapshots found in {directory}")
    samples.sort()
    return [seconds / 60 for seconds, _ in samples], [value for _, value in samples]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lqc_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-minutes", type=float)
    arguments = parser.parse_args()

    series = [
        (display_name(directory), *load_series(directory, arguments.max_minutes))
        for directory in arguments.lqc_dirs
    ]
    maximum_minutes = arguments.max_minutes or max(max(minutes) for _, minutes, _ in series)
    use_hours = maximum_minutes > 240
    scale = 60 if use_hours else 1

    figure, axis = plt.subplots(figsize=(11, 6), dpi=140)
    for label, minutes, processing_seconds in series:
        axis.plot(
            [minute / scale for minute in minutes],
            processing_seconds,
            marker="o",
            linewidth=2,
            label=label,
        )
    axis.set_title("Post-Processing Time Over Time", fontsize=24)
    axis.set_xlabel(
        "Execution time (hours)" if use_hours else "Execution time (minutes)",
        fontsize=22,
    )
    axis.set_ylabel("Post-processing time (seconds)", fontsize=22)
    axis.set_xlim(0, maximum_minutes / scale)
    axis.set_ylim(0, max(max(values) for _, _, values in series) * 1.05)
    axis.xaxis.set_major_locator(MultipleLocator(1 if use_hours else 10))
    axis.tick_params(labelsize=20)
    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=20)
    figure.tight_layout()

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output)
    plt.close(figure)
    print(f"Saved standalone figure to {arguments.output.resolve()}")


if __name__ == "__main__":
    main()
