#!/usr/bin/env python3

from datetime import datetime
import json
import os


DEFAULT_RUN_SUMMARY_PATH = os.path.join(
    "bug_reports", "tester", "sort-repo", "run_summary.json"
)

NUMERIC_SUMMARY_KEYS = {
    "tests_run",
    "passed",
    "bugs_found",
    "cant_reproduce",
    "bugs_with_no_modified_styles",
    "crashes",
    "bug_group_count",
    "single_bug_count",
    "grouped_bug_instance_count",
    "total_bug_directories",
    "runtime_seconds",
    "minify_seconds",
}


def _default_summary(summary_path=DEFAULT_RUN_SUMMARY_PATH):
    target_root = os.path.abspath(os.path.dirname(summary_path))
    return {
        "updated_at": datetime.now().isoformat(),
        "target_root": target_root,
        "tests_run": 0,
        "passed": 0,
        "bugs_found": 0,
        "cant_reproduce": 0,
        "bugs_with_no_modified_styles": 0,
        "crashes": 0,
        "bug_group_count": 0,
        "single_bug_count": 0,
        "grouped_bug_instance_count": 0,
        "total_bug_directories": 0,
        "runtime_seconds": 0.0,
        "minify_seconds": 0.0,
        "bug_groups": [],
        "single_bugs": [],
    }


def read_run_summary(summary_path=DEFAULT_RUN_SUMMARY_PATH):
    if not os.path.isfile(summary_path):
        return _default_summary(summary_path)

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_summary(summary_path)

    summary = _default_summary(summary_path)
    summary.update(data if isinstance(data, dict) else {})
    return summary


def write_run_summary(summary, summary_path=DEFAULT_RUN_SUMMARY_PATH):
    payload = _default_summary(summary_path)
    payload.update(summary if isinstance(summary, dict) else {})
    payload["updated_at"] = datetime.now().isoformat()
    payload["target_root"] = os.path.abspath(os.path.dirname(summary_path))

    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return summary_path


def item_add(item, amount=1, summary_path=DEFAULT_RUN_SUMMARY_PATH):
    summary = read_run_summary(summary_path)

    if item not in NUMERIC_SUMMARY_KEYS:
        raise ValueError(f"item_add only supports numeric summary keys. Got: {item}")

    current = summary.get(item, 0)
    if not isinstance(current, (int, float)):
        raise TypeError(f"Summary item '{item}' is not numeric.")
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric.")

    summary[item] = current + amount
    write_run_summary(summary, summary_path)
    return summary[item]


def item_set(item, value, summary_path=DEFAULT_RUN_SUMMARY_PATH):
    summary = read_run_summary(summary_path)
    summary[item] = value
    write_run_summary(summary, summary_path)
    return value


def item_get(item, default=None, summary_path=DEFAULT_RUN_SUMMARY_PATH):
    summary = read_run_summary(summary_path)
    return summary.get(item, default)
