
import argparse
import pickle
from tooling.tree_merge import pickle_to_node_tree, walk_tree_verbose
from lqc.generate.web_page.create import save_as_web_page

"""
Loads a run_subject pickle file, converts it into a node tree, prints the tree
structure, and generates an HTML visualization.

Usage
-----
python src/tooling/scripts/pickle_to_tree.py --pickle path/to/run_subject.pkl --output output.html

Arguments
---------
--pickle
    Path to the pickle file containing the run_subject object.

--output
    Path to the output HTML file. Defaults to tmp_generated_files/tmp.html.

Output
------
Prints the tree structure to the console and generates an HTML file that
visualizes the run_subject object.
"""

def run_subject_pickle_to_html(pickle_path, output_path="tmp_generated_files/tmp.html"):
    with open(pickle_path, "rb") as f:
        run_subject = pickle.load(f)

    tree, start_node = pickle_to_node_tree(run_subject)

    walk_tree_verbose(tree)
    print(f"Loaded run_subject from {pickle_path}")

    save_as_web_page(run_subject, output_path, run_result=None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--pickle", required=True, help="Path to run_subject pickle file")
    parser.add_argument("--output", default="tmp_generated_files/tmp.html", help="Output HTML file")

    args = parser.parse_args()

    run_subject_pickle_to_html(args.pickle, args.output)
