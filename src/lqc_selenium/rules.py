import json
import os

class Rule:
    def __init__(self, name, style, html_pattern):
        self.name = name
        self.style = style
        self.html_pattern = html_pattern

    def to_dict(self):
        return {
            "name": self.name,
            "rule_class": {
                "style": [list(t) for t in self.style],
                "html_pattern": self.html_pattern
            }
        }

    @staticmethod
    def _canonical_rule_class(rule_class):
        style = rule_class.get("style", [])
        html_pattern = rule_class.get("html_pattern", [])
        style_t = tuple(sorted(tuple(p) for p in style))
        html_t = tuple(html_pattern)
        return (style_t, html_t)

    def add_to_json(self, json_path):
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        if "rules" not in data:
            data["rules"] = []

        new_rc = self._canonical_rule_class(self.to_dict()["rule_class"])
        for item in data["rules"]:
            if self._canonical_rule_class(item.get("rule_class", {})) == new_rc:
                return  # Skip adding duplicates

        data["rules"].append(self.to_dict())
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def from_json(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = []
        for item in data.get("rules", []):
            name = item.get("name", "")
            style = [tuple(s) for s in item["rule_class"].get("style", [])]
            html_pattern = item["rule_class"].get("html_pattern", [])
            rules.append(Rule(name, style, html_pattern))
        return rules


# Example usage:
json_path = "rules.json"

# Add a rule
r = Rule("DispNone", [("display", "inline")], ["text", "div"])
r.add_to_json(json_path)

# Load back all rules
rules_list = Rule.from_json(json_path)
for rule in rules_list:
    print(rule.name, rule.style, rule.html_pattern)
