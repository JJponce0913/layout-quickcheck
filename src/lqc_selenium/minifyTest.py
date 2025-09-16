import pickle
from lqc_selenium.runner import minify
from lqc_selenium.variants.variants import TargetBrowser
import sys, traceback, argparse
from lqc.config.config import Config, parse_config
from lqc.generate.html_file_generator import remove_file
from lqc.generate.style_log_generator import generate_run_subject
from lqc.minify.minify_test_file import MinifyStepFactory
from lqc.model.constants import BugType
from lqc_selenium.report.bug_report_helper import save_bug_report
from lqc.util.counter import Counter
from lqc_selenium.variants.variant_tester import test_variants
from lqc_selenium.variants.variants import TargetBrowser, getTargetVariant
from lqc_selenium.selenium_harness.layout_tester import test_combination
import pickle
import inspect, lqc.model.run_subject as rsmod
import os, uuid, pickle
DEFAULT_CONFIG_FILE = "./config/preset-default.config.json"
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""find bugs in browser layout calculation - run forever unless specified otherwise\n\nexamples: \n    compare.py -b 1         # Find one bug and quit \n    compare.py -t 2000      # Run 2000 tests and quit""")
parser.add_argument("-v", "--verbose", help="increase output verbosity (repeatable argument -v, -vv, -vvv, -vvvv)", action="count", default=0)
parser.add_argument("-b", "--bug-limit", help="quit after finding this many bugs", type=int, default=0)
parser.add_argument("-t", "--test-limit", help="quit after running this many tests", type=int, default=0)
parser.add_argument("-l", "--crash-limit", help="quit after crashing this many times", type=int, default=1)
parser.add_argument("-c", "--config-file", help="path to config file to use", type=str, default=DEFAULT_CONFIG_FILE)
print(f"Using config file {args.config_file}")
conf = parse_config(args.config_file)
Config(conf)
# Load the saved RunSubject
with open("pickles/run_subject_pre_0b405fa7c0a14c8096fd319acec69fdb.pkl", "rb") as f:
    run_subject = pickle.load(f)

# Create a fresh target browser
target_browser = TargetBrowser()

# Run minification
minified_run_subject, minified_run_result = minify(target_browser, run_subject)

print("Minification complete")
print(minified_run_subject)
print(minified_run_result)
