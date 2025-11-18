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

def check_pattern(filename, pattern):
    with open(filename, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    bodies = soup.find_all("body")
    for body in bodies:
        contents = visible_contents(body)
        n, m = len(contents), len(pattern)
        if m == 0:
            continue
        for i in range(0, n - m + 1):
            ok = True
            for j in range(m):
                if not node_matches(contents[i + j], pattern[j]):
                    ok = False
                    break
            if ok:
                return True
    return False


def check_style(html_path, prop, value):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.I | re.S)
    js = "\n".join(scripts)
    m = re.search(r"function\s+makeStyleChanges\s*\(\s*\)\s*\{(.*?)\}", js, flags=re.S)
    if not m:
        return False
    body = m.group(1)
    prop_esc = re.escape(prop)
    value_esc = re.escape(value)
    bracket_pat = rf"\.style\[\s*['\"]{prop_esc}['\"]\s*\]\s*=\s*['\"]{value_esc}['\"]\s*;"
    dot_pat = rf"\.style\.\s*{prop_esc}\s*=\s*['\"]{value_esc}['\"]\s*;"
    return re.search(bracket_pat, body) is not None or re.search(dot_pat, body) is not None

count_summary = {
    "pattern_and_style": 0,
    "pattern_only": 0,
    "style_only": 0,
    "none": 0
}

count_summary = {"pattern_and_style": 0, "pattern_only": 0, "style_only": 0, "none": 0}

def should_skip(file):
    any_match = False
    conf = Config()
    rules = conf.getRules()
    for rule in rules:
        # Get rule class details
        html_pat = rule.get("html_pattern", [])
        styles = rule.get("style", [])

        # Check HTML pattern
        patternFound = check_pattern(file, html_pat)
        
        # Check styles
        styleFound = False
        for prop, values in styles:
            vals = values if isinstance(values, list) else [values]
            for v in vals:
                if check_style(file, prop, v):
                    styleFound = True
                    break
            if styleFound:
                break
        
        # Update count summary
        if patternFound and styleFound:
            count_summary["pattern_and_style"] += 1
            any_match = True
        elif patternFound and not styleFound:
            count_summary["pattern_only"] += 1
        elif not patternFound and styleFound:
            count_summary["style_only"] += 1
        else:
            count_summary["none"] += 1
        print(f"Rule={rule.get('name','')}, Pattern found: {patternFound}, Style found: {styleFound}")

        
    return any_match



def minify(target_browser, run_subject):
    pickle_subject= run_subject
    #Return True if pattern found, else False
    shouldSkip = should_skip("test_pre.html")
    
    print(count_summary)
    
    #more runs
    #fewer bugs
    #more good bugs
    if shouldSkip:
        run_result, _ = test_combination(target_browser.getDriver(), run_subject)
        return (run_subject, run_result, pickle_subject, shouldSkip)

    #print("Minifying...")
    stepsFactory = MinifyStepFactory()

    # Keep applying minimization steps until no more are available
    while True:
        # Get the next candidate minimized version of run_subject
        temp_run_subject = stepsFactory.next_minimization_step(run_subject)
        # If there are no more steps, exit the loop
        if temp_run_subject is None:
            #print("No more minimization steps available.")
            break

        # Test the proposed minimized subject in the target browser
        run_result, *_ = test_combination(target_browser.getDriver(), temp_run_subject)

        # If the minimized subject still triggers the bug, accept it as the new subject
        if run_result.isBug():
            run_subject = temp_run_subject

    run_result, _ = test_combination(target_browser.getDriver(), run_subject)
    #print("Minifying done.")
    return (run_subject, run_result,pickle_subject, shouldSkip)



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

            (minified_run_subject, minified_run_result,pickle_subject, shouldSkip) = minify(target_browser, run_subject)

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
                if shouldSkip:
                    print(f"PATTERN FOUND: {shouldSkip}")
                print("Variants tested. Saving bug report...")
                url = save_bug_report(
                    variants,
                    minified_run_subject,
                    minified_run_result,
                    test_filepath,
                    pickle_subject,
                    shouldSkip
                )
                print(url)

        counter.incTests()
        output = counter.getStatusString()
        if output:
            print(output)

        # Clean Up
        remove_file(test_filepath)


DEFAULT_CONFIG_FILE = "./config/local/config-initial-chrome.json"

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


