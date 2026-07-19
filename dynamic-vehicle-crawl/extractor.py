import os
import re
import json

# Directories to scan – edit these for your setup
SEARCH_ROOTS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid\media\scripts",
    r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600",
]

OUTPUT_JSON = "vehicle_summary.json"


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    return text


def extract_blocks(text: str, keyword: str):
    """Top-level `keyword Name { ... }` blocks."""
    results = []
    pattern = re.compile(r"\b" + re.escape(keyword) + r"\s+([A-Za-z0-9_\.]+)\s*\{", re.MULTILINE)
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            break
        name = m.group(1)
        start_brace = text.find("{", m.end() - 1)
        if start_brace == -1:
            break
        depth = 1
        i = start_brace + 1
        while i < len(text) and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = text[start_brace + 1 : i - 1]
        results.append((name, body))
        pos = i
    return results


def extract_vehicle_and_template_blocks(mod_body: str):
    vehicles = []
    template_vehicles = []

    # vehicle Name { ... } (but not "template vehicle")
    pat_v = re.compile(r"\bvehicle\s+([A-Za-z0-9_\.]+)\s*\{", re.MULTILINE)
    pos = 0
    while True:
        m = pat_v.search(mod_body, pos)
        if not m:
            break
        # skip "template vehicle"
        line_start = mod_body.rfind("\n", 0, m.start())
        if line_start == -1:
            line_start = 0
        header_segment = mod_body[line_start:m.start()]
        if "template" in header_segment:
            pos = m.end()
            continue
        name = m.group(1)
        start_brace = mod_body.find("{", m.end() - 1)
        depth = 1
        i = start_brace + 1
        while i < len(mod_body) and depth > 0:
            c = mod_body[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = mod_body[start_brace + 1 : i - 1]
        vehicles.append((name, body))
        pos = i

    # template vehicle Name { ... }
    pat_tv = re.compile(r"\btemplate\s+vehicle\s+([A-Za-z0-9_\.]+)\s*\{", re.MULTILINE)
    pos = 0
    while True:
        m = pat_tv.search(mod_body, pos)
        if not m:
            break
        name = m.group(1)
        start_brace = mod_body.find("{", m.end() - 1)
        depth = 1
        i = start_brace + 1
        while i < len(mod_body) and depth > 0:
            c = mod_body[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = mod_body[start_brace + 1 : i - 1]
        template_vehicles.append((name, body))
        pos = i

    return vehicles, template_vehicles


def extract_items_from_module(mod_body: str):
    items = {}
    pat = re.compile(r"\bitem\s+([A-Za-z0-9_\.]+)\s*\{", re.MULTILINE)
    pos = 0
    while True:
        m = pat.search(mod_body, pos)
        if not m:
            break
        name = m.group(1)
        start_brace = mod_body.find("{", m.end() - 1)
        depth = 1
        i = start_brace + 1
        while i < len(mod_body) and depth > 0:
            c = mod_body[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = mod_body[start_brace + 1 : i - 1]
        items[name] = body
        pos = i
    return items


def parse_item_properties(body: str):
    props = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = re.match(r"([A-Za-z0-9_]+)\s*=\s*(.+?),\s*$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        props[key] = val
    return props


def extract_vehicle_basic_info(body: str):
    info = {}
    m = re.search(r"\bengineForce\s*=\s*([0-9]+)", body)
    if m:
        ef = int(m.group(1))
        info["engineForce"] = ef
        info["horsepower"] = ef // 10
    m = re.search(r"\bseats\s*=\s*([0-9]+)", body)
    if m:
        info["seats"] = int(m.group(1))
    return info


def find_templates_in_body(body: str):
    names = re.findall(r"\btemplate\s*=\s*([A-Za-z0-9_\.]+)\s*,", body)
    # unique, preserve order
    return list(dict.fromkeys(names))


def collect_template_bodies(start_body: str, template_blocks: dict):
    visited = set()
    bodies = [start_body]

    def add(body: str):
        for name in find_templates_in_body(body):
            if name in template_blocks and name not in visited:
                visited.add(name)
                t_body = template_blocks[name]
                bodies.append(t_body)
                add(t_body)

    add(start_body)
    return bodies


def extract_parts_with_containers(text: str):
    parts = []
    pat = re.compile(r"\bpart\s+([A-Za-z0-9_*\.]+)\s*\{", re.MULTILINE)
    pos = 0
    while True:
        m = pat.search(text, pos)
        if not m:
            break
        name = m.group(1)
        start_brace = text.find("{", m.end() - 1)
        depth = 1
        i = start_brace + 1
        while i < len(text) and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = text[start_brace + 1 : i - 1]
        if "container" in body:
            parts.append((name, body))
        pos = i
    return parts


def extract_itemType(part_body: str):
    m = re.search(r"\bitemType\s*=\s*([^,]+),", part_body)
    if not m:
        return None
    return m.group(1).strip()


def extract_container_body(part_body: str):
    m = re.search(r"container\s*\{([^}]*)\}", part_body, flags=re.S)
    if not m:
        return ""
    return m.group(1)


def extract_capacity_from_container(container_body: str):
    m = re.search(r"\bcapacity\s*=\s*([0-9]+)", container_body)
    if not m:
        return None
    return int(m.group(1))


def resolve_item_for_itemType(item_type: str, items_dict: dict):
    if not item_type:
        return None
    if item_type.lower() == "nil":
        return None

    s = item_type.strip()
    if "." in s:
        _, name = s.split(".", 1)
    else:
        name = s

    if name in items_dict:
        return name

    candidates = [n for n in items_dict if n.startswith(name)]
    if not candidates:
        return None
    # pick the most direct-looking match
    candidates.sort(key=lambda n: (len(n) != len(name), len(n)))
    return candidates[0]


def get_part_capacity(part_name: str, part_body: str, items_dict: dict):
    container_body = extract_container_body(part_body)
    cap = extract_capacity_from_container(container_body)

    item_type = extract_itemType(part_body)
    item_name = None
    item_max = None

    if item_type:
        item_name = resolve_item_for_itemType(item_type, items_dict)
        if item_name:
            props = parse_item_properties(items_dict[item_name])
            if "MaxCapacity" in props:
                try:
                    item_max = int(float(props["MaxCapacity"]))
                except ValueError:
                    pass

    if cap is None:
        cap = item_max

    return cap, item_type, item_name


def is_gastank_part(part_name: str, part_body: str):
    if re.search(r"\bGasTank\b", part_name, flags=re.I):
        return True
    if re.search(r"\barea\s*=\s*GasTank\b", part_body, flags=re.I):
        return True
    return False


def gather_container_parts_for_vehicle(vbody: str, template_blocks: dict, items_dict: dict):
    bodies = collect_template_bodies(vbody, template_blocks)
    parts_info = []

    for body in bodies:
        for part_name, part_body in extract_parts_with_containers(body):
            if is_gastank_part(part_name, part_body):
                continue
            cap, item_type, item_name = get_part_capacity(part_name, part_body, items_dict)
            if cap is None:
                continue
            parts_info.append(
                {
                    "partName": part_name,
                    "itemType": item_type,
                    "item": item_name,
                    "capacity": cap,
                }
            )

    return parts_info


def scan_scripts(search_roots):
    vehicle_blocks = {}
    template_blocks = {}
    item_blocks = {}

    for root in search_roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                if not fn.lower().endswith(".txt"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
                except OSError:
                    continue
                text = strip_comments(raw)
                modules = extract_blocks(text, "module")
                for module_name, mod_body in modules:
                    vlist, tlist = extract_vehicle_and_template_blocks(mod_body)
                    for vname, vbody in vlist:
                        key = f"{module_name}.{vname}"
                        vehicle_blocks[key] = {
                            "name": vname,
                            "module": module_name,
                            "body": vbody,
                            "file": path,
                        }
                    for tname, tbody in tlist:
                        template_blocks[tname] = tbody
                    items_map = extract_items_from_module(mod_body)
                    for iname, ibody in items_map.items():
                        item_blocks[iname] = ibody

    return vehicle_blocks, template_blocks, item_blocks


def build_vehicle_summaries(vehicle_blocks, template_blocks, item_blocks):
    result = {}
    for key, meta in vehicle_blocks.items():
        body = meta["body"]
        info = extract_vehicle_basic_info(body)
        containers = gather_container_parts_for_vehicle(body, template_blocks, item_blocks)
        total_storage = sum(c["capacity"] for c in containers if c.get("capacity") is not None)

        result[key] = {
            "module": meta["module"],
            "vehicleName": meta["name"],
            "file": meta["file"],
            "engineForce": info.get("engineForce"),
            "horsepower": info.get("horsepower"),
            "seats": info.get("seats"),
            "containers": containers,
            "totalStorage": total_storage,
        }
    return result


def main():
    vehicle_blocks, template_blocks, item_blocks = scan_scripts(SEARCH_ROOTS)
    summaries = build_vehicle_summaries(vehicle_blocks, template_blocks, item_blocks)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
    print(f"Wrote {len(summaries)} vehicles to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
