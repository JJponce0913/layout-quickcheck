import pickle
import os
import datetime

from tooling.treeComparison import run_subject_to_node_tree, merge_trees, walk_tree_verbose
from tooling.ruleConvergence import check_all_pkls, create_rule, extract_tag_tree, get_styles


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def hr(ch="=", n=80):
    print(ch * n)


def banner(msg):
    print()
    hr("=")
    print(f"[{now()}] {msg}")
    hr("=")


def section(msg):
    print()
    hr("-")
    print(f"[{now()}] {msg}")
    hr("-")


def kv(k, v):
    print(f"{k:<18}: {v}")


def find_subject_pkl(bug_instance_dir):
    for name in ("minified_run_subject.pkl", "run_subject.pkl"):
        p = os.path.join(bug_instance_dir, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("no run_subject pickle found")


def test_bug_instance_against_group(
    bug_group_dir,
    bug_instance_dir,
    safe_dir
):
    banner("BUG GROUP TEST")

    kv("bug_group_dir", bug_group_dir)
    kv("bug_instance_dir", bug_instance_dir)
    kv("safe_dir", safe_dir)

    subject_pkl = find_subject_pkl(bug_instance_dir)

    kv("subject_pickle", subject_pkl)

    with open(subject_pkl, "rb") as f:
        run_subject = pickle.load(f)

    tree, startnode = run_subject_to_node_tree(run_subject)

    merged_pkl = os.path.join(bug_group_dir, "merged_tree.pkl")
    with open(merged_pkl, "rb") as f:
        merged_tree, merged_startnode = pickle.load(f)

    temp_tree, temp_startnode = merge_trees(startnode, merged_startnode)
    rule = create_rule(extract_tag_tree(temp_tree), get_styles(temp_startnode))
    section("TREES")
    walk_tree_verbose(tree)
    section("MERGED TREE")
    walk_tree_verbose(merged_tree)
    section("MERGED TREE")
    walk_tree_verbose(temp_tree)

    section("GENERATED RULE")
    kv("rule_name", rule.get("name"))
    kv("rule", rule)
    kv("style_count", len(rule["rule_class"]["style"]))
    kv("pattern_root", rule["rule_class"]["html_pattern"][0])

    section("TEST AGAINST BUG GROUP")
    results_bug, true_bug, false_bug = check_all_pkls(bug_group_dir, [rule])
    for p, r in results_bug:
        print(os.path.basename(p), "->", r)
    kv("matches", true_bug)
    kv("non_matches", false_bug)

    section("TEST AGAINST SAFE")
    results_safe, true_safe, false_safe = check_all_pkls(safe_dir, [rule])
    for p, r in results_safe:
        print(os.path.basename(p), "->", r)
    kv("matches", true_safe)
    kv("non_matches", false_safe)

    banner("DONE")


bug_group_dir = r"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/testFolders/bug-group-2026-02-02-23-18-42-207362-6724"
bug_instance_dir = r"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/testFolders/bug-group-2026-02-02-23-18-42-422817-3605/bug-instance-2026-02-02-23-18-39-212331-5386"
safe_dir = r"bug_reports\test-repo\safe"

test_bug_instance_against_group(
    bug_group_dir,
    bug_instance_dir,
    safe_dir
)