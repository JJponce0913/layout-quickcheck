import json
import os
import pickle
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lqc.generate.web_page.create import save_as_web_page
from lqc_selenium.report.bug_report_helper import save_bug_report
from tooling.ruleConvergence import check_all_pkls, create_rule, extract_tag_tree, get_styles
from tooling.treeComparison import merge_trees, run_subject_to_node_tree


def process_bug(
    variants,
    prerun_subject,
    run_result,
    original_filepath,
    minified_run_subject=None,
    verbose=False,
):
    working_dir = "bug_reports/bug_groups"
    known_dir = os.path.join(working_dir, "known-bugs")
    unknown_dir = os.path.join(working_dir, "unknown-bugs")
    safe_dir = "bug_reports/test-repo/safe"

    os.makedirs(known_dir, exist_ok=True)
    os.makedirs(unknown_dir, exist_ok=True)

    def log(*args):
        if verbose:
            print(*args)

    def save_pickle(path, value):
        with open(path, "wb") as f:
            pickle.dump(value, f)

    def save_source_link(instance_dir, source_bug_folder):
        if source_bug_folder is None:
            return

        source_bug_folder = os.path.abspath(source_bug_folder)

        link_data = {
            "source_bug_folder": source_bug_folder,
            "source_minified_bug": os.path.join(source_bug_folder, "minified_bug.html"),
            "source_original_bug": os.path.join(source_bug_folder, "original_bug.html"),
            "source_data_json": os.path.join(source_bug_folder, "data.json"),
            "source_pickle": os.path.join(source_bug_folder, "run_subject.pkl"),
        }

        with open(os.path.join(instance_dir, "source_bug_report.json"), "w") as f:
            json.dump(link_data, f, indent=4)

        with open(os.path.join(instance_dir, "open_source_bug_report.txt"), "w") as f:
            f.write("file://" + os.path.join(source_bug_folder, "minified_bug.html"))

    def build_rule_from_merge(base_startnode, other_startnode):
        temp_tree, temp_startnode = merge_trees(base_startnode, other_startnode)
        rule = create_rule(
            extract_tag_tree(temp_tree),
            get_styles(temp_startnode)
        )
        return temp_tree, temp_startnode, rule

    def run_rule_check(label, directory, rule):
        results, true_count, false_count = check_all_pkls(directory, [rule])
        log(f"\nResults for {label}:")
        log("positive matches:", true_count)
        log("negative matches:", false_count)
        return results, true_count, false_count

    def create_bug_instance(parent_dir, tree, startnode, run_subject, source_bug_folder):
        base_name = f"bug-instance-{random.randint(1000, 9999)}"
        instance_dir = os.path.join(parent_dir, base_name)
        os.makedirs(instance_dir, exist_ok=True)

        save_pickle(os.path.join(instance_dir, "bug.pkl"), (tree, startnode))
        save_pickle(os.path.join(instance_dir, "run_subject.pkl"), run_subject)
        save_as_web_page(run_subject, os.path.join(instance_dir, "bug.html"))
        save_source_link(instance_dir, source_bug_folder)

        return instance_dir

    def add_to_existing_known_group(group_dir, tree, startnode, run_subject, source_bug_folder):
        instance_dir = create_bug_instance(group_dir, tree, startnode, run_subject, source_bug_folder)
        log("Added to existing known bug group:", group_dir)
        return instance_dir

    def create_known_bug_group(tree, startnode, run_subject, rule, source_bug_folder):
        new_bug_group = os.path.join(
            known_dir,
            f"bug-group-{random.randint(1000, 9999)}"
        )
        os.makedirs(new_bug_group, exist_ok=True)

        create_bug_instance(new_bug_group, tree, startnode, run_subject, source_bug_folder)
        save_pickle(os.path.join(new_bug_group, "merged_tree.pkl"), (tree, startnode))

        log("Created known bug group:", new_bug_group)
        log("rule:", rule)

        return new_bug_group
    
    def promote_unknown_to_known(group_dir, tree, startnode, run_subject, rule, source_bug_folder):
        new_group_dir = os.path.join(
            known_dir,
            f"bug-group-{random.randint(1000, 9999)}"
        )
        os.makedirs(new_group_dir, exist_ok=True)

        moved_unknown_name = os.path.basename(group_dir)
        moved_unknown_dst = os.path.join(new_group_dir, moved_unknown_name)

        shutil.move(group_dir, moved_unknown_dst)

        create_bug_instance(
            new_group_dir,
            tree,
            startnode,
            run_subject,
            source_bug_folder
        )

        save_pickle(os.path.join(new_group_dir, "merged_tree.pkl"), (tree, startnode))

        log("Created known bug group:", new_group_dir)
        log("Moved unknown bug into group:", moved_unknown_dst)
        log("rule:", rule)

        return new_group_dir

    log("Processing bug")

    initial_tree, initial_startnode = run_subject_to_node_tree(prerun_subject)

    for bug_folder in os.listdir(known_dir):
        group_dir = os.path.join(known_dir, bug_folder)
        merged_tree_path = os.path.join(group_dir, "merged_tree.pkl")

        if not os.path.isfile(merged_tree_path):
            continue

        log("VIEWING KNOWN BUG FOLDER:", bug_folder)

        with open(merged_tree_path, "rb") as f:
            merged_tree, merged_tree_startnode = pickle.load(f)

        _, temp_startnode, rule = build_rule_from_merge(initial_startnode, merged_tree_startnode)

        log("Rule created:", rule)

        _, bug_true_count, bug_false_count = run_rule_check("known bug folder", group_dir, rule)
        _, safe_true_count, safe_false_count = run_rule_check("safe folder", safe_dir, rule)

        if bug_false_count == 0 and safe_true_count == 0:
            report_info = save_bug_report(
                variants=variants,
                run_result=run_result,
                original_filepath=original_filepath,
                prerun_subject=prerun_subject,
            )
            add_to_existing_known_group(
                group_dir,
                initial_tree,
                initial_startnode,
                prerun_subject,
                report_info["bug_folder"],
            )
            return {
                "status": "existing-known",
                "group_dir": os.path.abspath(group_dir),
                "report_info": report_info,
            }

        log("Done" + "$" * 30)

    if minified_run_subject is None:
        log("No known group match found and no minified subject provided")
        return {
            "status": "needs-minification",
            "group_dir": None,
            "report_info": None,
        }

    tree, startnode = run_subject_to_node_tree(minified_run_subject)

    report_info = save_bug_report(
        variants=variants,
        run_result=run_result,
        original_filepath=original_filepath,
        prerun_subject=prerun_subject,
        minified_run_subject=minified_run_subject,
    )

    for bug_folder in os.listdir(unknown_dir):
        group_dir = os.path.join(unknown_dir, bug_folder)
        bug_pickle_path = os.path.join(group_dir, "bug.pkl")

        if not os.path.isfile(bug_pickle_path):
            continue

        log("VIEWING UNKNOWN BUG FOLDER:", bug_folder)

        with open(bug_pickle_path, "rb") as f:
            unknown_tree, unknown_tree_startnode = pickle.load(f)

        _, temp_startnode, rule = build_rule_from_merge(startnode, unknown_tree_startnode)

        if rule["rule_class"]["style"] == []:
            log("Skipping empty rule")
            return {
                "status": "skipped-empty-rule",
                "group_dir": None,
                "report_info": report_info,
            }

        if rule["rule_class"]["style"] == [["display", "diff"]]:
            raise Exception("Diff rule found, investigate why this is being created")

        _, bug_true_count, bug_false_count = run_rule_check("unknown bug folder", group_dir, rule)
        _, safe_true_count, safe_false_count = run_rule_check("safe folder", safe_dir, rule)

        try:
            ratio = safe_true_count / safe_false_count
        except ZeroDivisionError:
            ratio = float("inf")

        log("ratio:", ratio)

        if ratio < 0.1:
            new_group_dir = promote_unknown_to_known(
                group_dir,
                tree,
                startnode,
                minified_run_subject,
                rule,
                report_info["bug_folder"],
            )
            return {
                "status": "new-known",
                "group_dir": os.path.abspath(new_group_dir),
                "report_info": report_info,
            }

        log("Not adding to known bugs" + "-" * 40)

    instance_dir = create_bug_instance(
        unknown_dir,
        tree,
        startnode,
        minified_run_subject,
        report_info["bug_folder"],
    )
    log("Added to unknown bugs")

    return {
        "status": "unknown",
        "group_dir": os.path.abspath(unknown_dir),
        "instance_dir": os.path.abspath(instance_dir),
        "report_info": report_info,
    }