import os,pickle,time, re
from treeComparison import run_subject_to_node_tree,walk_tree, walk_tree_verbose, merge_trees
from ruleConvergence import get_styles, get_all_styles, extract_tag_tree_with_ids,extract_tag_tree
pkl_path = "C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/test-repo/non-skipped-bug-report/non-skipped-bug-report-2026-01-11-23-42-44-312495/run_subject_prerun.pkl"
with open(pkl_path, "rb") as f:
    run_subject = pickle.load(f)
    tree, start_node = run_subject_to_node_tree(run_subject)
    print(f"Loaded run_subject from {pkl_path}")

walk_tree_verbose(tree)
htmlpat=extract_tag_tree(tree)
idHtml=extract_tag_tree_with_ids(tree)
styles=get_styles(tree)
styles_list = get_all_styles(tree)
print(f"All styles ({len(styles_list)}):")
print(styles_list)
print("html pattern with ids:")
print(idHtml)
print("")
print("Created html pattern and styles.")
print("HTML Pattern:")
print(htmlpat)
print("Styles:")
print(styles)