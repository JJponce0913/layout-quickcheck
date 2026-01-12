from treeComparison import run_subject_to_node_tree, walk_tree, walk_tree_verbose, merge_trees
from checkFile import should_skip
import os,pickle,time, re
from bs4 import BeautifulSoup
from lqc.generate.web_page.create import save_as_web_page


def load_tree_start_pairs(folder_path):
    pairs = []

    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.endswith(".pkl"):
                continue
            if "run_subject" not in name:
                continue

            pkl_path = os.path.join(root, name)
            try:
                with open(pkl_path, "rb") as f:
                    run_subject = pickle.load(f)
                tree, start_node = run_subject_to_node_tree(run_subject)
                pairs.append((tree, start_node))
            except Exception:
                continue

    return pairs
def check_all_pkls(folder_path, rules):
    print(f"Checking all pkls in {folder_path} against {len(rules)} rules.")
    results = []
    total = 0

    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.endswith(".pkl"):
                continue
            total += 1
            pkl_path = os.path.join(root, name)
            try:
                matched = checks(pkl_path, rules)
                results.append((pkl_path, matched))
            except Exception as e:
                results.append((pkl_path, f"ERROR: {e}"))

    print(f"Total pkl files found: {total}")

    false = 0
    true = 0
    for p, r in results:
        if r == True:
            true += 1
        else:
            false += 1

    return results, true, false

def create_html_pat(node):
    """
    Return the html_pattern-style list of direct child tags for the given node.
    Uses "text" for text nodes (#text) with non-empty content, mirroring check_pattern().
    """
    if node is None:
        return []

    def _children(n):
        # Prefer our Node.children list; fall back to firstchild/next chain if present.
        kids = getattr(n, "children", None)
        if kids is not None:
            return kids
        chain = []
        child = getattr(n, "firstchild", None)
        while child is not None:
            chain.append(child)
            child = getattr(child, "next", None)
        return chain

    pattern = []
    for child in _children(node):
        tag = getattr(child, "tag", None)
        if tag == "#text":
            text_val = getattr(child, "text", "")
            if isinstance(text_val, str) and not text_val.strip():
                continue
            pattern.append("text")
        elif tag:
            pattern.append(tag)

    return pattern

def get_styles(node):
    if node is None:
        return {}
    pairs= []
    for pair in list(node.modified_style.items()):
        pairs.append(list(pair))
    return pairs
def create_rule(html_pattern, styles):
    rule = {
        "name": str(time.time()),
        "rule_class": {
            "style": styles,
            "html_pattern": html_pattern,
            
        }
    }
    return rule



def check_pattern(filename, pattern):
    with open(filename, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    need = {}
    for x in pattern:
        need[x] = need.get(x, 0) + 1

    for body in soup.find_all("body"):
        kids = [c for c in body.contents if getattr(c, "name", None) or str(c).strip()]
        have = {}
        for c in kids:
            if getattr(c, "name", None):
                k = c.name
            else:
                k = "text"
            have[k] = have.get(k, 0) + 1

        ok = True
        for k, cnt in need.items():
            if have.get(k, 0) < cnt:
                ok = False
                break
        if ok:
            return True

    return False


def checks(pkl_path, rules):
    with open(pkl_path, "rb") as f:
        run_subject = pickle.load(f)

    save_as_web_page(run_subject, "tmp_generated_files/rule_check.html", run_result=None)
    file = "tmp_generated_files/rule_check.html"

    should_be_skip = should_skip(file, rules)

    return should_be_skip


def merge_folder(folder_path):
    pairs = load_tree_start_pairs(folder_path)
    print(f"Loaded {len(pairs)} tree-start_node pairs.")

    if len(pairs) < 2:
        raise RuntimeError("Need at least 2 run_subject files to merge")

    _, curStartNode = pairs.pop(0)
    _, secondStartNode = pairs.pop(0)

    curTree, curStartNode = merge_trees(curStartNode, secondStartNode)
    merge_count = 1

    for _, start_node in pairs:
        curTree, curStartNode = merge_trees(curStartNode, start_node)
        merge_count += 1

    return curTree, curStartNode


import json

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, required=True)
    args = parser.parse_args()

    if args.runs == 1:
        base_folder = "bug_reports/test-repo/skipped-bug-report"
        check_folder = "bug_reports/test-repo/skipped-bug-report"
    elif args.runs == 2:
        base_folder = "bug_reports/test-repo/skipped-bug-report"
        check_folder = "bug_reports/test-repo/non-skipped-bug-report"
    elif args.runs == 3:
        base_folder = "bug_reports/test-repo/skipped-bug-report"
        check_folder = "bug_reports/test-repo/safe"
    elif args.runs == 4:
        base_folder = "bug_reports/test-repo/non-skipped-bug-report"
        check_folder = "bug_reports/test-repo/safe"



    curTree, curStartNode = merge_folder(
        f"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/{base_folder}"
    )

    # Part 2 print the merged tree
    print("\n\nFinal merged tree:")
    walk_tree_verbose(curTree)

    # Part 3 create a rule from the merged tree
    rule = create_rule(create_html_pat(curTree), get_styles(curStartNode))

    # Part 4 print the generated rule
    print("\n\nGenerated Rules:")
    print(rule)

    # Part 5 write the rule to a json file
    with open("generated_rule.json", "w", encoding="utf-8") as f:
        json.dump(rule, f, indent=2)

    # Part 6 check the rule against non skipped pkls
    results, true, false = check_all_pkls(
        f"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/{check_folder}",
        [rule]
    )

    # Part 7 print results and summary counts
    print("\n\nFinal Results:")
    print("Results for each pkl:")
    for p, r in results:
        print(f"{p}: {r}")
    print(f"positive matches: {true}")
    print(f"negative matches: {false}")

