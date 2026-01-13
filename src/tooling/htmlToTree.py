import pickle
from treeComparison import run_subject_to_node_tree
from lqc.generate.web_page.create import save_as_web_page

PKL_PATH = "C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/test-repo/non-skipped-bug-report/non-skipped-bug-report-2026-01-11-22-45-13-932078/run_subject_prerun.pkl"
OUT_HTML = "tmp_generated_files/tmp.html"

with open(PKL_PATH, "rb") as f:
    run_subject = pickle.load(f)

tree, start_node = run_subject_to_node_tree(run_subject)
print(f"Loaded run_subject from {PKL_PATH}")

save_as_web_page(run_subject, OUT_HTML, run_result=None)
