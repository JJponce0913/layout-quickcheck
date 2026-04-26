import argparse
import json
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lqc.rules.rule_engine import check_all_pkls, create_rule, extract_tag_tree, get_base_styles, get_modified_styles, merge_folder
from lqc.rules.tree_merge import walk_tree_verbose

"""
Merges tree structures from run_subject PKL files in a base folder,
generates a rule from the merged result, and evaluates that rule
against all PKL files in a check folder.

Usage
-----
python src/tooling/scripts/merge_folder.py --base <base_folder_path> --check <check_folder_path>

Arguments
---------
--base
    Folder containing PKL files used to build the merged tree and rule.

--check
    Folder containing PKL files that will be evaluated against the
    generated rule.

Output
------
Prints the final merged tree, the generated rule, and the results
of applying the rule to each PKL file in the check folder.
"""


def run_pipeline(base_folder, check_folder):
    cur_tree, cur_start = merge_folder(base_folder)

    print("\n\nFinal merged tree:")
    walk_tree_verbose(cur_tree)

    rule = create_rule(
        extract_tag_tree(cur_tree),
        get_base_styles(cur_start),
        get_modified_styles(cur_start),
    )

    print("\n\nGenerated Rule:")
    print(rule)

    with open("generated_rule.json", "w", encoding="utf-8") as f:
        json.dump(rule, f, indent=2)

    results, true_count, false_count = check_all_pkls(check_folder, [rule])

    print("\n\nFinal Results:")
    print("Results for each pkl:")
    for p, r in results:
        print(f"{p}: {r}")

    print(f"positive matches: {true_count}")
    print(f"negative matches: {false_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--base", required=True, help="Path to base folder")
    parser.add_argument("--check", required=True, help="Path to check folder")

    args = parser.parse_args()

    run_pipeline(args.base, args.check)
