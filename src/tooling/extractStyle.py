import os, re, json, collections, sys

def extract_styles(text):
    # Compile regex patterns to match JS style assignments:
    # 1) element.style["prop"] = "value"
    # 2) element.style.prop = "value"
    # 3) element.style.setProperty("prop", "value")
    patterns = [
        re.compile(r'\.style\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'\.style\.([a-zA-Z_]\w*)\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'setProperty\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']')
    ]
    results = []
    # Apply each pattern and collect all (property, value) pairs
    for pat in patterns:
        results.extend(pat.findall(text))
    normalized = []
    # Normalize keys/values by stripping whitespace and quotes
    for k, v in results:
        k = k.strip().replace('"', '').replace("'", '')
        v = v.strip().replace('"', '').replace("'", '')
        if k:
            normalized.append((k, v))
    return normalized

def scan_reports(root="bug_reports"):
    # per_folder maps folder name -> Counter of (property, value) pairs
    per_folder = {}

    # totals is a global Counter over all folders
    totals = collections.Counter()

    # Iterate over immediate entries in the root directory
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue

        # Each bug report folder is expected to contain minified_bug.html
        html_path = os.path.join(entry.path, "minified_bug.html")
        if not os.path.isfile(html_path):
            continue
        try:
            # Read HTML content, ignoring encoding issues
            with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            # Skip folders we fail to read
            continue

        # Extract all style assignments from the HTML/JS
        pairs = extract_styles(text)

        # Count per-folder occurrences
        per_folder[os.path.basename(entry.path)] = collections.Counter(pairs)
        
        # Update global totals
        totals.update(pairs)
    return per_folder, totals

def main():
    # First argument: root directory of bug reports (default: "bug_reports")
    root = sys.argv[1] if len(sys.argv) > 1 else "bug_reports"

    # Second argument: output JSON path (default: style_counts.json inside root)
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "style_counts.json")

    # Scan all reports under root
    per_folder, totals = scan_reports(root)

    # Prepare a summary structure for JSON output
    summary = {
        "root": os.path.abspath(root),
        "totals_sorted": [
            {"property": k[0], "value": k[1], "count": c}
            for k, c in totals.most_common()
        ],
        "per_folder": {
            folder: [
                {"property": k[0], "value": k[1], "count": c}
                for k, c in cnt.most_common()
            ]
            for folder, cnt in per_folder.items()
        }
    }

    # Save summary JSON 
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    # Print path
    print(out_path)

if __name__ == "__main__":
    main()
