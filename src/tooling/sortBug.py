from contextlib import redirect_stdout
import datetime
import pickle
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.treeComparison import run_subject_to_node_tree, merge_trees, walk_tree_verbose
from tooling.ruleConvergence import check_all_pkls, create_rule, extract_tag_tree, get_base_styles, get_modified_styles
from lqc.generate.web_page.create import save_as_web_page


def now_stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def hr(ch="=", n=90):
    return ch * n


def banner(title):
    print()
    print(hr("=", 90))
    print(f"[{now_stamp()}] {title}")
    print(hr("=", 90))


def section(title):
    print()
    print(hr("-", 90))
    print(f"[{now_stamp()}] {title}")
    print(hr("-", 90))


def kv(key, value, indent=0):
    pad = " " * indent
    print(f"{pad}{key:<22}: {value}")


def result_summary(label, true_count, false_count, ratio=None, indent=2):
    pad = " " * indent
    print(f"{pad}{label}")
    print(f"{pad}{'matches':<14}: {true_count}")
    print(f"{pad}{'non-matches':<14}: {false_count}")
    if ratio is not None:
        print(f"{pad}{'ratio':<14}: {ratio}")


def list_results(label, results, max_items=12, indent=2):
    pad = " " * indent
    print(f"{pad}{label}")
    if not results:
        print(f"{pad}  (no results)")
        return
    shown = 0
    for path, r in results:
        if shown >= max_items:
            break
        print(f"{pad}  - {os.path.basename(path)} -> {r}")
        shown += 1
    if len(results) > max_items:
        print(f"{pad}  ... ({len(results) - max_items} more)")


def minified_pkls(*roots):
    paths = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                if name == "minified_run_subject.pkl" or name == "run_subject.pkl":
                    paths.append(os.path.join(dirpath, name))
    random.shuffle(paths)
    for p in paths:
        yield p

def pattern_token_count(p):
    if isinstance(p, str):
        return 1
    if isinstance(p, list):
        return sum(pattern_token_count(x) for x in p)
    return 0

def load_merged_tree_from_group(group_dir):
    p = os.path.join(group_dir, "merged_tree.pkl")
    with open(p, "rb") as f:
        merged_tree, merged_startnode = pickle.load(f)
    return merged_tree, merged_startnode


def group_dirs(known_dir):
    out = []
    for name in os.listdir(known_dir):
        p = os.path.join(known_dir, name)
        if os.path.isdir(p):
            out.append(p)
    out.sort()
    return out


def rule_is_usable(rule):
    rc = rule.get("rule_class", {})
    pattern = rc.get("html_pattern", [])
    modified_styles = rc.get("modified_style", [])
    has_real_modified = any(v != "diff" for _, v in modified_styles)
    return pattern_token_count(pattern) > 1 and has_real_modified


def can_merge_two_groups(group_a_dir, group_b_dir, safe_dir):
    _, a_start = load_merged_tree_from_group(group_a_dir)
    _, b_start = load_merged_tree_from_group(group_b_dir)

    temp_tree, temp_start = merge_trees(a_start, b_start)
    rule = create_rule(
        extract_tag_tree(temp_tree),
        get_base_styles(temp_start),
        get_modified_styles(temp_start),
    )

    if not rule_is_usable(rule):
        return False, None

    _, a_true, a_false = check_all_pkls(group_a_dir, [rule])
    _, b_true, b_false = check_all_pkls(group_b_dir, [rule])
    _, safe_true, _ = check_all_pkls(safe_dir, [rule])

    ok = (a_false == 0) and (b_false == 0) and (safe_true == 0)
    return ok, rule


def find_group_merges(known_dir, safe_dir, max_pairs=5):
    groups = group_dirs(known_dir)
    merges = []
    n = len(groups)

    for i in range(n):
        for j in range(i + 1, n):
            ok, rule = can_merge_two_groups(groups[i], groups[j], safe_dir)
            if ok:
                merges.append((groups[i], groups[j], rule))
                if len(merges) >= max_pairs:
                    return merges

    return merges


def merge_groups_on_disk(group_a_dir, group_b_dir):
    base_name = os.path.basename(os.path.normpath(group_b_dir))
    dst = os.path.join(group_a_dir, base_name)

    if os.path.isdir(group_b_dir):
        shutil.copytree(group_b_dir, dst, dirs_exist_ok=True)
        shutil.rmtree(group_b_dir)

    return dst


def recompute_group_merged_tree(group_dir):
    instance_starts = []

    for root, _, files in os.walk(group_dir):
        for name in files:
            if name != "tree.pkl":
                continue
            p = os.path.join(root, name)
            try:
                with open(p, "rb") as f:
                    _, startnode = pickle.load(f)
                if startnode is not None:
                    instance_starts.append(startnode)
            except Exception:
                pass

    if not instance_starts:
        return None

    cur = instance_starts[0]
    cur_tree = None
    for nxt in instance_starts[1:]:
        cur_tree, cur = merge_trees(cur, nxt)

    merged_path = os.path.join(group_dir, "merged_tree.pkl")
    with open(merged_path, "wb") as f:
        pickle.dump((cur_tree, cur), f)

    with open(os.path.join(group_dir, "merged_tree.txt"), "w", encoding="utf-8") as f:
        with redirect_stdout(f):
            walk_tree_verbose(cur_tree)

    return merged_path


def merge_converge_known_bugs(known_dir, safe_dir, max_merges_per_run=1, max_pairs_to_try=50):
    groups = group_dirs(known_dir)
    merges_done = 0
    tried = 0

    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            tried += 1
            ok, rule = can_merge_two_groups(groups[i], groups[j], safe_dir)
            if ok:
                print("MERGE_CANDIDATE")
                print("A", groups[i])
                print("B", groups[j])
                print("RULE", rule)

                merge_groups_on_disk(groups[i], groups[j])
                recompute_group_merged_tree(groups[i])

                merges_done += 1
                if merges_done >= max_merges_per_run:
                    return merges_done

            if tried >= max_pairs_to_try:
                return merges_done

    return merges_done


gen = minified_pkls(
    r"bug_reports/test-repo2/non-skipped-bug-report",
    r"bug_reports/test-repo2/skipped-bug-report",
)

working_dir = f"bug_reports/sortRepo-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
os.makedirs(os.path.join(working_dir, "known-bugs"), exist_ok=True)
os.makedirs(os.path.join(working_dir, "unknown-bugs"), exist_ok=True)

safe_dir = "bug_reports/test-repo2/safe"

banner("BUG SORT RUN START")
kv("working_dir", working_dir)
kv("safe_dir", safe_dir)
kv("known_bugs_dir", os.path.join(working_dir, "known-bugs"))
kv("unknown_bugs_dir", os.path.join(working_dir, "unknown-bugs"))
print()

for i, p in enumerate(gen, start=1):
    known_dir = os.path.join(working_dir, "known-bugs")

    if i % 10 == 0:
        print("CONVERGENCE_PASS", i)
        merge_converge_known_bugs(
            known_dir=known_dir,
            safe_dir=safe_dir,
            max_merges_per_run=1,
            max_pairs_to_try=50,
        )

    banner(f"INPUT #{i}")
    kv("minified_pickle", p)
    kv("source_dir", os.path.dirname(p))

    with open(p, "rb") as f:
        run_subject = pickle.load(f)

    tree, startnode = run_subject_to_node_tree(run_subject)
    kv("tree_built", "yes")
    kv("known_groups", len(os.listdir(os.path.join(working_dir, "known-bugs"))))
    kv("unknown_instances", len(os.listdir(os.path.join(working_dir, "unknown-bugs"))))

    added_to_known = False

    for bugFolder in os.listdir(os.path.join(working_dir, "known-bugs")):
        section(f"TRY KNOWN GROUP: {bugFolder}")
        bugGroupPath = os.path.join(working_dir, "known-bugs", bugFolder)
        pkl_path = os.path.join(bugGroupPath, "merged_tree.pkl")

        if not os.path.exists(pkl_path):
            kv("status", "skip, missing merged_tree.pkl", indent=2)
            continue

        with open(pkl_path, "rb") as f:
            merged_tree, merged_tree_startnode = pickle.load(f)

        temp_tree, temp_startnode = merge_trees(startnode, merged_tree_startnode)

        rule = create_rule(
            extract_tag_tree(temp_tree),
            get_base_styles(temp_startnode),
            get_modified_styles(temp_startnode),
        )

        kv("rule_name", rule.get("name", "<none>"), indent=2)
        kv("style_count", len(rule["rule_class"]["base_style"]), indent=2)
        kv("modified_style_count", len(rule["rule_class"]["modified_style"]), indent=2)
        kv("pattern_len", len(rule["rule_class"]["html_pattern"]), indent=2)
        kv("pattern_root", rule["rule_class"]["html_pattern"][0] if rule["rule_class"]["html_pattern"] else "<empty>", indent=2)

        if not rule_is_usable(rule):
            kv("decision", "skip this group, rule not usable", indent=2)
            continue

        results_bug, true_bug, false_bug = check_all_pkls(bugGroupPath, [rule])
        list_results("bug group sample", results_bug, max_items=10, indent=2)
        result_summary("bug group totals", true_bug, false_bug, indent=2)

        results_safe, true_safe, false_safe = check_all_pkls(safe_dir, [rule])
        list_results("safe folder sample", results_safe, max_items=10, indent=2)
        result_summary("safe folder totals", true_safe, false_safe, indent=2)

        if false_bug == 0 and true_safe == 0:
            section("DECISION: ADD TO THIS KNOWN GROUP")
            kv("reason", "rule matches all in group and matches none in safe", indent=2)

            base_name = f"bug-instance-b-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}-{random.randint(1000,9999)}"
            os.makedirs(os.path.join(bugGroupPath, base_name), exist_ok=True)

            tree_pkl_path = os.path.join(bugGroupPath, base_name, "tree.pkl")
            tree_txt_path = os.path.join(bugGroupPath, base_name, "tree.txt")
            html_pkl_path = os.path.join(bugGroupPath, base_name, "run_subject.pkl")
            html_path = os.path.join(bugGroupPath, base_name, "run_subject.html")

            with open(tree_pkl_path, "wb") as f:
                pickle.dump((tree, startnode), f)

            with open(tree_txt_path, "w", encoding="utf-8") as f:
                with redirect_stdout(f):
                    walk_tree_verbose(tree)

            with open(html_pkl_path, "wb") as f:
                pickle.dump(run_subject, f)

            save_as_web_page(run_subject, html_path)

            kv("wrote_tree_pkl", tree_pkl_path, indent=2)
            kv("wrote_tree_txt", tree_txt_path, indent=2)
            kv("wrote_run_subject_pkl", html_pkl_path, indent=2)
            kv("wrote_run_subject_html", html_path, indent=2)

            merged_path = os.path.join(bugGroupPath, "merged_tree.pkl")
            with open(merged_path, "wb") as f:
                pickle.dump((temp_tree, temp_startnode), f)

            with open(os.path.join(bugGroupPath, "merged_tree.txt"), "w", encoding="utf-8") as f:
                with redirect_stdout(f):
                    walk_tree_verbose(temp_tree)
                    print()
                    print("Generated Rule:")
                    print(rule)

            added_to_known = True
            break

        kv("decision", "not a match for this known group", indent=2)

    if added_to_known:
        section("INPUT HANDLED")
        kv("final_action", "added to existing known group", indent=2)
        continue

    for bugFolder in os.listdir(os.path.join(working_dir, "unknown-bugs")):
        section(f"TRY UNKNOWN INSTANCE: {bugFolder}")
        bugInstancePath = os.path.join(working_dir, "unknown-bugs", bugFolder)
        pkl_path = os.path.join(bugInstancePath, "tree.pkl")

        if not os.path.exists(pkl_path):
            kv("status", "skip, missing tree.pkl", indent=2)
            continue

        with open(pkl_path, "rb") as f:
            unknown_tree, unknown_tree_startnode = pickle.load(f)

        temp_tree, temp_startnode = merge_trees(startnode, unknown_tree_startnode)

        rule = create_rule(
            extract_tag_tree(temp_tree),
            get_base_styles(temp_startnode),
            get_modified_styles(temp_startnode),
        )

        kv("rule_name", rule.get("name", "<none>"), indent=2)
        kv("base_style", rule["rule_class"]["base_style"], indent=2)
        kv("modified_style", rule["rule_class"]["modified_style"], indent=2)
        kv("html_pattern", rule["rule_class"]["html_pattern"], indent=2)
        kv("style_count", len(rule["rule_class"]["base_style"]), indent=2)
        kv("modified_style_count", len(rule["rule_class"]["modified_style"]), indent=2)
        kv("pattern_len", len(rule["rule_class"]["html_pattern"]), indent=2)

        if not rule_is_usable(rule):
            kv("decision", "skip unknown instance, rule not usable", indent=2)
            continue

        results_safe, true_safe, false_safe = check_all_pkls(safe_dir, [rule])
        list_results("safe folder sample", results_safe, max_items=10, indent=2)

        if false_safe == 0:
            ratio = float("inf")
        else:
            ratio = true_safe / false_safe

        result_summary("safe folder totals", true_safe, false_safe, ratio=ratio, indent=2)

        if true_safe == 0:
            section("DECISION: PROMOTE UNKNOWN INSTANCE TO NEW KNOWN GROUP")
            kv("reason", "rule matches none of safe", indent=2)

            known_dir = os.path.join(working_dir, "known-bugs")
            new_folder_name = f"bug-group-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}-{random.randint(1000,9999)}"
            new_bug_group = os.path.join(known_dir, new_folder_name)
            os.makedirs(new_bug_group, exist_ok=True)

            src = os.path.join(working_dir, "unknown-bugs", bugFolder)
            dst = os.path.join(new_bug_group, bugFolder)
            os.makedirs(dst, exist_ok=True)

            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                shutil.rmtree(src)

            base_name = f"bug-instance-b-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}-{random.randint(1000,9999)}"
            os.makedirs(os.path.join(new_bug_group, base_name), exist_ok=True)

            tree_pkl_path = os.path.join(new_bug_group, base_name, "tree.pkl")
            html_pkl_path = os.path.join(new_bug_group, base_name, "run_subject.pkl")
            html_path = os.path.join(new_bug_group, base_name, "run_subject.html")

            with open(tree_pkl_path, "wb") as f:
                pickle.dump((temp_tree, startnode), f)

            with open(html_pkl_path, "wb") as f:
                pickle.dump(run_subject, f)

            save_as_web_page(run_subject, html_path)

            merged_path = os.path.join(new_bug_group, "merged_tree.pkl")
            with open(merged_path, "wb") as f:
                pickle.dump((temp_tree, temp_startnode), f)

            with open(os.path.join(new_bug_group, "merged_tree.txt"), "w", encoding="utf-8") as f:
                with redirect_stdout(f):
                    walk_tree_verbose(temp_tree)
                    print()
                    print("Generated Rule:")
                    print(rule)

            kv("new_known_group", new_bug_group, indent=2)
            kv("moved_unknown_instance", bugFolder, indent=2)
            kv("wrote_merged_tree_pkl", merged_path, indent=2)
            kv("wrote_tree_pkl", tree_pkl_path, indent=2)
            kv("wrote_run_subject_pkl", html_pkl_path, indent=2)
            kv("wrote_run_subject_html", html_path, indent=2)
            added_to_known = True
            break

        kv("decision", "keep unknown instance as unknown", indent=2)

    if added_to_known:
        section("INPUT HANDLED")
        kv("final_action", "promoted from unknown to new known group", indent=2)
        continue

    section("FALLBACK: ADD INPUT TO UNKNOWN BUGS")
    working_unknown_bugs = os.path.join(working_dir, "unknown-bugs")
    base_name = f"bug-instance-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}-{random.randint(1000,9999)}"
    os.makedirs(os.path.join(working_unknown_bugs, base_name), exist_ok=True)

    tree_pkl_path = os.path.join(working_unknown_bugs, base_name, "tree.pkl")
    html_pkl_path = os.path.join(working_unknown_bugs, base_name, "run_subject.pkl")
    html_path = os.path.join(working_unknown_bugs, base_name, "run_subject.html")

    with open(tree_pkl_path, "wb") as f:
        pickle.dump((tree, startnode), f)

    with open(html_pkl_path, "wb") as f:
        pickle.dump(run_subject, f)

    save_as_web_page(run_subject, html_path)

    kv("wrote_tree_pkl", tree_pkl_path, indent=2)
    kv("wrote_run_subject_pkl", html_pkl_path, indent=2)
    kv("wrote_run_subject_html", html_path, indent=2)

banner("BUG SORT RUN COMPLETE")
print("Done sorting bugs.")