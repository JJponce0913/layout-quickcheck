class Node:
    def __init__(self, tag=None, id="none", attrs=None, parent=None, base_style=None, modified_style=None, style=None):
        if attrs is None:
            attrs = {}
        if base_style is None:
            base_style = {}
        if modified_style is None:
            modified_style = {}
        if style is None:
            style = {}

        self.id = id
        self.tag =tag
        self.base_style = base_style
        self.modified_style = modified_style
        self.style = style
        self.parent = parent
        self.children = []


    def __str__(self):
        parent_id = self.parent.id if self.parent is not None else None
        return (
        f"Node(tag={self.tag}, id={self.id}, parent_id={parent_id}, "
        f"children={len(self.children)}, "
        f"base_style={self.base_style}, modified_style={self.modified_style}, style={self.style})")

    def get_parent(self):
        return self.parent

class TextNode:
    def __init__(self, text, parent=None):
        self.tag = "#text"
        self.text = text
        self.parent = parent

    def __str__(self):
        return f"TextNode(text={self.text})"

    def get_parent(self):
        return self.parent

def _merge_dicts(d1, d2):
    keys = set(d1.keys()) & set(d2.keys())
    out = {}
    for k in keys:
        v1 = d1[k]
        v2 = d2[k]

        if isinstance(v1, dict) and isinstance(v2, dict):
            merged = _merge_dicts(v1, v2)
            if merged:
                out[k] = merged
        elif v1 == v2:
            out[k] = v1
        else:
            out[k] = "diff"
    return out


def merge_nodes(a, b, parent=None):
    if a is None or b is None:
        return None
    
    a_is_text = isinstance(a, TextNode) 
    b_is_text = isinstance(b, TextNode)

    if a_is_text and b_is_text:
        text = a.text if a.text == b.text else "diff"
        return TextNode(text, parent=parent)

    if a_is_text or b_is_text:
        return Node(tag="diff", id="empty", parent=parent, base_style={}, modified_style={}, style={})

    tag = a.tag if a.tag == b.tag else "diff"
    node_id = a.id if a.id == b.id else "diff"

    base_style = _merge_dicts(getattr(a, "base_style", {}) or {}, getattr(b, "base_style", {}) or {})
    modified_style = _merge_dicts(getattr(a, "modified_style", {}) or {}, getattr(b, "modified_style", {}) or {})
    style = _merge_dicts(getattr(a, "style", {}) or {}, getattr(b, "style", {}) or {})

    return Node(
        tag=tag,
        id=node_id,
        parent=parent,
        base_style=base_style,
        modified_style=modified_style,
        style=style,
    )

def run_subject_to_node_tree(run_subject):
    base_map = getattr(run_subject.base_styles, "map", {}) or {}
    mod_map = getattr(run_subject.modified_styles, "map", {}) or {}

    def merged_style_for(node_id):
        b = base_map.get(node_id, {}) or {}
        m = mod_map.get(node_id, {}) or {}
        combined = dict(b)
        combined.update(m)
        return b, m, combined

    startnodeID = None

    def element_dict_to_node(el, parent=None):
        nonlocal startnodeID

        if el is None:
            return None

        if el.get("tag") == "<text>":
            return TextNode(el.get("value", ""), parent=parent)

        attrs = {k: v for k, v in el.items() if k != "children"}
        tag = attrs.pop("tag", "")
        node_id = attrs.get("id", "none")

        if str(node_id) == "lqc_dev_controls":
            return None

        b, m, combined = {}, {}, {}
        if node_id != "none":
            b, m, combined = merged_style_for(node_id)

        n = Node(tag=tag, id=node_id, attrs=attrs, parent=parent, base_style=b, modified_style=m, style=combined)

        if startnodeID is None and m:
            startnodeID = n

        for child in el.get("children", []):
            child_node = element_dict_to_node(child, parent=n)
            if child_node is not None:
                n.children.append(child_node)

        return n

    tree = run_subject.html_tree.tree

    if isinstance(tree, list):
        root = Node(tag="body", id="Root", attrs={}, parent=None)
        for child in tree:
            cn = element_dict_to_node(child, parent=root)
            if cn is not None:
                root.children.append(cn)
        return root, startnodeID

    raise Exception("Incorrect tree format in run_subject")

def walk_tree(n, depth=0):
    indent = "  " * depth

    if isinstance(n, TextNode) or n.tag == "#text":
        print(indent + "TextNode: " + repr(n.attrs.get("text", "")))
    else:
        label = n.tag if n.tag else ""
        if n.id != "none":
            label += f"#{n.id}"
        print(indent + label)

    for child in n.children:
        walk_tree(child, depth + 1)

def walk_tree_verbose(n, depth=0):
    indent = "  " * depth
    parent_id = n.parent.id if n.parent is not None else None

    print(f"{indent}Node:")
    print(f"{indent}  tag: {n.tag}")
    if isinstance(n, TextNode) or n.tag == "#text":
        print(f"{indent}  text: {n.text}")
        print(f"{indent}  parent: {n.parent.id}")
        return
    print(f"{indent}  id: {n.id}")
    print(f"{indent}  parent_id: {parent_id}")
    print(f"{indent}  base_style: {n.base_style}")
    print(f"{indent}  modified_style: {n.modified_style}")
    print(f"{indent}  style: {n.style}")
    print(f"{indent}  children_count: {len(n.children)}")

    for child in n.children:
        walk_tree_verbose(child, depth + 1)

def build_down(a, b, parent=None):
    merged = merge_nodes(a, b, parent=parent)
    if merged is None:
        return None

    if isinstance(merged, TextNode) or getattr(merged, "tag", None) == "#text":
        return merged

    if getattr(merged, "tag", None) == "empty":
        return merged

    a_children = getattr(a, "children", []) if a is not None else []
    b_children = getattr(b, "children", []) if b is not None else []
    n = max(len(a_children), len(b_children))

    for i in range(n):
        ca = a_children[i] if i < len(a_children) else None
        cb = b_children[i] if i < len(b_children) else None
        child = build_down(ca, cb, parent=merged)
        if child is not None:
            merged.children.append(child)

    return merged

def _sibling_index(node):
    if node is None or node.parent is None:
        return None
    sibs = node.parent.children
    for i, s in enumerate(sibs):
        if s is node:
            return i
    return None

def build_left(a, b, merged_parent, a_index=None, b_index=None):
    if a is None or b is None or a.parent is None or b.parent is None:
        return []

    s1 = a.parent.children
    s2 = b.parent.children

    i1 = _sibling_index(a) if a_index is None else a_index
    i2 = _sibling_index(b) if b_index is None else b_index
    if i1 is None or i2 is None:
        return []

    left_pairs = []
    while i1 - 1 >= 0 and i2 - 1 >= 0:
        i1 -= 1
        i2 -= 1
        left_pairs.append((s1[i1], s2[i2]))

    left_pairs.reverse()
    out = []
    for x, y in left_pairs:
        out.append(build_down(x, y, parent=merged_parent))
    return out

def build_right(a, b, merged_parent, a_index=None, b_index=None):
    if a is None or b is None or a.parent is None or b.parent is None:
        return []

    s1 = a.parent.children
    s2 = b.parent.children

    i1 = _sibling_index(a) if a_index is None else a_index
    i2 = _sibling_index(b) if b_index is None else b_index
    if i1 is None or i2 is None:
        return []

    out = []
    i1 += 1
    i2 += 1
    while i1 < len(s1) and i2 < len(s2):
        out.append(build_down(s1[i1], s2[i2], parent=merged_parent))
        i1 += 1
        i2 += 1
    return out

def build_up(a, b):
    merged_subtree = build_down(a, b, parent=None)
    if merged_subtree is None:
        return None

    cur_a = a
    cur_b = b
    cur_merged = merged_subtree

    while cur_a is not None and cur_b is not None and cur_a.parent is not None and cur_b.parent is not None:
        pa = cur_a.parent
        pb = cur_b.parent

        i1 = _sibling_index(cur_a)
        i2 = _sibling_index(cur_b)
        if i1 is None or i2 is None:
            break

        merged_parent = merge_nodes(pa, pb, parent=None)
        cur_merged.parent = merged_parent

        left = build_left(cur_a, cur_b, merged_parent, a_index=i1, b_index=i2)
        right = build_right(cur_a, cur_b, merged_parent, a_index=i1, b_index=i2)

        merged_parent.children = left + [cur_merged] + right

        cur_merged = merged_parent
        cur_a = pa
        cur_b = pb

    return cur_merged

def merge_trees(a, b):
    start_node = build_down(a, b, parent=None)
    if start_node is None:
        return None

    if isinstance(start_node, Node):
        start_node.id = "start"

    cur_a = a
    cur_b = b
    cur_merged = start_node

    while cur_a is not None and cur_b is not None and cur_a.parent is not None and cur_b.parent is not None:
        pa = cur_a.parent
        pb = cur_b.parent

        i1 = _sibling_index(cur_a)
        i2 = _sibling_index(cur_b)
        if i1 is None or i2 is None:
            break

        merged_parent = merge_nodes(pa, pb, parent=None)
        if merged_parent is None:
            break

        cur_merged.parent = merged_parent

        left = build_left(cur_a, cur_b, merged_parent, a_index=i1, b_index=i2)
        right = build_right(cur_a, cur_b, merged_parent, a_index=i1, b_index=i2)

        merged_parent.children = left + [cur_merged] + right

        cur_merged = merged_parent
        cur_a = pa
        cur_b = pb

    if isinstance(cur_merged, Node):
        cur_merged.id = "root"

    return cur_merged,start_node



