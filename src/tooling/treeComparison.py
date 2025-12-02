from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
import re

class Node:
    def __init__(self, id="none", attrs=None, parent=None):
        if attrs is None:
            attrs = {}
        self.id = id
        self.attrs = attrs
        self.parent = parent
        self.children = []

    def __str__(self):
        tag = self.attrs.get("tag", "")
        parent_id = self.parent.id if self.parent is not None else None
        return f"Node(tag={tag}, attrs={self.attrs}, id={self.id}, parent_id={parent_id}, children={len(self.children)})"

    def get_parent(self):
        return self.parent


class TextNode(Node):
    def __init__(self, text, parent=None):
        super().__init__(id="text_node", attrs={"tag": "#text", "text": text}, parent=parent)

    def __str__(self):
        return f"TextNode(text={self.attrs['text']})"


def first_make_style_element(html_path):
    with open(html_path, encoding="utf8") as f:
        src = f.read()
    func_match = re.search(
        r'function\s+makeStyleChanges\s*\([^)]*\)\s*\{(.*?)\}',
        src,
        re.DOTALL,
    )
    if not func_match:
        return None
    body = func_match.group(1)
    m = re.search(
        r'([A-Za-z_$][\w$]*)\.style\[\s*["\'][^"\']+["\']\s*\]\s*=\s*["\'][^"\']+["\']',
        body,
    )
    if not m:
        return None
    return m.group(1)


def parse_style(style_str):
    style_dict = {}
    for part in style_str.split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        prop, val = part.split(":", 1)
        style_dict[prop.strip()] = val.strip()
    return style_dict


def build_tree(bs_node, parent=None):
    if isinstance(bs_node, NavigableString):
        text = str(bs_node).strip()
        if not text:
            return None
        return TextNode(text, parent=parent)

    if getattr(bs_node, "name", None) is None:
        return None
    
    attrs = dict(bs_node.attrs)
    attrs["tag"] = bs_node.name

    if "style" in attrs:
        attrs["style"] = parse_style(attrs["style"])
    
    node_id = attrs.get("id", "none")

    if str(node_id) == "lqc_dev_controls":
        return None
    
    n = Node(node_id, attrs, parent)
    for child in bs_node.children:
        child_node = build_tree(child, parent=n)
        if child_node is not None:
            n.children.append(child_node)
    return n


def html_file_to_tree(path): 
    firstNodeName = first_make_style_element(path) 
    html = Path(path).read_text(encoding="utf8") 
    soup = BeautifulSoup(html, "html.parser") 
    root = soup.body 
    tree = build_tree(root) 
    targetNode = find_node_by_id(tree, firstNodeName) 
    return tree, targetNode


def walk_tree(n, depth=0):
    indent = "  " * depth
    tag = n.attrs.get("tag", "")

    if isinstance(n, TextNode) or tag == "#text":
        text= n.attrs.get("text", "")
        print(indent + "TextNode: " + repr(text))
    else:
        label = tag
        if n.id != "none":
            label += f"#{n.id}"
        print(indent + label)

    for child in n.children:
        walk_tree(child, depth + 1)


def walk_tree_verbose(n, depth=0):
    indent = "  " * depth
    tag = n.attrs.get("tag", "")
    parent_id = n.parent.id if n.parent is not None else None
    print(f"{indent}Node:")
    print(f"{indent}  tag: {tag}")
    print(f"{indent}  id: {n.id}")
    print(f"{indent}  parent_id: {parent_id}")
    print(f"{indent}  attrs: {n.attrs}")
    print(f"{indent}  children_count: {len(n.children)}")
    for child in n.children:
        walk_tree_verbose(child, depth + 1)


def find_node_by_id(n, target_id):
    if n.id == target_id:
        return n
    for child in n.children:
        result = find_node_by_id(child, target_id)
        if result is not None:
            return result
    return None


def merge_attrs(n1, n2):
    tag1 = n1.attrs.get("tag")
    tag2 = n2.attrs.get("tag")
    if tag1 != tag2:
        return {"tag": "empty"}

    attrs = {}
    keys1 = set(n1.attrs.keys()) 
    keys2 = set(n2.attrs.keys()) 
    shared_keys = keys1 & keys2

    for key in shared_keys:
        v1 = n1.attrs[key]
        v2 = n2.attrs[key]

        if key == "style" and isinstance(v1, dict) and isinstance(v2, dict):
            style_result = {}
            shared_props = set(v1.keys()) & set(v2.keys())
            for prop in shared_props:
                if v1[prop] == v2[prop]:
                    style_result[prop] = v1[prop]
                else:
                    style_result[prop] = "diff"
            if style_result:
                attrs["style"] = style_result
        else:
            if v1 == v2:
                attrs[key] = v1
            else:
                attrs[key] = "diff"

    return attrs

def build_common_tree(n1, n2, debug=False):

    # ---------- debug logging helper ----------
    def log(*args, **kwargs):
        if debug:
            print(*args, **kwargs)

    # ---------- helper to create placeholder "empty" nodes ----------
    def create_empty_node(parent):
        return Node(id="empty", attrs={"tag": "empty"}, parent=parent)

    # ---------- helper to merge two single nodes into one common node ----------
    def merge_nodes(a, b, parent):
        log(f"\nMerging nodes:\n  a: {a}\n\n  b: {b}\n")
        if a is None and b is None:
            return None
        if a is None or b is None:
            return None

        tag1 = a.attrs.get("tag")
        tag2 = b.attrs.get("tag")
        log(f"Tags: a: {tag1}, b: {tag2}")

        if tag1 == "#text" and tag2 == "#text":
            text1 = a.attrs.get("text", "")
            text2 = b.attrs.get("text", "")
            if text1 == text2:
                return TextNode(text1, parent=parent)
            return TextNode("diff", parent=parent)

        if tag1 == tag2:
            attrs = merge_attrs(a, b)
            node_id = a.id if a.id == b.id else "none"
            return Node(node_id, attrs, parent)

        return create_empty_node(parent)

    # ---------- recursive merge of subtrees rooted at a and b ----------
    def build_down(a, b, parent=None, is_start_root=False):
        node = merge_nodes(a, b, parent)
        log(
            "Building down:\n"
            f"  a:   {a}\n\n"
            f"  b:   {b}\n\n"
            f"  mergenode: {node}\n"
        )

        if node is None:
            return None

        if is_start_root:
            node.id = "starting node"

        if node.attrs.get("tag") == "empty":
            return node

        children_count = max(len(a.children), len(b.children))
        for i in range(children_count):
            c1 = a.children[i] if i < len(a.children) else None
            c2 = b.children[i] if i < len(b.children) else None
            child = build_down(c1, c2, parent=node)
            if child is not None:
                node.children.append(child)

        return node

    # ---------- build common subtree rooted at the given nodes ----------
    log("n1:", n1)
    log("n2:", n2)
    log("\n\n")

    current = build_down(n1, n2, parent=None, is_start_root=True)
    if current is None:
        return None
    current.id = "common_root"
    startingNode = current
    log("Starting Node:", current)

    # ---------- climb parents in lockstep to aligned ancestors ----------
    p1 = n1.parent
    p2 = n2.parent
    log("\n\nParent 1:", p1)
    log("\n\nParent 2:", p2)

    cnt = 0
    while p1.parent is not None and p2.parent is not None:
        p1 = p1.parent
        p2 = p2.parent
        log("Loop: ", cnt)
        log("\n\nParent 1:", p1)
        log("\n\nParent 2:", p2)
        cnt += 1

    # ---------- build common tree for those ancestor roots ----------
    log("\n\nBuilding up...\n")
    parent = build_down(p1, p2, parent=None)
    log("\n\nBuilding up...\n")
    log("parent", parent)
    if debug:
        walk_tree_verbose(parent)

    # ---------- find sibling lists for the original nodes ----------
    s1 = n1.parent.children
    s2 = n2.parent.children
    log("\n\nSiblings 1:", s1)
    log("\n\nSiblings 2:", s2)

    for i1 in range(len(s1)):
        if s1[i1] == n1:
            log(i1)
            log("Sibling 1:", s1[i1])
            break

    for i2 in range(len(s2)):
        if s2[i2] == n2:
            log(i2)
            log("Sibling 2:", s2[i2])
            break

    # ---------- align siblings around the starting nodes ----------
    log("\n\nMerging left siblings starting at indices:", i1, i2)
    si1 = i1
    si2 = i2
    sif = 0

    while i1 - 1 >= 0 and i2 - 1 >= 0:
        sif += 1
        i1 -= 1
        i2 -= 1

    log("sif:", sif)
    log("\n\nMerging left siblings starting at indices:", i1, i2)

    # ---------- merge sibling subtrees and insert startingNode ----------
    siblings = []
    while i1 < len(s1) and i2 < len(s2):
        log("Merging siblings:\n", s1[i1], "\n", s2[i2])
        sibling_node = build_down(s1[i1], s2[i2], parent=parent)
        if sibling_node is not None:
            siblings.append(sibling_node)
        i1 += 1
        i2 += 1

    log("\n\nMerged Siblings:", siblings)
    parent.children = siblings
    siblings[sif] = startingNode
    return parent, startingNode






if __name__ == "__main__":
    file1 = (
        "bug_reports/PRE/postSkip-bug-report/"
        "postSkip-bug-report-2025-11-25-12-57-03-292812/minified_bug.html"
    )
    file2 = (
        "bug_reports/PRE/postSkip-bug-report/"
        "postSkip-bug-report-2025-11-25-12-57-40-244373/minified_bug.html"
    )

    tree1, start1 = html_file_to_tree(file1)
    tree2, start2 = html_file_to_tree(file2)

    print("Tree 1:")
    walk_tree_verbose(tree1)

    print("\n\nTree 2:")
    walk_tree(tree2)

    print("\n\nCommon tree...\n")
    common_tree1, common_root1 = build_common_tree(start1, start2)
    print("first", common_root1)
    walk_tree_verbose(common_tree1)

    print("\n\nCommon tree Done\n")
    common_tree2, common_root2 = build_common_tree(start1, common_root1)
    print("\n\nCommon tree 2...\n")
    walk_tree_verbose(common_tree2)
    print("\n\nCommon tree 2 Done\n")

