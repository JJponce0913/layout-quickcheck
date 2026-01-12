import re
from bs4 import BeautifulSoup

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

    for body in soup.find_all("body"):
        kids = [c for c in body.contents if getattr(c, "name", None) or str(c).strip()]
        tags = []
        for c in kids:
            if getattr(c, "name", None):
                tags.append(c.name)
            else:
                tags.append("text")

        if tags == pattern:
            return True

    return False

def should_skip(file, rules):
    
    print(f"Checking {len(rules)} skip rules...")

    for rule in rules:
        html_pat = rule.get("rule_class", {}).get("html_pattern", [])
        styles = rule.get("rule_class", {}).get("style", [])

        patternFound = check_pattern(file, html_pat)
        
        styleFound = False
        for prop, values in styles:
            vals = values if isinstance(values, list) else [values]
            for v in vals:
                if check_style(file, prop, v):
                    styleFound = True
                    break
            if styleFound:
                break

        if patternFound and styleFound:
            return True

    return False