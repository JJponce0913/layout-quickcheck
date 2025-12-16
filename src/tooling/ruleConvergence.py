from treeComparison import run_subject_to_node_tree, walk_tree, walk_tree_verbose, merge_trees
import os,pickle,time, re
from bs4 import BeautifulSoup
from lqc.generate.web_page.create import save_as_web_page

def load_tree_start_pairs(folder_path):
    pairs = []

    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.endswith(".pkl"):
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
def check_all_pkls(folder_path, rules):
    results = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.endswith(".pkl"):
                continue
            pkl_path = os.path.join(root, name)
            try:
                matched = checks(pkl_path, rules)
                results.append((pkl_path, matched))
            except Exception as e:
                results.append((pkl_path, f"ERROR: {e}"))
    false=0
    true=0
    for p, r in results:
        if r==True:
            false+=1
        else:
            true+=1
    return results, true, false
def create_html_pat(node):
    """
    Return the html_pattern-style list of direct child tags for the given node.
    Uses "text" for text nodes (#text) with non-empty content, mirroring check_pattern().
    """
    if node is None:
        return []

    def _children(n):
        # Prefer our Node.children list; fall back to firstchild/next chain if present.
        kids = getattr(n, "children", None)
        if kids is not None:
            return kids
        chain = []
        child = getattr(n, "firstchild", None)
        while child is not None:
            chain.append(child)
            child = getattr(child, "next", None)
        return chain

    pattern = []
    for child in _children(node):
        tag = getattr(child, "tag", None)
        if tag == "#text":
            text_val = getattr(child, "text", "")
            if isinstance(text_val, str) and not text_val.strip():
                continue
            pattern.append("text")
        elif tag:
            pattern.append(tag)

    return pattern

def get_styles(node):
    if node is None:
        return {}
    pairs= []
    for pair in list(node.modified_style.items()):
        pairs.append(list(pair))
    return pairs
def create_rule(html_pattern, styles):
    rule = {
        "name": str(time.time()),
        "rule_class": {
            "html_pattern": html_pattern,
            "style": styles
        }
    }
    return rule

def check_style(html_path, prop, value):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.I | re.S)
    js = "\n".join(scripts)
    m = re.search(r"function\s+makeStyleChanges\s*\(\s*\)\s*\{(.*?)\}", js, flags=re.S)
    if not m:
        return False
    body = m.group(1)
    prop_esc = re.escape(prop)
    value_esc = re.escape(value)
    bracket_pat = rf"\.style\[\s*['\"]{prop_esc}['\"]\s*\]\s*=\s*['\"]{value_esc}['\"]\s*;"
    dot_pat = rf"\.style\.\s*{prop_esc}\s*=\s*['\"]{value_esc}['\"]\s*;"
    return re.search(bracket_pat, body) is not None or re.search(dot_pat, body) is not None

def check_pattern(filename, pattern):
    with open(filename, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    need = {}
    for x in pattern:
        need[x] = need.get(x, 0) + 1

    for body in soup.find_all("body"):
        kids = [c for c in body.contents if getattr(c, "name", None) or str(c).strip()]
        have = {}
        for c in kids:
            if getattr(c, "name", None):
                k = c.name
            else:
                k = "text"
            have[k] = have.get(k, 0) + 1

        ok = True
        for k, cnt in need.items():
            if have.get(k, 0) < cnt:
                ok = False
                break
        if ok:
            return True

    return False


def checks(pkl_path, rules):
    with open(pkl_path, "rb") as f:
        run_subject = pickle.load(f)

    save_as_web_page(run_subject, "tmp_generated_files/rule_check.html", run_result=None)
    file = "tmp_generated_files/rule_check.html"

    for i, rule in enumerate(rules):
        html_pat = rule.get("rule_class", {}).get("html_pattern", [])
        styles = rule.get("rule_class", {}).get("style", [])

        patternFound = check_pattern(file, html_pat)

        styleFound = False
        styleHit = None
        for prop, values in styles:
            vals = values if isinstance(values, list) else [values]
            for v in vals:
                if check_style(file, prop, v):
                    styleFound = True
                    styleHit = (prop, v)
                    break
            if styleFound:
                break

        if patternFound and styleFound:
            return True

    return False


def merge_folder(folder_path):
    pairs = load_tree_start_pairs(folder_path)
    print(f"Loaded {len(pairs)} tree-start_node pairs.")

    if len(pairs) < 2:
        raise RuntimeError("Need at least 2 run_subject files to merge")

    _, curStartNode = pairs.pop(0)
    _, secondStartNode = pairs.pop(0)

    curTree, curStartNode = merge_trees(curStartNode, secondStartNode)
    merge_count = 1

    for _, start_node in pairs:
        curTree, curStartNode = merge_trees(curStartNode, start_node)
        merge_count += 1

    return curTree, curStartNode


if __name__ == "__main__":
    curTree, curStartNode = merge_folder("C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/bug_reports/test-repo/skipped-bug-report")
   
        
    print("\n\nFinal merged tree:")
    walk_tree_verbose(curTree)
    rules=[create_rule(create_html_pat(curTree),get_styles(curStartNode))]

    results,true,false = check_all_pkls("C:/Users/pika1/source/repos/JJponce0913/layout-quickcheck/safe", rules)
    
    print("\n\nFinal Results:")
    print(f"positive matches: {true}")
    print(f"negative matches: {false}")