import json
import os
import shutil
import pickle
from datetime import datetime
from lqc.config.file_config import FileConfig
from lqc.generate.web_page.create import save_as_web_page
from lqc.generate.web_page.run_subject_converter import copyExternalJSFiles
from lqc.model.constants import BugType
from lqc.model.run_result import RunResult, RunResultLayoutBug
from lqc.model.run_subject import RunSubject
from tooling.rule_engine import dissolve_bug_group, recompute_bug_group_artifacts


def save_bug_report(
    variants,
    minified_run_subject: RunSubject,
    run_result: RunResult,
    original_filepath,
    prerun_subject: RunSubject,
    shouldSkip
):
    file_config = FileConfig()

    bug_folder = file_config.getCustomTimestampBugReport("bug_report")

    # Create a folder to hold all the bug report files
    os.mkdir(bug_folder)

    # Copy the original file
    bug_filepath = os.path.join(bug_folder, "original_bug.html")
    shutil.copy(original_filepath, bug_filepath)

    # Copy the minimized bug
    minified_bug = os.path.join(bug_folder, "minified_bug.html")
    print(f"Saving minimized bug to {minified_bug}")
    save_as_web_page(minified_run_subject, minified_bug, run_result=run_result)
    copyExternalJSFiles(bug_folder)

    # Custom bug helper file - JSON file
    styles_used = list(minified_run_subject.all_style_names())
    styles_used.sort()
    styles_used_string = ",".join(styles_used)
    base_styles = list(minified_run_subject.base_styles.all_style_names())
    modified_styles = list(minified_run_subject.modified_styles.all_style_names())
    bug_type = "Page Crash" if run_result.type == BugType.PAGE_CRASH else "Under Invalidation"

    
    pickle_addr = f"{bug_folder}/minified_run_subject.pkl"
    with open(pickle_addr, "wb") as f:
        pickle.dump(minified_run_subject, f)

    prerun_subject_addr = f"{bug_folder}/run_subject_prerun.pkl"
    with open(prerun_subject_addr, "wb") as f:
        pickle.dump(prerun_subject, f)
    
    json_data = {
        "datetime": datetime.now().isoformat(),
        "bug_type": bug_type,
        "styles_used": styles_used,
        "styles_used_string": styles_used_string,
        "base_styles": base_styles,
        "modified_styles": modified_styles,
        "variants": variants,
        "minified_run_subject": minified_run_subject,
        "prerun_subject": prerun_subject,
        "pickle_addr": pickle_addr,
        "shouldSkip": shouldSkip
    }
    
    if isinstance(run_result, RunResultLayoutBug):
        json_data["differences"] = run_result.element_dimensions

    json_data_filepath = os.path.join(bug_folder, "data.json")
    with open(json_data_filepath, "w") as f:
        f.write(json.dumps(json_data, indent=4, default=lambda o: o.__dict__))

    # Todo: Copy the necessary javascript files (debugger_tools.js)

    # Return a URL
    url = "file://" + os.path.abspath(minified_bug)
    return url


import ast
import json
import os
import pickle
import re
import shutil
from datetime import datetime

def find_matching_rule_folder(folder_name, rule_name):
    base_dir = os.path.join("bug_reports", folder_name)

    if not os.path.isdir(base_dir):
        return None

    for entry in os.listdir(base_dir):
        entry_path = os.path.join(base_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        merged_tree_path = os.path.join(entry_path, "merged_tree.txt")
        if not os.path.isfile(merged_tree_path):
            continue

        with open(merged_tree_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"Generated Rule:\s*(\{.*\})", content, re.DOTALL)
        if not match:
            continue

        try:
            rule_data = ast.literal_eval(match.group(1).strip())
        except Exception:
            continue

        if str(rule_data.get("name")) == str(rule_name):
            return entry_path

    return None


def save_bug_report_custom(
    variants,
    minified_run_subject: RunSubject,
    run_result: RunResult,
    original_filepath,
    prerun_subject: RunSubject,
    path,
    shouldSkip,
    rule_name,
    sorting_seconds=None,
    true_minification_seconds=None,
):
    report_run_subject = minified_run_subject or prerun_subject
    parent_path = path
    group_path = parent_path if os.path.basename(os.path.normpath(parent_path)).startswith("bug-group-") else None
    if group_path is not None:
        bug_folder = os.path.join(
            path,
            f"bug-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        )
    else:
        bug_folder = path
    matched_rule_folder = group_path

    print(f"[save_bug_report_custom] creating bug_folder: {os.path.abspath(bug_folder)}")

    os.makedirs(bug_folder, exist_ok=True)

    bug_filepath = os.path.join(bug_folder, "original_bug.html")
    shutil.copy(original_filepath, bug_filepath)

    minified_bug = os.path.join(bug_folder, "minified_bug.html")
    print(f"Saving minimized bug to {minified_bug}")
    save_as_web_page(report_run_subject, minified_bug, run_result=run_result)
    copyExternalJSFiles(bug_folder)

    styles_used = list(report_run_subject.all_style_names())
    styles_used.sort()
    styles_used_string = ",".join(styles_used)
    base_styles = list(report_run_subject.base_styles.all_style_names())
    modified_styles = list(report_run_subject.modified_styles.all_style_names())
    bug_type = "Page Crash" if run_result.type == BugType.PAGE_CRASH else "Under Invalidation"

    pickle_addr = os.path.join(bug_folder, "minified_run_subject.pkl")
    with open(pickle_addr, "wb") as f:
        pickle.dump(report_run_subject, f)

    prerun_subject_addr = os.path.join(bug_folder, "run_subject_prerun.pkl")
    with open(prerun_subject_addr, "wb") as f:
        pickle.dump(prerun_subject, f)

    json_data = {
        "datetime": datetime.now().isoformat(),
        "bug_type": bug_type,
        "styles_used": styles_used,
        "styles_used_string": styles_used_string,
        "base_styles": base_styles,
        "modified_styles": modified_styles,
        "variants": variants,
        "minified_run_subject": report_run_subject,
        "prerun_subject": prerun_subject,
        "pickle_addr": pickle_addr,
        "shouldSkip": shouldSkip,
        "matched_rule_name": rule_name,
        "matched_rule_folder": matched_rule_folder,
        "sorting_seconds": sorting_seconds,
        "true_minification_seconds": true_minification_seconds,
    }

    if isinstance(run_result, RunResultLayoutBug):
        json_data["differences"] = run_result.element_dimensions

    json_data_filepath = os.path.join(bug_folder, "data.json")
    with open(json_data_filepath, "w", encoding="utf-8") as f:
        f.write(json.dumps(json_data, indent=4, default=lambda o: o.__dict__))

    if group_path is not None:
        rule = recompute_bug_group_artifacts(group_path)
        if rule is None:
            moved_paths = dissolve_bug_group(group_path)
            moved_bug_folder = moved_paths.get(os.path.abspath(bug_folder))
            if moved_bug_folder is not None:
                minified_bug = os.path.join(moved_bug_folder, "minified_bug.html")

    url = "file://" + os.path.abspath(minified_bug)
    return url
