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
        text = n.attrs.get("text", "")
        print(indent + repr(text))
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

def build_common_tree(n1, n2):
    def create_empty_node(parent):
        return Node(id="empty", attrs={"tag": "empty"}, parent=parent)

    def merge_nodes(a, b, parent):
        print(f"Merging nodes:\n  a: {a}\n  b: {b}\n")
        if a is None and b is None:
            return None
        if a is None or b is None:
            return None

        tag1 = a.attrs.get("tag")
        tag2 = b.attrs.get("tag")

        if tag1 == "#text" and tag2 == "#text":
            text1 = a.attrs.get("text", "")
            text2 = b.attrs.get("text", "")
            if text1 == text2:
                return TextNode(text1, parent=parent)
            return create_empty_node(parent)

        if tag1 == tag2:
            attrs = merge_attrs(a, b)
            node_id = a.id if a.id == b.id else "none"
            return Node(node_id, attrs, parent)

        return create_empty_node(parent)

    def build_down(a, b, parent=None, is_start_root=False):
        node = merge_nodes(a, b, parent)
        print(
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

    current = build_down(n1, n2, parent=None, is_start_root=True)
    if current is None:
        return None
    current.id = "common_root"
    startingNode = current
    print("Starting Node:", current)

    p1 = n1.parent
    p2 = n2.parent
    print("p1", p1)
    print("p2", p2)
    while p1 is not None and p2 is not None:
        new_parent = merge_nodes(p1, p2, parent=None)
        if new_parent is None:
            break

        current.parent = new_parent
        new_parent.children = [current]

        current = new_parent
        p1 = p1.parent
        p2 = p2.parent

    print("Parent Node:",startingNode.parent)

    parent = startingNode.parent
    if parent is not None and n1.parent is not None and n2.parent is not None:
        ch1 = n1.parent.children
        ch2 = n2.parent.children
        max_children = max(len(ch1), len(ch2))
        for i in range(max_children):
            c1 = ch1[i] if i < len(ch1) else None
            c2 = ch2[i] if i < len(ch2) else None

            if c1 is n1 and c2 is n2:
                child = startingNode
            else:
                child = merge_nodes(c1, c2, parent=parent)

            if child is not None:
                parent.children.append(child)



    return current






if __name__ == "__main__":
    file1 = "bug_reports/chrome/postSkip-bug-report/postSkip-bug-report-2025-11-24-00-12-28-577512/minified_bug.html"
    file2 = "bug_reports/chrome/postSkip-bug-report/postSkip-bug-report-2025-11-24-00-12-41-303617/minified_bug.html"

    tree1, start1 = html_file_to_tree(file1)
    tree2, start2 = html_file_to_tree(file2)
    walk_tree(start1)
    print("-----")
    walk_tree(start2)
    print("=====")
    common_root = build_common_tree(start1, start2)
    print("Common Tree:")
    walk_tree_verbose(common_root)
