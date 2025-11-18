import os, re, json, collections, sys

def extract_styles(text):
    # Compile patterns for three kinds of style changes:
    # 1) element.style["prop"] = "value"
    # 2) element.style.prop = "value"
    # 3) element.style.setProperty("prop", "value")
    patterns = [
        re.compile(r'\.style\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'\.style\.([a-zA-Z_]\w*)\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'setProperty\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']')
    ]
    results = []
    # Run all regexes and collect all (property, value) matches
    for pat in patterns:
        results.extend(pat.findall(text))
    cleaned = []
    # Normalize property and value strings
    for k, v in results:
        k = k.strip().replace('"', '').replace("'", '')
        v = v.strip().replace('"', '').replace("'", '')
        if k:
            cleaned.append((k, v))
    return cleaned

def aggregate_counts(root="bug_reports"):
    # combo_counter counts how many folders share the same unique combination
    combo_counter = collections.Counter()
    # Walk immediate subdirectories of root (each bug report folder)
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        html_path = os.path.join(entry.path, "minified_bug.html")
        # Only consider folders that have a minified_bug.html
        if not os.path.isfile(html_path):
            continue
        try:
            with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            # Skip unreadable files/folders
            continue

        # Get all style pairs and then deduplicate them for this file
        unique_pairs = sorted(set(extract_styles(text)))
        if unique_pairs:
            # Convert to tuple of tuples so it’s hashable as a key
            key = tuple(unique_pairs)
            combo_counter[key] += 1

    # Convert the aggregated combos into a JSON-friendly structure
    combined = []
    for combo, count in combo_counter.most_common():
        entry = {"count": count}
        for i, (prop, val) in enumerate(combo, start=1):
            entry[f"property_{i}"] = prop
            entry[f"value_{i}"] = val
        combined.append(entry)

    return combined

def main():
    # Optional first arg: root directory of bug reports
    root = sys.argv[1] if len(sys.argv) > 1 else "bug_reports"
    combined = aggregate_counts(root)
    output = {
        "root": os.path.abspath(root),
        "combined_counts": combined
    }
    # Always write to this aggregate JSON file
    with open("style_counts_aggregate_firefox.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
