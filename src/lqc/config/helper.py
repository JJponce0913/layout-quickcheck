from lqc.config.config import Config, parse_config
import os
import json
import re

def set_config(filename="./config/preset-default.config.json"):
    print(f"Using config file {filename}")
    Config(parse_config(filename))

def extract_change(html_path, folder_path, json_path="bug_reports/extracted_styles.json"):
    if html_path.startswith("file://"):
        html_path = html_path[7:]

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    start = html.find("function makeStyleChanges()")
    if start == -1:
        print(f"No makeStyleChanges() in {html_path}")
        return

    brace_count = 0
    i = start
    while i < len(html):
        if html[i] == "{":
            brace_count += 1
            if brace_count == 1:
                func_start = i
        elif html[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                func_end = i
                break
        i += 1

    func_text = html[start:func_end+1]

    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}

    new_key = str(len(data))
    data[new_key] = {
        "folder_path": folder_path,
        "change": func_text
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"Appended {new_key} to {json_path}")
    return json_path

def extract_style_properties(func_text):
    pattern = r'one\.style(?:\["([^"]+)"\]|\.([a-zA-Z\-]+))\s*='
    matches = re.findall(pattern, func_text)
    properties = []
    for prop1, prop2 in matches:
        properties.append(prop1 if prop1 else prop2)
    return properties

def extract_style_weights(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    style_weights = config.get("style-weights", {})
    print(type(style_weights))
    print(style_weights)
    return style_weights


def update_style_weight(config_path, style, weight):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    config.setdefault("style-weights", {})
    config["style-weights"][style] = weight

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

#Get the latest properties
def get_latest(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        return None

    # Convert keys to int and find the max
    max_key = max(int(k) for k in data.keys())
    latest_change = data[str(max_key)].get("change", None)

    return latest_change

#set all properties to zero
def set_zero(func_text, config_path):
    props = extract_style_properties(get_latest(func_text))
    for p in props:
        print(f"Resetting {p}")
        update_style_weight(config_path, p, 0)


