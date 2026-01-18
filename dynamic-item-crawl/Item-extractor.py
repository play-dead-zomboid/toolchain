import os
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json
import gzip
import base64
from pathlib import Path

ROOT_WORKSHOP_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600"


# -----------------------------
# Data structures
# -----------------------------

@dataclass
class RawProperty:
    key: Optional[str]
    value: Optional[str]
    original_line: str


@dataclass
class ItemDefinition:
    identity: str
    workshop_id: str
    mod_id: str
    module: str
    item_name: str
    file_path: str
    source_root: str  # "common" or "42"
    raw_properties: List[RawProperty]
    effective_properties: Dict[str, str]


@dataclass
class ParseError:
    file_path: str
    module: Optional[str]
    item_name: Optional[str]
    message: str


# -----------------------------
# Filesystem discovery
# -----------------------------

def discover_script_files(
    workshop_root: str,
    base_game_root: str
) -> List[tuple]:
    results = []

    # -----------------------------
    # Base game scripts
    # -----------------------------
    base_scripts_root = os.path.join(base_game_root, "media", "scripts")
    if os.path.isdir(base_scripts_root):
        for r, _, files in os.walk(base_scripts_root):
            for f in files:
                if f.lower().endswith(".txt"):
                    results.append(
                        (
                            "BASE",           # workshop_id
                            "BaseGame",       # mod_id
                            "base",           # source_root
                            os.path.join(r, f)
                        )
                    )

    # -----------------------------
    # Workshop mods (full recursive)
    # -----------------------------
    workshop_root = os.path.normpath(workshop_root)

    for r, _, files in os.walk(workshop_root):
        for f in files:
            if not f.lower().endswith(".txt"):
                continue

            full_path = os.path.join(r, f)
            parts = os.path.normpath(full_path).split(os.sep)

            try:
                idx = parts.index("108600")
                workshop_id = parts[idx + 1]

                mods_idx = parts.index("mods", idx + 2)
                mod_id = parts[mods_idx + 1]
            except (ValueError, IndexError):
                continue

            # Infer source root (best-effort, informational only)
            source_root = "unknown"
            for p in parts:
                pl = p.lower()
                if pl == "common":
                    source_root = "common"
                    break
                if pl.startswith("42"):
                    source_root = p
                    break

            results.append(
                (workshop_id, mod_id, source_root, full_path)
            )

    return results

# -----------------------------
# Property vocabulary discovery
# -----------------------------

def discover_property_vocabulary(files: List[tuple]) -> Dict[str, int]:
    vocab = defaultdict(int)

    for _, _, _, path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if "=" in s and not s.startswith("//"):
                        key = s.split("=", 1)[0].strip().lower()
                        if key:
                            vocab[key] += 1
        except Exception:
            continue

    return dict(vocab)


# -----------------------------
# Item parser
# -----------------------------

def parse_items(files: List[tuple]):
    items: List[ItemDefinition] = []
    errors: List[ParseError] = []

    for workshop_id, mod_id, source_root, path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as ex:
            errors.append(ParseError(path, None, None, f"File read error: {ex}"))
            continue

        current_module = None
        i = 0
        items_found = 0
        local_errors: List[ParseError] = []

        while i < len(lines):
            line = lines[i].strip()

            # MODULE
            if line.lower().startswith("module "):
                parts = line.split()
                if len(parts) >= 2:
                    current_module = parts[1]
                i += 1
                continue

            # ITEM 
            if line.lower().startswith("item "):

                j = i + 1
                while j < len(lines):
                    peek = lines[j].strip()
                    if not peek or peek.startswith("//"):
                        j += 1
                        continue
                    break

                if j >= len(lines) or lines[j].strip() != "{":
                    i += 1
                    continue

                if current_module is None:
                    i += 1
                    continue

                parts = line.split()
                if len(parts) < 2:
                    i += 1
                    continue

                item_name = parts[1]
                raw_props: List[RawProperty] = []
                effective: Dict[str, str] = {}

                # Consume '{'
                i = j + 1
                brace_depth = 1

                while i < len(lines) and brace_depth > 0:
                    text = lines[i]
                    stripped = text.strip()

                    brace_depth += stripped.count("{")
                    brace_depth -= stripped.count("}")

                    if "=" in stripped:
                        key, val = stripped.split("=", 1)
                        key = key.strip()
                        val = val.rstrip(",").strip()
                        raw_props.append(RawProperty(key, val, text.rstrip()))
                        effective[key.lower()] = val
                    else:
                        if stripped:
                            raw_props.append(RawProperty(None, None, text.rstrip()))

                    i += 1

                identity = f"{workshop_id}.{mod_id}.{current_module}.{item_name}"
                items.append(
                    ItemDefinition(
                        identity=identity,
                        workshop_id=workshop_id,
                        mod_id=mod_id,
                        module=current_module,
                        item_name=item_name,
                        file_path=path,
                        source_root=source_root,
                        raw_properties=raw_props,
                        effective_properties=effective,
                    )
                )
                items_found += 1
                continue

            i += 1

        # Only emit errors if the file actually contained items
        if items_found > 0:
            errors.extend(local_errors)

    return items, errors

# -----------------------------
# Serialization
# -----------------------------

def serialize(items, errors, vocab, out_dir="output"):
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    **asdict(item),
                    "raw_properties": [asdict(p) for p in item.raw_properties],
                }
                for item in items
            ],
            f,
            indent=2,
        )

    with open(os.path.join(out_dir, "errors.json"), "w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in errors], f, indent=2)

    with open(os.path.join(out_dir, "property_vocabulary.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2)

# -----------------------------
# Mod Indexer
# -----------------------------

def write_mod_index(root: str, out_path: str = "output/mod_index.txt"):
    mods = {}

    root = os.path.normpath(root)

    for r, _, _ in os.walk(root):
        parts = os.path.normpath(r).split(os.sep)

        try:
            idx = parts.index("108600")
            workshop_id = parts[idx + 1]

            mods_idx = parts.index("mods", idx + 2)
            mod_id = parts[mods_idx + 1]
            mod_path = os.sep.join(parts[:mods_idx + 2])
        except (ValueError, IndexError):
            continue

        # Deduplicate by (workshop_id, mod_id)
        mods[(workshop_id, mod_id)] = mod_path

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for (workshop_id, mod_id), path in sorted(mods.items()):
            f.write(f"{workshop_id} {mod_id}\n")
            f.write(f"{path}\n\n")


# -----------------------------
# Presentation
# -----------------------------

def build_display_items(items, out_dir="output"):
    display_items = []

    for item in items:
        display_items.append(
            {
                "identity": item.identity,
                "item_name": item.item_name,
                "file_path": item.file_path,
                "properties": {
                    key: value
                    for key, value in item.effective_properties.items()
                },
            }
        )

    with open(os.path.join(out_dir, "items_display.json"), "w", encoding="utf-8") as f:
        json.dump(display_items, f, indent=2)


import json
import os

# -----------------------------
# Normalization
# -----------------------------

def normalize_value(raw: str):
    """
    Normalize a single property value according to final rules:
    1. Numeric → float
    2. Semicolon-delimited → list[str]
    3. Fallback → lowercase string
    """
    if raw is None:
        return None

    raw = raw.strip()

    # Try numeric coercion
    try:
        # Reject cases like "1.0f" or "10kg"
        if raw.replace(".", "", 1).isdigit():
            return float(raw)
    except Exception:
        pass

    # Semicolon-delimited list
    if ";" in raw:
        return [
            token.strip().lower()
            for token in raw.split(";")
            if token.strip()
        ]

    # Fallback string
    return raw.lower()


def normalize_items_display(
    input_path: str = "output/items_display.json",
    output_path: str = "output/items_display_normalized.json"
):
    if not os.path.isfile(input_path):
        raise FileNotFoundError(input_path)

    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    normalized_items = []

    for item in items:
        normalized_props = {}

        for key, value in item.get("properties", {}).items():
            if value is None:
                continue

            norm_key = key.lower()
            norm_val = normalize_value(str(value))

            normalized_props[norm_key] = norm_val

        normalized_items.append(
            {
                "identity": item["identity"],
                "item_name": item["item_name"],
                "file_path": item["file_path"],
                "properties": normalized_props,
            }
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_items, f, separators=(",", ":"))

    print(f"Normalized items written to {output_path}")


# -----------------------------
# Compress and inject to page
# -----------------------------

def compress_json(path: Path) -> str:
    raw = path.read_bytes()
    compressed = gzip.compress(raw, compresslevel=9)
    return base64.b64encode(compressed).decode("ascii")


def build_play_dead(
    template_path: str = "template.html",
    output_path: str = "play-dead.html",
    items_path: str = "output/items_display_normalized.json",
    vocab_path: str = "output/property_vocabulary.json",
):
    SCRIPT_DIR = Path(__file__).resolve().parent
    OUTPUT_PATH = SCRIPT_DIR.parent / "play-dead.html"
    template = Path(template_path).read_text(encoding="utf-8")

    items_payload = compress_json(Path(items_path))
    vocab_payload = compress_json(Path(vocab_path))

    if "__ITEMS_PAYLOAD__" not in template:
        raise RuntimeError("Missing __ITEMS_PAYLOAD__ marker in template")

    if "__PROPERTY_VOCAB_PAYLOAD__" not in template:
        raise RuntimeError("Missing __PROPERTY_VOCAB_PAYLOAD__ marker in template")

    rendered = (
        template
        .replace("/*__ITEMS_PAYLOAD__*/", items_payload)
        .replace("/*__PROPERTY_VOCAB_PAYLOAD__*/", vocab_payload)
    )

    Path(OUTPUT_PATH).write_text(rendered, encoding="utf-8")

    print(f"Built {output_path}")
    print(f"Items payload size: {len(items_payload):,} chars")
    print(f"Vocab payload size: {len(vocab_payload):,} chars")



# -----------------------------
# Main
# -----------------------------

def main():
    files = discover_script_files(
        workshop_root=ROOT_WORKSHOP_PATH,
        base_game_root=r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"
    )
    print(f"Discovered script files: {len(files)}")

    vocab = discover_property_vocabulary(files)
    items, errors = parse_items(files)

    serialize(items, errors, vocab)
    build_display_items(items)
    write_mod_index(ROOT_WORKSHOP_PATH)
    normalize_items_display()
    build_play_dead()
    print("done")


if __name__ == "__main__":
    main()
