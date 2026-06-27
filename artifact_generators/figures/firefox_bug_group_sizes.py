"""Create a standalone Firefox bug-group-size figure.

Usage:
    python firefox_bug_group_sizes.py LQC_DIR

``LQC_DIR`` must be a Layout QuickCheck directory containing ``bug-group-*``
and optionally ungrouped ``bug-*`` directories.

Optional parameters:
    --output PATH
        Output PNG path. Defaults to ``figures/firefox_bug_group_sizes.png``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "figures" / "firefox_bug_group_sizes.png"


def collect_groups(directory: Path) -> list[tuple[str, int]]:
    if not directory.is_dir():
        raise SystemExit(f"Layout QuickCheck directory not found: {directory}")
    groups = [
        (
            group.name,
            sum(
                child.is_dir() and child.name.startswith("bug-")
                for child in group.iterdir()
            ),
        )
        for group in directory.glob("bug-group-*")
        if group.is_dir()
    ]
    single_count = sum(
        child.is_dir()
        and child.name.startswith("bug-")
        and not child.name.startswith("bug-group-")
        for child in directory.iterdir()
    )
    if single_count:
        groups.append(("Single bugs", single_count))
    if not groups:
        raise SystemExit(f"No bug reports found in {directory}")
    return sorted(groups, key=lambda item: (-item[1], item[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lqc_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    groups = collect_groups(arguments.lqc_dir)
    names, counts = zip(*groups)

    figure, axis = plt.subplots(figsize=(max(12, len(groups) * 0.32), 7), dpi=140)
    positions = range(len(groups))
    axis.bar(positions, counts, color="#2563eb")
    axis.set_xticks(list(positions), labels=names, rotation=60, ha="right")
    axis.set_ylabel("Bug instances")
    axis.set_title("Firefox Bug-Group Sizes")
    axis.grid(axis="y", alpha=0.3)
    axis.set_axisbelow(True)
    largest = max(counts)
    axis.set_ylim(0, largest * 1.12)
    for position, count in zip(positions, counts):
        axis.text(position, count + largest * 0.01, str(count), ha="center", fontweight="bold")
    figure.tight_layout()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output)
    plt.close(figure)
    print(f"Saved standalone figure to {arguments.output.resolve()}")


if __name__ == "__main__":
    main()
