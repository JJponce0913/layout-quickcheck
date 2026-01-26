import argparse
import json
from time import time
from tooling.ruleConvergence import create_rule, create_rule, extract_tag_tree, check_all_pkls,load_tree_start_pairs, merge_trees, get_styles

def run_graph_pipeline(base_folder, check_folder, include_text=True):
    #treeLists=[]
    #a result=(pos,neg)
    #baseLits=[results]
    #checkLists=[results]
    #initial tree
    #Loope
        #for each pkl in base_folder
            #load new tree
            #merge tree
            #check if it matches all pkls in base_folder
            #check if it matches any pkls in check_folder
            #append to results
    treeLists=[]
    ruleLists=[]
    baseLists=[]
    checkLists=[]

    pairs = load_tree_start_pairs(base_folder)
    _, cur_start = pairs.pop(0)

    for _, start_node in pairs:
        cur_tree, cur_start = merge_trees(cur_start, start_node)

        treeLists.append(cur_tree)

        rule = create_rule(extract_tag_tree(cur_tree), get_styles(cur_start))
        ruleLists.append(rule)

        results, true_count, false_count = check_all_pkls(check_folder, [rule])
        checkLists.append((true_count, false_count))
        results, true_count, false_count = check_all_pkls(base_folder, [rule])
        baseLists.append((true_count, false_count))

    return treeLists, ruleLists, baseLists, checkLists





if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--include_text", action="store_true")
    args = parser.parse_args()

    if args.runs == 1:
        base_folder = "bug_reports/test-repo/skipped-bug-report"
        check_folder = "bug_reports/test-repo/skipped-bug-report"
    elif args.runs == 2:
        base_folder = "bug_reports/test-repo2/skipped-bug-report"
        check_folder = "bug_reports/test-repo2/non-skipped-bug-report"
    elif args.runs == 3:
        base_folder = "bug_reports/test-repo/skipped-bug-report"
        check_folder = "bug_reports/test-repo/safe"
    elif args.runs == 4:
        base_folder = "bug_reports/test-repo/non-skipped-bug-report"
        check_folder = "bug_reports/test-repo/safe"
    else:
        raise ValueError("--runs must be 1, 2, 3, or 4")

    base_folder_abs = f"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/{base_folder}"
    check_folder_abs = f"C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/{check_folder}"

    results=run_graph_pipeline(base_folder_abs, check_folder_abs, include_text=args.include_text)

    for item in results:
        print("==== New Result ====")
        print(item)

