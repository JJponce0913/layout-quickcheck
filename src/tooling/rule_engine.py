import datetime
import html
import io
import os
import pickle
import pprint
import random
import shutil
import time
import json
from contextlib import redirect_stdout

from tooling.tree_merge import run_subject_to_node_tree, merge_trees, walk_tree_verbose


def load_tree_start_pairs(folder_path):
    pairs = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.endswith("minified_run_subject.pkl"):
                continue
            if "run_subject" not in name:
                continue
            pkl_path = os.path.join(root, name)
            try:
                with open(pkl_path, "rb") as f:
                    run_subject = pickle.load(f)
                tree, start_node = run_subject_to_node_tree(run_subject)
                pairs.append((tree, start_node))
            except Exception:
                continue
    return pairs


def check_all_pkls(folder_path, rules, verbose=False):
    results = []
    folder_name = os.path.basename(os.path.normpath(folder_path))

    for root, _, files in os.walk(folder_path):
        for name in files:
            if not (name.endswith("run_subject_prerun.pkl") or "safe" in name or "run_subject.pkl" in name):
                continue

            pkl_path = os.path.join(root, name)
            try:
                with open(pkl_path, "rb") as f:
                    run_subject = pickle.load(f)

                matched = should_skip(run_subject, rules, verbose=verbose)
                if verbose:
                    print(f"[{folder_name}] {name}: {matched}")
                results.append((pkl_path, matched))

            except Exception as e:
                if verbose:
                    print(f"[{folder_name}] {name}: ERROR {e}")
                results.append((pkl_path, f"ERROR: {e}"))

    true_count = 0
    false_count = 0
    for _, r in results:
        matched = r[0] if isinstance(r, tuple) else r
        if matched is True:
            true_count += 1
        else:
            false_count += 1

    return results, true_count, false_count



def extract_tag_tree(node):
    if node is None:
        return None

    if isinstance(node, dict):
        tag = node.get("tag")
        children = node.get("children", []) or []
    else:
        tag = getattr(node, "tag", None)
        children = getattr(node, "children", []) or []

    out_children = []
    for c in children:
        t = extract_tag_tree(c)
        if t is not None:
            out_children.append(t)

    if tag == "body":
        return out_children

    if not out_children:
        return tag

    return [tag, out_children]


def get_modified_styles(node):
    if node is None:
        return []
    pairs = []
    for pair in list(node.modified_style.items()):
        pairs.append(list(pair))
    return pairs

def get_base_styles(node):
    if node is None:
        return []
    pairs = []
    for pair in list(node.base_style.items()):
        pairs.append(list(pair))
    return pairs

def get_all_styles(node):
    if node is None:
        return {}

    out = {}

    def dfs(n):
        if n is None:
            return
        if getattr(n, "tag", None) == "#text":
            return

        node_id = getattr(n, "id", "none")
        base = getattr(n, "base_style", None)
        modified = getattr(n, "modified_style", None)

        if base or modified:
            out[node_id] = {
                "base_style": dict(base) if base else {},
                "modified_style": dict(modified) if modified else {},
            }

        for c in getattr(n, "children", []) or []:
            dfs(c)

    dfs(node)
    return out


def create_rule(html_pattern,base_style, modified_style):
    return {
        "name": str(time.time()),
        "rule_class": {
            "base_style": base_style,
            "modified_style": modified_style,
            "html_pattern": html_pattern,
        },
    }



def merge_folder(folder_path):
    pairs = load_tree_start_pairs(folder_path)
    print(f"Loaded {len(pairs)} tree-start_node pairs.")

    if len(pairs) < 2:
        raise RuntimeError("Need at least 2 run_subject files to merge")

    _, cur_start = pairs.pop(0)
    _, other_start = pairs.pop(0)

    cur_tree, cur_start = merge_trees(cur_start, other_start)

    for _, start_node in pairs:
        cur_tree, cur_start = merge_trees(cur_start, start_node)

    return cur_tree, cur_start


def _render_tree_html(tree_root):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        walk_tree_verbose(tree_root)
    tree_text = html.escape(buffer.getvalue())
    return f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Bug Group Tree</title>
  </head>
  <body>
    <pre>{tree_text}</pre>
  </body>
</html>
"""


def recompute_bug_group_artifacts(group_dir):
    bug_instances = []
    for name in os.listdir(group_dir):
        if not name.startswith("bug-") or name.startswith("bug-group-"):
            continue

        bug_dir = os.path.join(group_dir, name)
        if not os.path.isdir(bug_dir):
            continue

        pickle_path = os.path.join(bug_dir, "minified_run_subject.pkl")
        if not os.path.exists(pickle_path):
            continue

        with open(pickle_path, "rb") as f:
            run_subject = pickle.load(f)

        tree, start_node = run_subject_to_node_tree(run_subject)
        if start_node is None:
            continue

        bug_instances.append((tree, start_node))

    if not bug_instances:
        return None

    merged_tree, merged_start = bug_instances[0]
    for next_tree, next_start in bug_instances[1:]:
        merged_tree, merged_start = merge_trees(merged_start, next_start)

    rule = create_rule(
        extract_tag_tree(merged_tree),
        get_base_styles(merged_start),
        get_modified_styles(merged_start),
    )

    if rule.get("rule_class", {}).get("modified_style") == []:
        tree_pickle_path = os.path.join(group_dir, "tree.pkl")
        tree_html_path = os.path.join(group_dir, "tree.html")
        extracted_rule_path = os.path.join(group_dir, "extracted_rule.json")
        for artifact_path in (tree_pickle_path, tree_html_path, extracted_rule_path):
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
        return None

    tree_pickle_path = os.path.join(group_dir, "tree.pkl")
    with open(tree_pickle_path, "wb") as f:
        pickle.dump((merged_tree, merged_start), f)

    tree_html_path = os.path.join(group_dir, "tree.html")
    with open(tree_html_path, "w", encoding="utf-8") as f:
        f.write(_render_tree_html(merged_tree))

    extracted_rule_path = os.path.join(group_dir, "extracted_rule.json")
    with open(extracted_rule_path, "w", encoding="utf-8") as f:
        json.dump(rule, f, indent=2)

    return rule


def node_to_ordered_tokens(root, include_text=True):
    def keep_text(n):
        txt = getattr(n, "text", "")
        return (not isinstance(txt, str)) or bool(txt.strip())

    def build_token(n):
        if n is None:
            return None

        tag = getattr(n, "tag", None)

        if tag == "#text":
            if not include_text:
                return None
            if not keep_text(n):
                return None
            return "#text"

        if not tag:
            return None

        kids = []
        for c in getattr(n, "children", []) or []:
            v = build_token(c)
            if v is not None:
                kids.append(v)

        if not kids:
            return tag
        return [tag, kids]

    out = []
    for c in getattr(root, "children", []) or []:
        v = build_token(c)
        if v is not None:
            out.append(v)
    return out


def all_ordered_patterns_unique(tree_root, include_text=True, contiguous=True):
    tokens = node_to_ordered_tokens(tree_root, include_text=include_text)

    def freeze(x):
        if isinstance(x, list):
            return tuple(freeze(y) for y in x)
        return x

    def unfreeze(x):
        if isinstance(x, tuple):
            return [unfreeze(y) for y in x]
        return x

    def dedupe_choices(choices):
        seen = set()
        out = []
        for c in choices:
            fc = freeze(c)
            if fc not in seen:
                seen.add(fc)
                out.append(c)
        return out

    def patterns_from_sequence(token_choices):
        token_choices = [dedupe_choices(c) for c in token_choices]
        n = len(token_choices)
        out = set()

        if contiguous:
            for i in range(n):
                acc = [[]]
                for j in range(i, n):
                    nxt = []
                    for a in acc:
                        for c in token_choices[j]:
                            nxt.append(a + [c])
                    acc = nxt
                    for seq in acc:
                        if seq:
                            out.add(freeze(seq))
            return [unfreeze(p) for p in out]

        idxs_all = []
        cur = []

        def rec(i):
            if i == n:
                if cur:
                    idxs_all.append(cur[:])
                return
            cur.append(i)
            rec(i + 1)
            cur.pop()
            rec(i + 1)

        rec(0)

        for idxs in idxs_all:
            pools = [token_choices[i] for i in idxs]
            acc = [[]]
            for choices in pools:
                nxt = []
                for a in acc:
                    for c in choices:
                        nxt.append(a + [c])
                acc = nxt
            for seq in acc:
                if seq:
                    out.add(freeze(seq))

        return [unfreeze(p) for p in out]

    def subtree_variants(node):
        if not isinstance(node, list):
            return [node]
        tag = node[0]
        kids = node[1] if len(node) > 1 and isinstance(node[1], list) else []
        out = [tag]
        if kids:
            kid_choices = [expand_token(t) for t in kids]
            for kp in patterns_from_sequence(kid_choices):
                out.append([tag, kp])
        return dedupe_choices(out)

    def expand_token(tok):
        if isinstance(tok, str):
            if tok == "#text" and not include_text:
                return []
            return [tok]
        return subtree_variants(tok)

    token_choices = [expand_token(t) for t in tokens]
    token_choices = [dedupe_choices(c) for c in token_choices]
    patterns = patterns_from_sequence(token_choices)

    seen = set()
    unique = []
    for p in patterns:
        fp = freeze(p)
        if fp not in seen:
            seen.add(fp)
            unique.append(p)
    return unique


def pattern_to_key(p):
    return json.dumps(p, separators=(",", ":"), ensure_ascii=False)


def _node_id(n):
    nid = getattr(n, "id", None)
    if nid and nid != "none":
        return nid
    return None


def _children(n):
    return getattr(n, "children", []) or []

def _match_sequence_exact(nodes, pat, include_text=True):
    out_ids = []
    for n, t in zip(nodes, pat):
        tag = getattr(n, "tag", None)

        if isinstance(t, list) and len(t) == 1 and isinstance(t[0], str):
            t = t[0]

        if isinstance(t, str):
            if t == "#text":
                if not include_text:
                    return (False, [])
                if tag != "#text":
                    return (False, [])
                txt = getattr(n, "text", "")
                if isinstance(txt, str) and not txt.strip():
                    return (False, [])
            else:
                if tag != t:
                    return (False, [])
                nid = _node_id(n)
                if nid:
                    out_ids.append(nid)
            continue

        if not isinstance(t, list) or len(t) != 2:
            return (False, [])

        want_tag, kid_pat = t[0], t[1]
        if tag != want_tag:
            return (False, [])

        nid = _node_id(n)
        if nid:
            out_ids.append(nid)

        ok, kid_ids = _match_sequence_anywhere(_children(n), kid_pat, include_text=include_text)
        if not ok:
            return (False, [])
        out_ids.extend(kid_ids)

    return (True, out_ids)



def _match_sequence_anywhere(nodes, pat, include_text=True):
    m = len(pat)
    if m == 0:
        return (True, [])
    for i in range(0, len(nodes) - m + 1):
        ok, ids = _match_sequence_exact(nodes[i : i + m], pat, include_text=include_text)
        if ok:
            return (True, ids)
    return (False, [])


def _pattern_has_diff(p):
    if isinstance(p, str):
        return p == "diff"
    if isinstance(p, list):
        return any(_pattern_has_diff(x) for x in p)
    return False

def _match_sequence_exact_wild(nodes, pat, include_text=True):
    def keep_text(n):
        txt = getattr(n, "text", "")
        return (not isinstance(txt, str)) or bool(txt.strip())

    out_ids = []
    for n, t in zip(nodes, pat):
        tag = getattr(n, "tag", None)

        if isinstance(t, list) and len(t) == 1 and isinstance(t[0], str):
            t = t[0]

        if isinstance(t, str):
            if t == "diff":
                if tag == "#text":
                    if not include_text or not keep_text(n):
                        return (False, [])
                else:
                    nid = _node_id(n)
                    if nid:
                        out_ids.append(nid)
                continue
            if t == "#text":
                if not include_text:
                    return (False, [])
                if tag != "#text":
                    return (False, [])
                if not keep_text(n):
                    return (False, [])
            else:
                if tag != t:
                    return (False, [])
                nid = _node_id(n)
                if nid:
                    out_ids.append(nid)
            continue

        if not isinstance(t, list) or len(t) != 2:
            return (False, [])

        want_tag, kid_pat = t[0], t[1]
        if want_tag != "diff" and tag != want_tag:
            return (False, [])
        if tag == "#text":
            return (False, [])

        nid = _node_id(n)
        if nid:
            out_ids.append(nid)

        ok, kid_ids = _match_sequence_anywhere_wild(_children(n), kid_pat, include_text=include_text)
        if not ok:
            return (False, [])
        out_ids.extend(kid_ids)

    return (True, out_ids)



def _match_sequence_anywhere_wild(nodes, pat, include_text=True):
    m = len(pat)
    if m == 0:
        return (True, [])
    for i in range(0, len(nodes) - m + 1):
        ok, ids = _match_sequence_exact_wild(nodes[i : i + m], pat, include_text=include_text)
        if ok:
            return (True, ids)
    return (False, [])


def _walk_all_nodes(root):
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        for c in reversed(_children(n)):
            stack.append(c)


def ids_by_pattern(tree_root, patterns, include_text=True):
    out = {pattern_to_key(p): [] for p in patterns}

    for n in _walk_all_nodes(tree_root):
        kids = _children(n)
        if not kids:
            continue

        for p in patterns:
            key = pattern_to_key(p)
            m = len(p)
            if m == 0 or len(kids) < m:
                continue

            for i in range(0, len(kids) - m + 1):
                ok, ids = _match_sequence_exact(kids[i : i + m], p, include_text=include_text)
                if ok:
                    out[key].append(ids)

    return out

def id_with_styles(styles_list, base_styles, modified_styles):
    ids = []

    for node_id, data in styles_list.items():
        base = data.get("base_style", {})
        modified = data.get("modified_style", {})

        match = True

        for k, v in base_styles:
            if v == "diff":
                continue
            if base.get(k) != v:
                match = False
                break

        if not match:
            continue

        for k, v in modified_styles:
            if v == "diff":
                continue
            if modified.get(k) != v:
                match = False
                break

        if match:
            ids.append(node_id)

    return ids

def follow_html_and_style_pattern(style_ids, mapping, html_pattern, tree_root):
    if _pattern_has_diff(html_pattern):
        pat = html_pattern if isinstance(html_pattern, list) else [html_pattern]
        for hit in _iter_pattern_hits_wild(tree_root, pat, include_text=True):
            for node_id in style_ids:
                if node_id in hit:
                    return True
        return False

    key = pattern_to_key(html_pattern) if isinstance(html_pattern, list) else html_pattern
    pattern_hits = mapping.get(key, [])

    for node_id in style_ids:
        for hit in pattern_hits:
            if node_id in hit:
                return True
    return False


def _iter_pattern_hits_wild(tree_root, pat, include_text=True):
    m = len(pat)
    for n in _walk_all_nodes(tree_root):
        kids = _children(n)
        if not kids or len(kids) < m:
            continue
        for i in range(0, len(kids) - m + 1):
            ok, ids = _match_sequence_exact_wild(kids[i : i + m], pat, include_text=include_text)
            if ok:
                yield ids



def should_skip(run_subject, rules, verbose=False):
    tree, _ = run_subject_to_node_tree(run_subject)
    styles_list = get_all_styles(tree)
    patterns = all_ordered_patterns_unique(tree)
    mapping = ids_by_pattern(tree, patterns, include_text=True)

    for rule in rules:
        html_pat = rule.get("rule_class", {}).get("html_pattern", [])
        base_styles=rule.get("rule_class", {}).get("base_style", [])
        modified_styles = rule.get("rule_class", {}).get("modified_style", [])

        style_ids = id_with_styles(styles_list, base_styles, modified_styles)
        if verbose:
            print("Style check result ids")
            print(style_ids)

        html_match = follow_html_and_style_pattern(style_ids, mapping, html_pat, tree)
        if verbose:
            print("HTML pattern check result")
            print(html_match)

        if html_match:
            if verbose:
                print("Rule matched, should skip.")
            return True, rule.get("name", "unknown")

    return False, None

    
def sort_single_bug(base_dir, run_subject, safe_dir, verbose=False):
    """
    Args:
        base_dir: Root folder containing grouped bugs as `bug-group-*` folders
            and ungrouped single bugs as `bug-*` folders.
        run_subject: The bug instance being classified.
        safe_dir: Folder of known-safe pickle files used to reject unsafe rules.

    Returns:
        A tuple of `(path, shouldSkip, rule_name)`.
    """
    def log(message=""):
        if verbose:
            print(message)

    tree, startnode = run_subject_to_node_tree(run_subject)
    log("\n[sort_single_bug] start")
    log(f"[sort_single_bug] base_dir={os.path.abspath(base_dir)}")
    log(f"[sort_single_bug] safe_dir={os.path.abspath(safe_dir)}")
    if verbose:
        print("\n[sort_single_bug] incoming_run_subject_tree:")
        pprint.pprint(extract_tag_tree(tree))
        print("\n[sort_single_bug] incoming_run_subject_base_styles:")
        pprint.pprint(get_base_styles(startnode))
        print("\n[sort_single_bug] incoming_run_subject_modified_styles:")
        pprint.pprint(get_modified_styles(startnode))

    if startnode is None:
        log("[sort_single_bug] incoming_run_subject_has_no_start_node")
        new_unknown = f"bug-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
        log(f"[sort_single_bug] creating_new_single_bug={os.path.join(base_dir, new_unknown)}")
        return os.path.join(base_dir, new_unknown), False, None

    os.makedirs(base_dir, exist_ok=True)

    # First try to match the incoming bug against an existing grouped bug cluster.
    for bugFolder in os.listdir(base_dir):
        if not bugFolder.startswith("bug-group-"):
            continue

        bugGroupPath = os.path.join(base_dir, bugFolder)
        if not os.path.isdir(bugGroupPath):
            continue

        log(f"\n[sort_single_bug] checking_known_group={bugGroupPath}")

        merged_path = os.path.join(bugGroupPath, "tree.pkl")

        if not os.path.exists(merged_path):
            log(f"[sort_single_bug] missing_merged_tree={merged_path}")
            continue

        with open(merged_path, "rb") as f:
            _, merged_start = pickle.load(f)

        temp_tree, temp_start = merge_trees(startnode, merged_start)

        rule = create_rule(
            extract_tag_tree(temp_tree),
            get_base_styles(temp_start),
            get_modified_styles(temp_start),
        )
        if rule.get("rule_class", {}).get("modified_style") == []:
            log(f"[sort_single_bug] known_group_candidate_has_no_modified_styles, skipping={bugGroupPath}")
            continue
        if verbose:
            print("[sort_single_bug] known_group_candidate_rule:")
            pprint.pprint(rule)

        _, true_safe, _ = check_all_pkls(safe_dir, [rule], verbose=verbose)
        log(f"[sort_single_bug] known_group_counts true_safe={true_safe}")

        # Reuse the group only if the merged rule does not reject grouped bugs
        # and does not match any known-safe cases.
        if true_safe < 10:
            log(f"[sort_single_bug] matched_existing_group={bugGroupPath}")
            return bugGroupPath, True, rule.get("name", "unknown")

    # Next try to combine the bug with an ungrouped single-bug folder and
    # promote that pair into a new bug group when the rule stays safe.
    for bugFolder in os.listdir(base_dir):
        if not bugFolder.startswith("bug-") or bugFolder.startswith("bug-group-"):
            continue

        bugInstancePath = os.path.join(base_dir, bugFolder)
        if not os.path.isdir(bugInstancePath):
            continue

        log(f"\n[sort_single_bug] checking_single_bug={bugInstancePath}")

        tree_path = os.path.join(bugInstancePath, "minified_run_subject.pkl")

        if not os.path.exists(tree_path):
            log(f"[sort_single_bug] missing_tree={tree_path}")
            continue

        with open(tree_path, "rb") as f:
            existing_run_subject = pickle.load(f)
        log(existing_run_subject)

        _, unknown_start = run_subject_to_node_tree(existing_run_subject)
        if unknown_start is None:
            log(f"[sort_single_bug] existing_single_bug_has_no_start_node={bugInstancePath}")
            continue

        temp_tree, temp_start = merge_trees(startnode, unknown_start)

        rule = create_rule(
            extract_tag_tree(temp_tree),
            get_base_styles(temp_start),
            get_modified_styles(temp_start),
        )
        if rule.get("rule_class", {}).get("modified_style") == []:
            log(f"[sort_single_bug] merged_rule_has_no_modified_styles, skipping={bugInstancePath}")
            continue
        
        if verbose:
            print("[sort_single_bug] promote_single_bug_candidate_rule:")
            pprint.pprint(rule)

        _, true_safe, _ = check_all_pkls(safe_dir, [rule], verbose=verbose)
        log(f"[sort_single_bug] single_bug_counts true_safe={true_safe}")

        if true_safe <10:
            new_folder_name = f"bug-group-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
            new_group_path = os.path.join(base_dir, new_folder_name)
            os.makedirs(new_group_path, exist_ok=True)
            promoted_bug_path = os.path.join(new_group_path, os.path.basename(bugInstancePath))
            shutil.move(bugInstancePath, promoted_bug_path)
            log(f"[sort_single_bug] promote_to_new_group={new_group_path}")
            log(f"[sort_single_bug] moved_existing_bug_into_group={promoted_bug_path}")
            if verbose:
                print(f"[sort_single_bug] new_group_rule:")
                pprint.pprint(rule)
            return new_group_path, False, None

    # If no safe grouping is possible, keep the bug as a standalone instance.
    new_unknown = f"bug-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
    log(f"[sort_single_bug] creating_new_single_bug={os.path.join(base_dir, new_unknown)}")
    return os.path.join(base_dir, new_unknown), False, None


