"""Create a standalone bug-groups-and-single-bugs-over-time figure.

Usage:
    python bug_groups_and_single_bugs_over_time.py LQC_DIR

``LQC_DIR`` must contain Layout QuickCheck ``run_summary_<seconds>s.json``
snapshots with ``bug_group_count`` and ``single_bug_count`` fields.

Optional parameters:
    --output PATH
        Output PNG path. Defaults to
        ``figures/bug_groups_and_single_bugs_over_time.png``.
    --max-minutes MINUTES
        Ignore snapshots after this execution time.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "figures" / "bug_groups_and_single_bugs_over_time.png"


def load_snapshots(
    directory: Path, max_minutes: float | None = None
) -> list[tuple[float, int, int]]:
    snapshots = []
    for path in directory.glob("run_summary_*s.json"):
        match = SNAPSHOT_PATTERN.match(path.name)
        if not match or int(match.group(1)) % 60:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            elapsed_minutes = int(match.group(1)) / 60
            if max_minutes is not None and elapsed_minutes > max_minutes:
                continue
            snapshots.append(
                (
                    elapsed_minutes / 60,
                    int(data["bug_group_count"]),
                    int(data["single_bug_count"]),
                )
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"Invalid Layout QuickCheck snapshot: {path}: {error}") from error
    if not snapshots:
        raise SystemExit(f"No usable Layout QuickCheck snapshots found in {directory}")
    return sorted(snapshots)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lqc_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-minutes", type=float)
    arguments = parser.parse_args()
    snapshots = load_snapshots(arguments.lqc_dir, arguments.max_minutes)
    elapsed_hours, group_counts, single_counts = zip(*snapshots)

    figure, axis = plt.subplots(figsize=(11, 6), dpi=140)
    axis.plot(elapsed_hours, group_counts, marker="o", linewidth=2, label="Bug groups")
    axis.plot(elapsed_hours, single_counts, marker="o", linewidth=2, label="Single bugs")
    axis.set_title("Bug Groups and Single Bugs Over Time", fontsize=24)
    axis.set_xlabel("Execution time (hours)", fontsize=22)
    axis.set_ylabel("Count", fontsize=22)
    axis.set_xlim(0, max(elapsed_hours))
    axis.set_ylim(0, max(max(group_counts), max(single_counts)) + 2)
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
