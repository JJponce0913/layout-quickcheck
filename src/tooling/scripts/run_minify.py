import argparse
import os
import pickle
import sys
import uuid

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lqc.config.config import Config, parse_config
from lqc.generate.html_file_generator import remove_file
from lqc.generate.web_page.create import save_as_web_page
from lqc.model.constants import BugType
from lqc_selenium.report.bug_report_helper import save_bug_report
from lqc_selenium.runner import minify
from lqc_selenium.selenium_harness.layout_tester import test_combination
from lqc_selenium.variants.variant_tester import test_variants
from lqc_selenium.variants.variants import TargetBrowser

DEFAULT_CONFIG_FILE = "./config/change.json"

"""
Loads a saved run_subject pickle, replays it through the minification process,
tests the result, and saves debugging artifacts for inspection.

This script is useful for reproducing and debugging a previously saved
run_subject outside the full generation pipeline. It renders the input as HTML,
runs it through the Selenium test flow, minifies the result, and if the bug is
still reproducible, tests variants and saves a bug report.

Usage
-----
python src/tooling/scripts/run_minify.py --pickle path/to/run_subject.pkl --config ./config/change.json

Arguments
---------
--pickle
    Path to the pickled run_subject file to replay and minify.

--config
    Path to the config file to use. Defaults to ./config/change.json.

Output
------
Creates a debug output folder under bug_reports/debug_minify_runs containing
a summary file, rendered HTML, and any generated bug report artifacts.
"""

def write_summary(summary_path, text):
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def run_minify_test(pickle_path, config_file=DEFAULT_CONFIG_FILE):
    run_id = uuid.uuid4().hex[:10]
    out_dir = os.path.join("bug_reports", "debug_minify_runs", f"run-{run_id}")
    os.makedirs(out_dir, exist_ok=True)
    summary_path = os.path.join(out_dir, "summary.txt")

    write_summary(summary_path, f"run_id: {run_id}")
    write_summary(summary_path, f"pickle_file: {pickle_path}")
    write_summary(summary_path, f"config_file: {config_file}")
    write_summary(summary_path, "")

    print(f"Using config file {config_file}")
    conf = parse_config(config_file)
    Config(conf)

    with open(pickle_path, "rb") as f:
        run_subject = pickle.load(f)

    print(f"Loaded run_subject from {pickle_path}")
    write_summary(summary_path, "loaded run_subject pickle")

    test_html_path = os.path.join(out_dir, "test.html")
    save_as_web_page(run_subject, test_html_path)
    write_summary(summary_path, f"wrote test html: {test_html_path}")

    target_browser = TargetBrowser()
    run_result, test_filepath = test_combination(
        target_browser.getDriver(), run_subject, keep_file=True
    )

    print(f"Tested {test_filepath}")
    write_summary(summary_path, f"selenium test file: {test_filepath}")
    write_summary(summary_path, f"initial result type: {getattr(run_result, 'type', None)}")
    write_summary(
        summary_path,
        f"initial isBug: {run_result.isBug() if hasattr(run_result, 'isBug') else None}",
    )

    if run_result.type == BugType.PAGE_CRASH:
        print("Found a page that crashes. Minifying...")
        write_summary(summary_path, "initial finding: page crash")
    else:
        print("Found bug. Minifying...")
        write_summary(summary_path, "initial finding: bug (non crash)")

    minified_run_subject, minified_run_result, pre_pickle_path, should_skip = minify(
        target_browser, run_subject
    )

    write_summary(summary_path, "")
    write_summary(summary_path, "minify result")
    write_summary(summary_path, f"pre_pickle: {pre_pickle_path}")
    write_summary(
        summary_path,
        f"minified result type: {getattr(minified_run_result, 'type', None)}",
    )
    write_summary(
        summary_path,
        f"minified isBug: {minified_run_result.isBug() if hasattr(minified_run_result, 'isBug') else None}",
    )
    write_summary(
        summary_path,
        f"minified modified_styles count: {len(minified_run_subject.modified_styles.map) if hasattr(minified_run_subject, 'modified_styles') else None}",
    )

    if not minified_run_result.isBug():
        print("False positive (could not reproduce)")
        write_summary(summary_path, "final status: false positive (could not reproduce)")
    elif (
        minified_run_result.type == BugType.LAYOUT
        and len(minified_run_subject.modified_styles.map) == 0
    ):
        print("False positive (no modified styles)")
        write_summary(summary_path, "final status: false positive (no modified styles)")
    else:
        print("Minified bug. Testing variants...")
        write_summary(summary_path, "final status: minified bug reproduced")

        variants = test_variants(minified_run_subject)
        write_summary(summary_path, "variants tested")

        print("Variants tested. Saving bug report...")
        url = save_bug_report(
            variants,
            minified_run_subject,
            minified_run_result,
            test_filepath,
            pre_pickle_path,
            should_skip,
        )
        print(url)
        write_summary(summary_path, f"bug report url: {url}")

    try:
        remove_file(test_filepath)
        write_summary(summary_path, f"removed temp file: {test_filepath}")
    except Exception as e:
        write_summary(summary_path, f"failed to remove temp file: {test_filepath}")
        write_summary(summary_path, f"remove error: {repr(e)}")

    write_summary(summary_path, "")
    write_summary(summary_path, f"outputs saved in: {out_dir}")

    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--pickle", required=True, help="Path to run_subject pickle file")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help="Path to config file",
    )

    args = parser.parse_args()

    run_minify_test(args.pickle, args.config)
