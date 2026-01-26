"""
This script loads a run_subject object from a pickle file and renders it into a  HTML file.

Example usage from the project root:
python src/tooling/saveHtml.py path/to/run_subject.pkl

The output HTML file will be written to test.html in the current working directory.
"""

import sys
import pickle
from lqc.generate.web_page.create import save_as_web_page

pickle_addre = sys.argv[1]

with open(pickle_addre, "rb") as f:
    run_subject = pickle.load(f)

print(f"Loaded run_subject from {pickle_addre}")
save_as_web_page(run_subject, "test.html")