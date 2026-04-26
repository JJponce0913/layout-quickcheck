#!/usr/bin/env python3

import argparse
import sys
import traceback

from lqc.config.config import Config, parse_config
from lqc.generate.html_file_generator import remove_file
from lqc.generate.style_log_generator import generate_run_subject
from lqc.minify.minify_test_file import MinifyStepFactory
from lqc.model.constants import BugType
from lqc.util.counter import Counter
from lqc_selenium.report.bug_report_helper import save_bug_report
from lqc_selenium.selenium_harness.layout_tester import test_combination
from lqc_selenium.variants.variant_tester import test_variants
from lqc_selenium.variants.variants import TargetBrowser, getTargetVariant
from lqc.rules.rule_engine import should_skip


def minify(target_browser, run_subject):
    # Copy the original subject before minifying so we can return both versions
    conf = Config()
    rules = conf.getRules()

    shouldSkip = should_skip(run_subject, rules)

    # Skip minimization if shouldSkip is True
    if shouldSkip:
        run_result, _ = test_combination(target_browser.getDriver(), run_subject)
        return (run_subject, run_result, shouldSkip) 

    stepsFactory = MinifyStepFactory()
    # Keep applying minimization steps until no more are available
    while True:
        # Get the next candidate minimized version of run_subject
        proposed_run_subject = stepsFactory.next_minimization_step(run_subject)
        # If there are no more steps, exit the loop
        if proposed_run_subject is None:
            # Break out when minimization can't shrink the subject further
            break

        # Test the proposed minimized subject in the target browser
        run_result, *_ = test_combination(target_browser.getDriver(), proposed_run_subject)

        # If the minimized subject still triggers the bug, accept it as the new subject
        if run_result.isBug():
            run_subject = proposed_run_subject

    # Create final representations of minified files
    run_result, _ = test_combination(target_browser.getDriver(), run_subject)
    # Return the minimized subject, result, original pre-minimized subject, and skip flag
    return (run_subject, run_result, shouldSkip)



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
                
            (minified_run_subject, minified_run_result, shouldSkip) = minify(target_browser, run_subject)
            print(f"Skip rule: {'skipped' if shouldSkip else 'not skipped'}")

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
                url = save_bug_report(
                    variants,
                    minified_run_subject,
                    minified_run_result,
                    test_filepath,
                    run_subject,
                    shouldSkip
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

