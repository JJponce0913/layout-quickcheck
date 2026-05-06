#!/usr/bin/env python3

import argparse
import ast
from contextlib import redirect_stdout
from datetime import datetime
import io
import json
import os
import pickle
import re
import sys
from time import time
import traceback

from lqc.config.config import Config, parse_config
from lqc.generate.html_file_generator import remove_file
from lqc.generate.style_log_generator import generate_run_subject
from lqc.generate.web_page.create import save_as_web_page
from lqc.minify.minify_test_file import MinifyStepFactory
from lqc.model.constants import BugType
from lqc.util.counter import Counter
from lqc_selenium.report.bug_report_helper import save_bug_report, save_bug_report_custom
from lqc_selenium.selenium_harness.layout_tester import test_combination
from lqc_selenium.variants.variant_tester import test_variants
from lqc_selenium.variants.variants import TargetBrowser, getTargetVariant
from lqc_selenium.api import write_run_summary as write_run_summary_file
from tooling.rule_engine import should_skip, sort_single_bug

VERBOSE = False
RUN_SUMMARY_ROOT = "bug_reports/tester/sort-repo"


def write_run_summary(counter, target_root=RUN_SUMMARY_ROOT):
    os.makedirs(target_root, exist_ok=True)

    group_dirs = []
    single_bug_dirs = []
    grouped_bug_instances = 0

    for entry in os.listdir(target_root):
        entry_path = os.path.join(target_root, entry)
        if not os.path.isdir(entry_path):
            continue

        if entry.startswith("bug-group-"):
            group_dirs.append(entry)
            grouped_bug_instances += sum(
                1
                for child in os.listdir(entry_path)
                if os.path.isdir(os.path.join(entry_path, child)) and child.startswith("bug-")
            )
        elif entry.startswith("bug-"):
            single_bug_dirs.append(entry)

    summary = {
        "updated_at": datetime.now().isoformat(),
        "target_root": os.path.abspath(target_root),
        "tests_run": counter.num_tests,
        "passed": counter.num_successful,
        "bugs_found": counter.num_error,
        "cant_reproduce": counter.num_cant_reproduce,
        "bugs_with_no_modified_styles": counter.num_no_mod_styles_bugs,
        "crashes": counter.num_crash,
        "bug_group_count": len(group_dirs),
        "single_bug_count": len(single_bug_dirs),
        "grouped_bug_instance_count": grouped_bug_instances,
        "total_bug_directories": len(single_bug_dirs) + grouped_bug_instances,
        "bug_groups": sorted(group_dirs),
        "single_bugs": sorted(single_bug_dirs),
        "runtime_seconds": round(counter.getRuntimeSeconds(), 3),
        "minify_seconds": round(counter.total_minify_seconds, 3),
    }

    summary_path = os.path.join(target_root, "run_summary.json")
    write_run_summary_file(summary, summary_path=summary_path)
    return summary_path


def _ensure_dir(d):
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def _next_html_index(d):
    _ensure_dir(d)
    nums = []
    pat = re.compile(r"^(\d+)\.html$")
    for f in os.listdir(d):
        m = pat.match(f)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 0

def _save_step_html(run_subject, folder, idx):
    path = os.path.join(folder, f"{idx:06d}.html")
    save_as_web_page(run_subject, path)
    return idx + 1

def minify_debug(target_browser, run_subject):
    folder = "tmp_generated_files/debug"
    idx = _next_html_index(folder)
    pickle_addr = f"{folder}/pre.pkl"
    with open(pickle_addr, "wb") as f:
        pickle.dump(run_subject, f)

    print(f"STEP {idx:06d} PRE")
    idx = _save_step_html(run_subject, folder, idx)
    print("Minifying...")
    stepsFactory = MinifyStepFactory()
    while True:
        proposed_run_subject = stepsFactory.next_minimization_step(run_subject)
        if proposed_run_subject is None:
            break
        print(f"STEP {idx:06d} PROPOSED")
        idx = _save_step_html(proposed_run_subject, folder, idx)
        run_result, *_ = test_combination(target_browser.getDriver(), proposed_run_subject)
        state = "BUG" if run_result.isBug() else "PASS"
        print(f"STEP {idx-1:06d} RESULT {state}")
        if run_result.isBug():
            run_subject = proposed_run_subject
            print(f"STEP {idx:06d} ACCEPTED")
            idx = _save_step_html(run_subject, folder, idx)
        else:
            print(f"STEP {idx:06d} REJECTED")
    run_result, _ = test_combination(target_browser.getDriver(), run_subject)
    print(f"STEP {idx:06d} FINAL")
    idx = _save_step_html(run_subject, folder, idx)
    print("Minifying done.")
    return (run_subject, run_result, pickle_addr)

def visible_contents(parent):
    out = []
    for c in parent.contents:
        if isinstance(c, str):
            if c.strip():
                out.append(c)
        else:
            out.append(c)
    return out

def node_matches(node, spec):
    if spec == "text":
        return isinstance(node, str) and bool(node.strip())
    if isinstance(spec, str):
        return getattr(node, "name", None) == spec
    if isinstance(spec, dict):
        tag = spec.get("tag")
        attrs = spec.get("attrs", {})
        if tag and getattr(node, "name", None) != tag:
            return False
        for k, v in attrs.items():
            if node.get(k) != v:
                return False
        return True
    return False


def _extract_generated_rules_from_text(content):
    rules = []
    marker = "Generated Rule:"
    start = 0

    while True:
        marker_idx = content.find(marker, start)
        if marker_idx == -1:
            break

        tail = content[marker_idx + len(marker):].lstrip()
        if not tail.startswith("{"):
            start = marker_idx + len(marker)
            continue

        depth = 0
        end_idx = None
        for i, ch in enumerate(tail):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        if end_idx is None:
            start = marker_idx + len(marker)
            continue

        try:
            parsed = ast.literal_eval(tail[:end_idx])
            if isinstance(parsed, dict):
                rules.append(parsed)
        except (SyntaxError, ValueError):
            pass

        start = marker_idx + len(marker)

    return rules


def extract_bug_group_rules_to_json(
    source_root="bug_reports/sort-repo",
    output_json_path="bug_reports/sort-repo/rules.json",
):
    print(f"Extracting rules from {source_root} to {output_json_path}...")
    all_rules = []
    bug_group_folder_count = 0

    if not os.path.isdir(source_root):
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump({"rules": []}, f, indent=2)
        print("Found 0 bug-group folders.")
        return output_json_path, all_rules

    for root, _, files in os.walk(source_root):
        group_name = os.path.basename(root)
        if not group_name.startswith("bug-group-"):
            continue
        bug_group_folder_count += 1

        if "extracted_rule.json" not in files:
            continue

        extracted_rule_path = os.path.join(root, "extracted_rule.json")
        try:
            with open(extracted_rule_path, "r", encoding="utf-8") as f:
                rule = json.load(f)
        except OSError:
            continue
        except json.JSONDecodeError:
            continue

        all_rules.append(
            {
                "bug_group": os.path.relpath(root, source_root),
                "merged_tree_path": extracted_rule_path.replace("\\", "/"),
                "rule": rule,
            }
        )

    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump({"rules": all_rules}, f, indent=2)

    print(f"Found {bug_group_folder_count} bug-group folders.")
    return output_json_path, [entry["rule"] for entry in all_rules]




def minify(target_browser, run_subject):
    prerun_subject = run_subject
    path,shouldSkip,rule_name = sort_single_bug(
        base_dir="bug_reports/tester/sort-repo",
        run_subject=run_subject,
        safe_dir="bug_reports/safe",
        verbose=VERBOSE,
    )
    print(f"Matching rule folder: {path}")
    
    #Skipe minimization if shouldSkip is True
    """ if shouldSkip:
        run_result, _ = test_combination(target_browser.getDriver(), run_subject)
        return (run_subject, run_result, prerun_subject, path,shouldSkip, rule_name)  """

    stepsFactory = MinifyStepFactory()

    # Keep applying minimization steps until no more are available
    while True:
        # Get the next candidate minimized version of run_subject
        temp_run_subject = stepsFactory.next_minimization_step(run_subject)
        # If there are no more steps, exit the loop
        if temp_run_subject is None:
            # Break out when minimization can't shrink the subject further
            break

        # Test the proposed minimized subject in the target browser
        run_result, *_ = test_combination(target_browser.getDriver(), temp_run_subject)

        # If the minimized subject still triggers the bug, accept it as the new subject
        if run_result.isBug():
            run_subject = temp_run_subject

    run_result, _ = test_combination(target_browser.getDriver(), run_subject)
    return (run_subject, run_result,prerun_subject, path,shouldSkip, rule_name)



def find_bugs(counter):
    target_browser = TargetBrowser()
    safe_dir = "bug_reports/safe"
    os.makedirs(safe_dir, exist_ok=True)
    write_run_summary(counter)

    def safe_count():
        return sum(
            1 for name in os.listdir(safe_dir)
            if name.endswith(".pkl")
        )

    while safe_count() < 50 and counter.should_continue():
        run_subject = generate_run_subject()
        run_result, test_filepath = test_combination(
            target_browser.getDriver(),
            run_subject,
            keep_file=True
        )

        if not run_result.isBug():
            print(f"Filling safe set: {safe_count() + 1}/50")
            pickle_addr = os.path.join(safe_dir, f"safe_{int(time() * 1000)}.pkl")
            with open(pickle_addr, "wb") as f:
                pickle.dump(run_subject, f)

        remove_file(test_filepath)
        counter.incTests()
        write_run_summary(counter)
        output = counter.getStatusString()
        if output:
            print(output)
            
    target_browser = TargetBrowser()

    while counter.should_continue():

        # Stage 1 - Generate & Test
        run_subject = generate_run_subject()
        (run_result, test_filepath) = test_combination(target_browser.getDriver(), run_subject, keep_file=True)
        
        if not run_result.isBug():
            counter.incSuccess()
        else:
            # Stage 2 - Minifying Bug
            print("Bug found. Minifying...")
            prerun_subject = run_subject
            minify_started_at = time()
            (minified_run_subject, minified_run_result, prerun_subject,path, shouldSkip, rule_name) = minify(target_browser, prerun_subject)
            minify_elapsed_seconds = time() - minify_started_at
            counter.addMinifyTime(minify_elapsed_seconds)
            print(
                f"Minify time: {minify_elapsed_seconds:.2f}s "
                f"(total {counter.total_minify_seconds:.2f}s)"
            )
            print(f"Skip rule: {'skipped' if shouldSkip else 'not skipped'}")
            print(f"Rule name: {rule_name}")
            # Save bug report that matches a rule 
            if shouldSkip:
                save_bug_report_custom(
                    variants=[],
                    minified_run_subject=None,
                    run_result=minified_run_result,
                    original_filepath=test_filepath,
                    prerun_subject=prerun_subject,
                    path=path,
                    shouldSkip=shouldSkip,
                    rule_name=rule_name
                )

            # False Positive Detection
            if not minified_run_result.isBug():
                print("Skipped: no repro after minify.")
                counter.incNoRepro()
            elif minified_run_result.type == BugType.LAYOUT and len(minified_run_subject.modified_styles.map) == 0:
                print("Skipped: no modified styles after minify.")
                counter.incNoMod()

            else:
                counter.incError()

                # Stage 3 - Test Variants
                variants = test_variants(minified_run_subject)
                
                url = save_bug_report_custom(
                    variants,
                    minified_run_subject,
                    minified_run_result,
                    test_filepath,
                    prerun_subject,
                    path=path,
                    shouldSkip=shouldSkip,
                    rule_name=rule_name,
                )
                print(f"Bug report saved: {url}")

        counter.incTests()
        write_run_summary(counter)
        output = counter.getStatusString()
        if output:
            print(output)

        # Clean Up
        remove_file(test_filepath)


DEFAULT_CONFIG_FILE = "./config/change.json"


if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""find bugs in browser layout calculation - run forever unless specified otherwise\n\nexamples: \n    compare.py -b 1         # Find one bug and quit \n    compare.py -t 2000      # Run 2000 tests and quit""")
    parser.add_argument("-v", "--verbose", help="increase output verbosity (repeatable argument -v, -vv, -vvv, -vvvv)", action="count", default=0)
    parser.add_argument("-b", "--bug-limit", help="quit after finding this many bugs", type=int, default=0)
    parser.add_argument("-t", "--test-limit", help="quit after running this many tests", type=int, default=0)
    parser.add_argument("-l", "--crash-limit", help="quit after crashing this many times", type=int, default=1)
    parser.add_argument("-c", "--config-file", help="path to config file to use", type=str, default=DEFAULT_CONFIG_FILE)
    args = parser.parse_args()
    
    # Initialize Config
    print(f"Using config file {args.config_file}")
    conf = parse_config(args.config_file)
    Config(conf)
    VERBOSE = args.verbose > 0

    # Logging - Target Variant
    target_variant = getTargetVariant()
    print(f"Using target variant \"{target_variant}\"")

    counter = Counter(bug_limit=args.bug_limit, test_limit=args.test_limit, crash_limit=args.crash_limit)

    while counter.should_continue():
        try:
            find_bugs(counter)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            exc = {
                "etype": exc_type,
                "value": exc_value,
                "traceback": exc_traceback,
            }
            counter.incCrash(exc=exc)
            write_run_summary(counter)

    write_run_summary(counter)

    if counter.num_crash > 0:
        print(f"Number of crashes: {counter.num_crash}\nCrash Errors:\n")
        for exc in counter.crash_exceptions:
            traceback.print_exception(exc["etype"], exc["value"], exc["traceback"])
            print("-"*60 + "\n")

