#!/usr/bin/env python3

from datetime import datetime
import json
import os
from time import sleep


DEFAULT_RUN_SUMMARY_PATH = os.path.join(
    "bug_reports", "tester", "run_summary.json"
)
BUG_SNAPSHOT_INTERVAL = 10
RUNTIME_SECONDS_SNAPSHOT_INTERVAL = 60
SUMMARY_WRITE_RETRIES = 20
SUMMARY_WRITE_RETRY_SECONDS = 0.25

NUMERIC_SUMMARY_KEYS = {
    "tests_run",
    "passed",
    "bugs_found",
    "success_rate",
    "cant_reproduce",
    "bugs_with_no_modified_styles",
    "crashes",
    "bug_group_count",
    "single_bug_count",
    "grouped_bug_instance_count",
    "total_bug_directories",
    "runtime_seconds",
    "minify_seconds",
    "sorting_seconds",
    "true_minification_seconds",
}


def _default_summary(summary_path=DEFAULT_RUN_SUMMARY_PATH):
    target_root = os.path.abspath(os.path.dirname(summary_path))
    return {
        "updated_at": datetime.now().isoformat(),
        "target_root": target_root,
        "tests_run": 0,
        "passed": 0,
        "bugs_found": 0,
        "success_rate": 0.0,
        "cant_reproduce": 0,
        "bugs_with_no_modified_styles": 0,
        "crashes": 0,
        "bug_group_count": 0,
        "single_bug_count": 0,
        "grouped_bug_instance_count": 0,
        "total_bug_directories": 0,
        "runtime_seconds": 0.0,
        "minify_seconds": 0.0,
        "sorting_seconds": 0.0,
        "true_minification_seconds": 0.0,
        "bug_groups": [],
        "single_bugs": [],
    }


def _with_computed_fields(summary):
    tests_run = int(summary.get("tests_run", 0) or 0)
    bugs_found = int(summary.get("bugs_found", 0) or 0)
    summary["success_rate"] = round(bugs_found / tests_run, 6) if tests_run else 0.0
    return summary


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
    return _with_computed_fields(summary)


def _write_summary_snapshot_once(payload, summary_path, snapshot_name):
    snapshot_path = os.path.join(os.path.dirname(summary_path), snapshot_name)
    if os.path.exists(snapshot_path):
        return

    _write_json_with_retries(snapshot_path, payload)


def _write_json_with_retries(path, payload):
    for attempt in range(SUMMARY_WRITE_RETRIES):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return
        except PermissionError:
            if attempt == SUMMARY_WRITE_RETRIES - 1:
                raise
            sleep(SUMMARY_WRITE_RETRY_SECONDS)


def _write_threshold_snapshots(payload, summary_path):
    bugs_found = int(payload.get("bugs_found", 0) or 0)
    max_bug_snapshot = (bugs_found // BUG_SNAPSHOT_INTERVAL) * BUG_SNAPSHOT_INTERVAL
    for bug_count in range(BUG_SNAPSHOT_INTERVAL, max_bug_snapshot + 1, BUG_SNAPSHOT_INTERVAL):
        _write_summary_snapshot_once(
            payload,
            summary_path,
            f"run_summary_{bug_count}_bugs.json",
        )

    runtime_seconds = float(payload.get("runtime_seconds", 0.0) or 0.0)
    max_runtime_snapshot = (
        int(runtime_seconds) // RUNTIME_SECONDS_SNAPSHOT_INTERVAL
    ) * RUNTIME_SECONDS_SNAPSHOT_INTERVAL
    for runtime_second in range(
        RUNTIME_SECONDS_SNAPSHOT_INTERVAL,
        max_runtime_snapshot + 1,
        RUNTIME_SECONDS_SNAPSHOT_INTERVAL,
    ):
        _write_summary_snapshot_once(
            payload,
            summary_path,
            f"run_summary_{runtime_second}s.json",
        )


def write_run_summary(summary, summary_path=DEFAULT_RUN_SUMMARY_PATH):
    payload = _default_summary(summary_path)
    payload.update(summary if isinstance(summary, dict) else {})
    payload["updated_at"] = datetime.now().isoformat()
    payload["target_root"] = os.path.abspath(os.path.dirname(summary_path))
    _with_computed_fields(payload)

    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    _write_json_with_retries(summary_path, payload)
    _write_threshold_snapshots(payload, summary_path)

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
