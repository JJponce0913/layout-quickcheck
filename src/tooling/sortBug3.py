import os
import sys
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.treeComparison import merge_trees, walk_tree_verbose


def group_dirs(known_dir):
    out = []
    for name in os.listdir(known_dir):
        p = os.path.join(known_dir, name)
        if os.path.isdir(p):
            out.append(p)
    out.sort()
    return out


def load_merged_tree_from_group(group_dir):
    p = os.path.join(group_dir, "merged_tree.pkl")
    with open(p, "rb") as f:
        merged_tree, merged_startnode = pickle.load(f)
    return merged_tree, merged_startnode


def merge_two_group_pkls(group_a_dir, group_b_dir):
    _, a_start = load_merged_tree_from_group(group_a_dir)
    _, b_start = load_merged_tree_from_group(group_b_dir)

    merged_tree, merged_start = merge_trees(a_start, b_start)
    return merged_tree, merged_start


def merge_all_groups_in_folder(known_dir):
    groups = group_dirs(known_dir)
    if not groups:
        raise RuntimeError("no group folders found")

    cur_tree, cur_start = load_merged_tree_from_group(groups[0])

    for g in groups[1:]:
        _, nxt_start = load_merged_tree_from_group(g)
        cur_tree, cur_start = merge_trees(cur_start, nxt_start)

    return cur_tree, cur_start, groups


def main():
    known_dir = r"C:\Users\pika1\source\repos\JJponce0913\layout-quickcheck\bug_reports\testFolders"
    out_pkl = os.path.join(known_dir, "ALL_MERGED.pkl")
    out_txt = os.path.join(known_dir, "ALL_MERGED.txt")

    cur_tree, cur_start, groups = merge_all_groups_in_folder(known_dir)

    with open(out_pkl, "wb") as f:
        pickle.dump((cur_tree, cur_start), f)

    with open(out_txt, "w", encoding="utf-8") as f:
        sys.stdout = f
        walk_tree_verbose(cur_tree)
        sys.stdout = sys.__stdout__

    print("merged_groups", len(groups))
    print("output_pickle", out_pkl)
    print("output_tree_txt", out_txt)


if __name__ == "__main__":
    main()
