import os
from datetime import datetime
from shutil import copy2
from lqc.config.file_config import FileConfig
from lqc.generate.web_page.create import save_as_web_page
from lqc.generate.web_page.javascript.create import EXTERNAL_JS_FILE_PATHS

def copyExternalJSFiles(folder):
    for filepath in EXTERNAL_JS_FILE_PATHS:
        copy2(filepath, folder)

def saveTestSubjectAsWebPage(run_subject):
    file_config = FileConfig()
    layout_folder_name = os.path.basename(file_config.layout_file_dir)
    folder, filepath = file_config.getCustomTimestampPath(
        layout_folder_name,
        filename=f"test-file.html"
    )
    folder = file_config.layout_file_dir
    copyExternalJSFiles(folder)
    save_as_web_page(run_subject, filepath)
    url = "file://" + os.path.abspath(filepath)

    return filepath, url
