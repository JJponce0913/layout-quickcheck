import os, re, json, collections, sys

def extract_styles(text):
    patterns = [
        re.compile(r'\.style\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'\.style\.([a-zA-Z_]\w*)\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'setProperty\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']')
    ]
    results = []
    for pat in patterns:
        results.extend(pat.findall(text))
    out = []
    for k, v in results:
        k = k.strip().replace('"', '').replace("'", '')
        v = v.strip().replace('"', '').replace("'", '')
        if k:
            out.append((k, v))
    return out

def aggregate_counts(root="bug_reports"):
    totals = collections.Counter()
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        html_path = os.path.join(entry.path, "minified_bug.html")
        if not os.path.isfile(html_path):
            continue
        try:
            with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        totals.update(extract_styles(text))
    return totals

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "bug_reports"
    totals = aggregate_counts(root)
    combined = [{"property": k[0], "value": k[1], "count": c} for k, c in totals.most_common()]
    output = {"root": os.path.abspath(root), "combined_counts": combined}

    with open("style_counts_aggregate.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
