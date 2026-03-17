import argparse
import pickle
from lqc.generate.web_page.create import save_as_web_page

"""
Loads a run_subject object from a pickle file and renders it into an HTML file.

This script reads a serialized run_subject object from a provided pickle path,
then uses the web page generator to convert that object into an HTML
representation.

Usage
-----
python src/tooling/scripts/pickle_to_html.py --pickle path/to/run_subject.pkl --output path/to/output.html

Arguments
---------
--pickle
    Path to the pickle file containing the run_subject object.

--output
    Path to the output HTML file. Defaults to test.html.

Output
------
Generates an HTML file containing a rendered visualization of the
run_subject object.
"""


def pickle_to_html(pickle_path, output_path="test.html"):
    with open(pickle_path, "rb") as f:
        run_subject = pickle.load(f)

    print(f"Loaded run_subject from {pickle_path}")
    save_as_web_page(run_subject, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--pickle", required=True, help="Path to run_subject pickle file")
    parser.add_argument("--output", default="test.html", help="Output HTML file")

    args = parser.parse_args()

    pickle_to_html(args.pickle, args.output)
