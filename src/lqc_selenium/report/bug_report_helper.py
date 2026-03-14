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


def save_bug_report(
    variants,
    run_result: RunResult,
    original_filepath,
    prerun_subject: RunSubject,
    minified_run_subject: RunSubject = None,
):
    file_config = FileConfig()

    bug_folder = file_config.getCustomTimestampBugReport("bug-directory")

    os.mkdir(bug_folder)

    bug_filepath = os.path.join(bug_folder, "original_bug.html")
    shutil.copy(original_filepath, bug_filepath)

    subject_to_save = minified_run_subject if minified_run_subject is not None else prerun_subject

    minified_bug = os.path.join(bug_folder, "minified_bug.html")
    print(f"Saving minimized bug to {minified_bug}")
    save_as_web_page(subject_to_save, minified_bug, run_result=run_result)
    copyExternalJSFiles(bug_folder)

    styles_used = list(subject_to_save.all_style_names())
    styles_used.sort()
    styles_used_string = ",".join(styles_used)
    base_styles = list(subject_to_save.base_styles.all_style_names())
    modified_styles = list(subject_to_save.modified_styles.all_style_names())
    bug_type = "Page Crash" if run_result.type == BugType.PAGE_CRASH else "Under Invalidation"

    pickle_addr = os.path.join(bug_folder, "run_subject.pkl")
    with open(pickle_addr, "wb") as f:
        pickle.dump(subject_to_save, f)

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
        "prerun_subject": prerun_subject,
        "pickle_addr": pickle_addr,
        "used_minified_run_subject": minified_run_subject is not None,
    }

    if minified_run_subject is not None:
        json_data["minified_run_subject"] = minified_run_subject

    if isinstance(run_result, RunResultLayoutBug):
        json_data["differences"] = run_result.element_dimensions

    json_data_filepath = os.path.join(bug_folder, "data.json")
    with open(json_data_filepath, "w") as f:
        f.write(json.dumps(json_data, indent=4, default=lambda o: o.__dict__))

    url = "file://" + os.path.abspath(minified_bug)
    return {
        "url": url,
        "bug_folder": os.path.abspath(bug_folder),
        "pickle_addr": os.path.abspath(pickle_addr),
        "json_data_path": os.path.abspath(json_data_filepath),
    }