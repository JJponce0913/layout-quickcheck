import argparse
from contextlib import redirect_stdout
import datetime
import io
import pickle
import os
import random
import shutil
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tooling.tree_merge import run_subject_to_node_tree, merge_trees, walk_tree_verbose
from tooling.rule_engine import check_all_pkls, create_rule, extract_tag_tree, get_base_styles, get_modified_styles
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


def kv(key, value, indent=0):
    pad = " " * indent
    print(f"{pad}{key:<22}: {value}")


def check_all_pkls_quiet(folder_path, rules):
    with redirect_stdout(io.StringIO()):
        return check_all_pkls(folder_path, rules)


def minified_pkls(roots, pickle_name):
    paths = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                if name == pickle_name:
                    paths.append(os.path.join(dirpath, name))
    random.shuffle(paths)
    for p in paths:
        yield p


def resolve_output_dir(output_dir_name):
    output_dir_name = output_dir_name.strip()
    if not output_dir_name:
        raise ValueError("output_dir_name must not be empty.")
    return output_dir_name if os.path.isabs(output_dir_name) else os.path.join("bug_reports", output_dir_name)

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

    _, _, a_false = check_all_pkls_quiet(group_a_dir, [rule])
    _, _, b_false = check_all_pkls_quiet(group_b_dir, [rule])
    _, safe_true, _ = check_all_pkls_quiet(safe_dir, [rule])

    ok = (a_false == 0) and (b_false == 0) and (safe_true == 0)
    return ok, rule


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
                print(f"[merge] {os.path.basename(groups[j])} -> {os.path.basename(groups[i])}")

                merge_groups_on_disk(groups[i], groups[j])
                recompute_group_merged_tree(groups[i])

                merges_done += 1
                if merges_done >= max_merges_per_run:
                    return merges_done

            if tried >= max_pairs_to_try:
                return merges_done

    return merges_done


def run_sort(pickles_dir, pickle_name, safe_dir, output_dir_name):
    output_dir_path = resolve_output_dir(output_dir_name)
    if os.path.exists(output_dir_path):
        shutil.rmtree(output_dir_path)
    os.makedirs(os.path.join(output_dir_path, "known-bugs"), exist_ok=True)
    os.makedirs(os.path.join(output_dir_path, "unknown-bugs"), exist_ok=True)

    gen = minified_pkls([pickles_dir], pickle_name)

    banner("BUG SORT RUN")
    kv("pickles_dir", pickles_dir)
    kv("pickle_name", pickle_name)
    kv("safe_dir", safe_dir)
    kv("output_dir", output_dir_path)

    processed_count = 0
    added_existing_count = 0
    promoted_count = 0
    unknown_count = 0
    for i, p in enumerate(gen, start=1):
        processed_count += 1
        known_dir = os.path.join(output_dir_path, "known-bugs")

        print(f"\n[{i}] processing {os.path.relpath(p, pickles_dir)}")

        with open(p, "rb") as f:
            run_subject = pickle.load(f)

        tree, startnode = run_subject_to_node_tree(run_subject)
        added_to_known = False

        for bugFolder in os.listdir(os.path.join(output_dir_path, "known-bugs")):
            bugGroupPath = os.path.join(output_dir_path, "known-bugs", bugFolder)
            pkl_path = os.path.join(bugGroupPath, "merged_tree.pkl")

            if not os.path.exists(pkl_path):
                continue

            with open(pkl_path, "rb") as f:
                _, merged_tree_startnode = pickle.load(f)

            temp_tree, temp_startnode = merge_trees(startnode, merged_tree_startnode)

            rule = create_rule(
                extract_tag_tree(temp_tree),
                get_base_styles(temp_startnode),
                get_modified_styles(temp_startnode),
            )

            if not rule_is_usable(rule):
                continue

            _, _, false_bug = check_all_pkls_quiet(bugGroupPath, [rule])
            _, true_safe, _ = check_all_pkls_quiet(safe_dir, [rule])

            if false_bug == 0 and true_safe == 0:
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
                added_existing_count += 1
                print(f"  -> known group: {bugFolder}")
                break

        if added_to_known:
            continue

        for bugFolder in os.listdir(os.path.join(output_dir_path, "unknown-bugs")):
            bugInstancePath = os.path.join(output_dir_path, "unknown-bugs", bugFolder)
            pkl_path = os.path.join(bugInstancePath, "tree.pkl")

            if not os.path.exists(pkl_path):
                continue

            with open(pkl_path, "rb") as f:
                _, unknown_tree_startnode = pickle.load(f)

            temp_tree, temp_startnode = merge_trees(startnode, unknown_tree_startnode)

            rule = create_rule(
                extract_tag_tree(temp_tree),
                get_base_styles(temp_startnode),
                get_modified_styles(temp_startnode),
            )

            if not rule_is_usable(rule):
                continue

            _, true_safe, _ = check_all_pkls_quiet(safe_dir, [rule])

            if true_safe == 0:
                known_dir = os.path.join(output_dir_path, "known-bugs")
                new_folder_name = f"bug-group-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}-{random.randint(1000,9999)}"
                new_bug_group = os.path.join(known_dir, new_folder_name)
                os.makedirs(new_bug_group, exist_ok=True)

                src = os.path.join(output_dir_path, "unknown-bugs", bugFolder)
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

                added_to_known = True
                promoted_count += 1
                print(f"  -> promoted unknown '{bugFolder}' to new known group")
                break

        if added_to_known:
            continue

        working_unknown_bugs = os.path.join(output_dir_path, "unknown-bugs")
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
        unknown_count += 1
        print("  -> kept as unknown")

    banner("BUG SORT COMPLETE")
    kv("processed", processed_count)
    kv("added_to_known", added_existing_count)
    kv("promoted_to_known", promoted_count)
    kv("kept_unknown", unknown_count)
    kv("output_dir", output_dir_path)
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sort bug pickle files into known/unknown groups."
    )
    parser.add_argument(
        "--pickles-dir",
        required=True,
        help="Directory containing input pickles (searched recursively).",
    )
    parser.add_argument(
        "--pickle-name",
        required=True,
        help="Filename of the pickles to process (for example, run_subject.pkl).",
    )
    parser.add_argument(
        "--safe-dir",
        required=True,
        help="Directory of safe pickles used for rule comparison.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory name or absolute path where sorted output will be saved.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    return run_sort(
        pickles_dir=args.pickles_dir,
        pickle_name=args.pickle_name,
        safe_dir=args.safe_dir,
        output_dir_name=args.output_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
