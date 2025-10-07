#!/usr/bin/env python3

import sys, traceback, argparse
from lqc.config.config import Config, parse_config
from lqc.generate.html_file_generator import remove_file
from lqc.generate.style_log_generator import generate_run_subject
from lqc.minify.minify_test_file import MinifyStepFactory
from lqc.model.constants import BugType
from lqc_selenium.report.bug_report_helper import save_bug_report
from lqc.util.counter import Counter
from lqc.generate.web_page.create import save_as_web_page

from lqc_selenium.variants.variant_tester import test_variants
from lqc_selenium.variants.variants import TargetBrowser, getTargetVariant
from lqc_selenium.selenium_harness.layout_tester import test_combination
import pickle
import inspect, lqc.model.run_subject as rsmod
import os, uuid, pickle, re
from bs4 import BeautifulSoup


def save_subject(run_subject, stage):
    os.makedirs("pickles", exist_ok=True)
    fn = f"pickles/run_subject_{stage}_{uuid.uuid4().hex}.pkl"
    with open(fn, "wb") as f:
        pickle.dump(run_subject, f)
    return fn

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
    folder = "testminify"
    idx = _next_html_index(folder)
    pickle_addre = save_subject(run_subject, "pre")
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
    return (run_subject, run_result, pickle_addre)

from bs4 import BeautifulSoup

def _visible_contents(parent):
    out = []
    for c in parent.contents:
        if isinstance(c, str):
            if c.strip():
                out.append(c)
        else:
            out.append(c)
    return out

def _node_matches(node, spec):
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

def check_pattern_in_file(filename, pattern):
    with open(filename, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    bodies = soup.find_all("body")
    for body in bodies:
        contents = _visible_contents(body)
        n, m = len(contents), len(pattern)
        if m == 0:
            continue
        for i in range(0, n - m + 1):
            ok = True
            for j in range(m):
                if not _node_matches(contents[i + j], pattern[j]):
                    ok = False
                    break
            if ok:
                return True
    return False


def minify(target_browser, run_subject):
    pickle_addre= save_subject(run_subject, "pre")
    save_as_web_page(run_subject, "test_pre.html")
    patternFound= check_pattern_in_file("test_pre.html", ["text", "div"])
    print("Minifying...")
    stepsFactory = MinifyStepFactory()

    # Keep applying minimization steps until no more are available
    while True:
        # Get the next candidate minimized version of run_subject
        temp_run_subject = stepsFactory.next_minimization_step(run_subject)
        # If there are no more steps, exit the loop
        if temp_run_subject is None:
            print("No more minimization steps available.")
            break

        # Test the proposed minimized subject in the target browser
        run_result, *_ = test_combination(target_browser.getDriver(), temp_run_subject)

        # If the minimized subject still triggers the bug, accept it as the new subject
        if run_result.isBug():
            run_subject = temp_run_subject

    run_result, _ = test_combination(target_browser.getDriver(), run_subject)
    print("Minifying done.")
    return (run_subject, run_result,pickle_addre, patternFound)



def find_bugs(counter):

    target_browser = TargetBrowser()

    while counter.should_continue():

        # Stage 1 - Generate & Test
        run_subject = generate_run_subject()
        (run_result, test_filepath) = test_combination(target_browser.getDriver(), run_subject, keep_file=True)
        
        if not run_result.isBug():
            counter.incSuccess()

        else:
            # Stage 2 - Minifying Bug
            if run_result.type == BugType.PAGE_CRASH:
                print("Found a page that crashes. Minifying...")
                
            else:
                print("Found bug. Minifying...")

            (minified_run_subject, minified_run_result,pickle_addre, patternFound) = minify(target_browser, run_subject)

            # False Positive Detection
            if not minified_run_result.isBug():
                print("False positive (could not reproduce)")
                counter.incNoRepro()
            elif minified_run_result.type == BugType.LAYOUT and len(minified_run_subject.modified_styles.map) == 0:
                print("False positive (no modified styles)")
                counter.incNoMod()

            else:
                counter.incError()

                # Stage 3 - Test Variants
                print("Minified bug. Testing variants...")
                variants = test_variants(minified_run_subject)
                if patternFound:
                    print(f"PATTERN FOUND: {patternFound}")
                print("Variants tested. Saving bug report...")
                url = save_bug_report(
                    variants,
                    minified_run_subject,
                    minified_run_result,
                    test_filepath,
                    pickle_addre,
                    patternFound
                )
                print(url)

        counter.incTests()
        output = counter.getStatusString()
        if output:
            print(output)

        # Clean Up
        remove_file(test_filepath)


DEFAULT_CONFIG_FILE = "./config/config-initial.json"

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


