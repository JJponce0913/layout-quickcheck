#!/usr/bin/env python3

import argparse
import ast
from contextlib import redirect_stdout
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
from tooling.rule_engine import should_skip, sort_single_bug


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
    all_rules = []

    if not os.path.isdir(source_root):
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump({"rules": []}, f, indent=2)
        return output_json_path, all_rules

    for root, _, files in os.walk(source_root):
        if "merged_tree.txt" not in files:
            continue

        group_name = os.path.basename(root)
        if not group_name.startswith("bug-group-"):
            continue

        merged_tree_path = os.path.join(root, "merged_tree.txt")
        try:
            with open(merged_tree_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        extracted = _extract_generated_rules_from_text(content)
        for rule in extracted:
            all_rules.append(
                {
                    "bug_group": os.path.relpath(root, source_root),
                    "merged_tree_path": merged_tree_path.replace("\\", "/"),
                    "rule": rule,
                }
            )

    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump({"rules": all_rules}, f, indent=2)

    return output_json_path, [entry["rule"] for entry in all_rules]




def minify(target_browser, run_subject):
    prerun_subject = run_subject
    conf = Config()
    print(conf.getRules(),"\n")
    _, rules = extract_bug_group_rules_to_json(
        source_root="bug_reports/sort-repo",
        output_json_path="bug_reports/sort-repo/rules.json",
    )
    if not rules:
        rules = conf.getRules()
    print(rules,"\n")
    with redirect_stdout(io.StringIO()):
        shouldSkip, rule_name = should_skip(run_subject, rules)

    #Skipe minimization if shouldSkip is True
    if shouldSkip:
        run_result, _ = test_combination(target_browser.getDriver(), run_subject)
        return (run_subject, run_result, prerun_subject, shouldSkip, rule_name) 

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
    return (run_subject, run_result,prerun_subject, shouldSkip, rule_name)



def find_bugs(counter):
    target_browser = TargetBrowser()
    safe_dir = "bug_reports/safe"
    os.makedirs(safe_dir, exist_ok=True)

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
            (minified_run_subject, minified_run_result, prerun_subject, shouldSkip, rule_name) = minify(target_browser, prerun_subject)
            print(f"Skip rule: {'skipped' if shouldSkip else 'not skipped'}")
            print(f"Rule name: {rule_name}")
            if shouldSkip:
                save_bug_report_custom(
                    variants=[],
                    minified_run_subject=None,
                    run_result=minified_run_result,
                    original_filepath=test_filepath,
                    prerun_subject=prerun_subject,
                    shouldSkip=shouldSkip,
                    folder_name="sort-repo",
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
                    folder_name="sort-repo",
                    shouldSkip=shouldSkip,
                    rule_name=rule_name,
                )
                print(f"Bug report saved: {url}")

        counter.incTests()
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

    if counter.num_crash > 0:
        print(f"Number of crashes: {counter.num_crash}\nCrash Errors:\n")
        for exc in counter.crash_exceptions:
            traceback.print_exception(exc["etype"], exc["value"], exc["traceback"])
            print("-"*60 + "\n")

