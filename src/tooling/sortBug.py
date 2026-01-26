#input a minified pickle
#do 1 of 3 things:
#each bug folder will have a list of pickles of each bug and one pickle of the tree
# 1. Already defined rules
    # loop 
        # merge with a rule folders to create a tree
        # if this new rule matches with all of that folders trees and none of the safe folders trees then add to that rule folder
# 2. Check folder of unkown bugs
    # loop
        # merge with eachk unknown bug to create a tree
        # if this new rule matches  none of the safe folders trees then create a new bug folder
# 3. Else add to unknown bugs folder

import datetime
import pickle
import os
import random

from tooling.treeComparison import run_subject_to_node_tree, merge_trees
from tooling.ruleConvergence import check_all_pkls, create_rule, extract_tag_tree, get_styles
from lqc.generate.web_page.create import save_as_web_page

def minified_pkls(*roots):
    paths = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                if name == "minified_run_subject.pkl":
                    paths.append(os.path.join(dirpath, name))
    random.shuffle(paths)
    for p in paths:
        yield p

gen = minified_pkls(
    r"bug_reports/test-repo2/skipped-bug-report",
    r"bug_reports/test-repo2/non-skipped-bug-report"
)

working_dir = f"bug_reports/sortRepo-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
os.makedirs(os.path.join(working_dir, "known-bugs"), exist_ok=True)
os.makedirs(os.path.join(working_dir, "unknown-bugs"), exist_ok=True)

safe_dir="bug_reports/test-repo2/safe"
print(f"Working dir: {working_dir}")
#working dir will have three folders: known bugs, unknown bugs
    #known bugss will have subfolders for each bug and pickle of the tree called merged_tree.pkl
        #each bug instance folder will have a pickles and html

    #unkwnown bugs will have pickles and html
for p in gen:
    print(p)
    with open(p, "rb") as f:
        run_subject = pickle.load(f)
    tree, startnode=run_subject_to_node_tree(run_subject)

    for bugFolder in os.listdir(os.path.join(working_dir, "known-bugs")):

        pkl_path = os.path.join(working_dir, "known-bugs", bugFolder, "merged_tree.pkl")
        with open(pkl_path, "rb") as f:
            merged_tree, merged_tree_startnode = pickle.load(f)
        #create a merged temp tree
        temp_tree, temp_startnode=merge_trees(startnode, merged_tree_startnode)
        bugInstancePath=os.path.join(working_dir, "known-bugs", bugFolder)
        rule = create_rule(extract_tag_tree(temp_tree), get_styles(temp_tree))
        #ceck all pkls in that bug folder and safe folder
        results, true_count, false_count=check_all_pkls(bugInstancePath,[rule])
        print("\n\nFinal Results:")
        print("Results for each pkl in bug folder:")
        print(f"positive matches: {true_count}")
        print(f"negative matches: {false_count}")
        
        results, true_count, false_count=check_all_pkls(safe_dir,[rule])
        print("\n\nFinal Results:")
        print("Results for each pkl in safe folder:")
        for path, r in results:
            print(f"{path}: {r}")
        print(f"positive matches: {true_count}")
        print(f"negative matches: {false_count}")


    #Search through unknown bugs
    #else add to unknown bugs folder
    working_unknown_bugs=os.path.join(working_dir, "unknown-bugs")
    base_name=f"unknown-bug{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
    with open(working_unknown_bugs+"/minified_run_subject.pkl", "wb") as f:
        pickle.dump((tree, startnode), f)
        save_as_web_page(run_subject, working_unknown_bugs+"base_name.html")




    

    
