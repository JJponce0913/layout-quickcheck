from copy import deepcopy

from lqc.model.element_tree import ElementTree
from lqc.model.style_map import StyleMap

class RunSubject:
    html_tree: ElementTree
    # Format: html_tree = {
    #     tag: 'div',
    #     id: '12981283',
    #     children: [html_tree, ...]
    # }

    base_styles: StyleMap
    # Format: base_styles = [{
    #     '1293918237': {'background-color': 'blue', ...}
    # }, ...]

    modified_styles: StyleMap
    # Format: modified_styles = [{
    #     '1293918237': {'background-color': 'blue', ...}
    # }, ...]

    def __init__(self, html_tree: ElementTree, base_styles: StyleMap, modified_styles: StyleMap):
        self.html_tree = html_tree
        self.base_styles = base_styles
        self.modified_styles = modified_styles
    def __str__(self):
        return (
            "RunSubject(\n"
            f"  Elements: {len(self.getElementIds())},\n"
            f"  Base Styles: {len(self.base_styles.all_style_names())},\n"
            f"  Modified Styles: {len(self.modified_styles.all_style_names())},\n"
            f"  Styles Signature: {self.styles_signature()}\n"
            ")"
        )                             
    def deepcopy(self):
        return RunSubject(
            deepcopy(self.html_tree),
            deepcopy(self.base_styles),
            deepcopy(self.modified_styles)
        )
    
    def _find_node(self, nodes, target_id):
        for node in nodes:
            if node.get("id") == target_id:
                return node
            res = self._find_node(node.get("children", []), target_id)
            if res is not None:
                return res
        return None

    def _collect_ids(self, node):
        ids = set()
        if isinstance(node, dict):
            nid = node.get("id")
            if nid is not None:
                ids.add(nid)
            for c in node.get("children", []):
                ids |= self._collect_ids(c)
        elif isinstance(node, list):
            for c in node:
                ids |= self._collect_ids(c)
        return ids

    def removeElementById(self, id):
        subtree = self._find_node(self.html_tree.tree, id)
        ids_to_remove = {id} if subtree is None else self._collect_ids(subtree)
        for rid in ids_to_remove:
            if rid in self.base_styles.map:
                del self.base_styles.map[rid]
            if rid in self.modified_styles.map:
                del self.modified_styles.map[rid]
        self.html_tree.removeElementById(id)

    
    def getElementIds(self):
        return self.html_tree.getElementIds() | self.base_styles.getElementIds() | self.modified_styles.getElementIds()
    
    def renameId(self, old_id, new_id):
        self.html_tree.renameId(old_id, new_id)
        self.base_styles.renameId(old_id, new_id)
        self.modified_styles.renameId(old_id, new_id)
    
    def all_style_names(self):
        return self.base_styles.all_style_names().union(self.modified_styles.all_style_names())
    
    def _simplify_style_signature(self, style_name):
        """Replace pieces of the style name to consolidate similar style signatures"""
        style_name = style_name.replace('block-start', '[block]')
        style_name = style_name.replace('block-end', '[block]')
        style_name = style_name.replace('inline-start', '[inline]')
        style_name = style_name.replace('inline-end', '[inline]')
        style_name = style_name.replace('block-size', '[height]')
        style_name = style_name.replace('inline-size', '[width]')
        style_name = style_name.replace('left', '[inline]')
        style_name = style_name.replace('right', '[inline]')
        style_name = style_name.replace('top', '[block]')
        style_name = style_name.replace('bottom', '[block]')
        return style_name


    def styles_signature(self):
        """ Return 'display' style values and modified styles """
        styles = set()
        display_styles = [x for x in self.base_styles.all_style_names() if ":" in x]
        styles = styles.union(display_styles)
        modified_styles = self.modified_styles.all_style_names()
        styles = styles.union(modified_styles)

        # Simplify the style names in the signature
        styles = set([self._simplify_style_signature(x) for x in styles])

        # Sort the styles
        styles = list(styles)
        styles.sort()
        styles = ",".join(styles)

        return styles
