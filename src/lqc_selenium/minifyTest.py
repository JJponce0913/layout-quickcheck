import pickle
from lqc_selenium.runner import minify_debug
from lqc_selenium.variants.variants import TargetBrowser
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
import os, uuid, pickle
DEFAULT_CONFIG_FILE = "./config/config-initial.json"
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""find bugs in browser layout calculation - run forever unless specified otherwise\n\nexamples: \n    compare.py -b 1         # Find one bug and quit \n    compare.py -t 2000      # Run 2000 tests and quit""")
parser.add_argument("-v", "--verbose", help="increase output verbosity (repeatable argument -v, -vv, -vvv, -vvvv)", action="count", default=0)
parser.add_argument("-b", "--bug-limit", help="quit after finding this many bugs", type=int, default=0)
parser.add_argument("-t", "--test-limit", help="quit after running this many tests", type=int, default=0)
parser.add_argument("-l", "--crash-limit", help="quit after crashing this many times", type=int, default=1)
parser.add_argument("-c", "--config-file", help="path to config file to use", type=str, default=DEFAULT_CONFIG_FILE)
args = parser.parse_args()
print(f"Using config file {args.config_file}")
conf = parse_config(args.config_file)
Config(conf)
# Load the saved RunSubject
pickle_addre="bug_reports/Bugs/bug-report-2025-09-15-22-11-57-070081/run_subject_pre_58a665a7814c404e9bacb679323f5bf7.pkl"
with open(pickle_addre, "rb") as f:
    run_subject = pickle.load(f)
print(f"Loaded run_subject from {run_subject}")
save_as_web_page(run_subject, "test.html")
# Create a fresh target browser
target_browser = TargetBrowser()
(run_result, test_filepath) = test_combination(target_browser.getDriver(), run_subject, keep_file=True)
print(f"Tested {test_filepath}")


# Stage 2 - Minifying Bug
if run_result.type == BugType.PAGE_CRASH:
    print("Found a page that crashes. Minifying...")
else:
    print("Found bug. Minifying...")

(minified_run_subject, minified_run_result, pickle_addre) = minify_debug(target_browser, run_subject)

# False Positive Detection
if not minified_run_result.isBug():
    print("False positive (could not reproduce)")
elif minified_run_result.type == BugType.LAYOUT and len(minified_run_subject.modified_styles.map) == 0:
    print("False positive (no modified styles)")

else:
    # Stage 3 - Test Variants
    print("Minified bug. Testing variants...")
    variants = test_variants(minified_run_subject)

    print("Variants tested. Saving bug report...")
    url = save_bug_report(
        variants,
        minified_run_subject,
        minified_run_result,
        test_filepath,
        pickle_addre
    )
    print(url)



# Clean Up
remove_file(test_filepath)