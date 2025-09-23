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
    normalized = []
    for k, v in results:
        k = k.strip().replace('"', '').replace("'", '')
        v = v.strip().replace('"', '').replace("'", '')
        if k:
            normalized.append((k, v))
    return normalized

def scan_reports(root="bug_reports"):
    per_folder = {}
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
        pairs = extract_styles(text)
        per_folder[os.path.basename(entry.path)] = collections.Counter(pairs)
        totals.update(pairs)
    return per_folder, totals

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "bug_reports"
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "style_counts.json")
    per_folder, totals = scan_reports(root)
    summary = {
        "root": os.path.abspath(root),
        "totals_sorted": [{"property": k[0], "value": k[1], "count": c} for k, c in totals.most_common()],
        "per_folder": {
            folder: [{"property": k[0], "value": k[1], "count": c} for k, c in cnt.most_common()]
            for folder, cnt in per_folder.items()
        }
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(out_path)

if __name__ == "__main__":
    main()
