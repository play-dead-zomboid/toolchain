import os
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from collections import defaultdict
from pathlib import Path
import gzip
import base64


# ============================================================
# CONFIG
# ============================================================

ROOT_WORKSHOP_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600"
BASE_GAME_ROOT = r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"
OUTPUT_DIR = "output"


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RawLine:
    text: str


@dataclass
class RecipeSlot:
    count: float
    items: List[str]
    tags: List[str]
    flags: List[str]
    mapper: Optional[str]
    mode: Optional[str]
    raw: str


@dataclass
class ItemMapper:
    name: str
    mappings: Dict[str, str]
    raw_lines: List[str]


@dataclass
class RecipeDefinition:
    identity: str
    workshop_id: str
    mod_id: str
    module: str
    recipe_name: str
    file_path: str
    source_root: str
    raw_lines: List[RawLine]
    effective_properties: Dict[str, Any]
    inputs: List[RecipeSlot]
    outputs: List[RecipeSlot]
    item_mappers: List[ItemMapper]


@dataclass
class RecipeParseError:
    file_path: str
    module: Optional[str]
    recipe_name: Optional[str]
    message: str


# ============================================================
# DISCOVERY
# ============================================================

def discover_script_files(workshop_root: str, base_game_root: str) -> List[tuple]:
    results = []

    base_scripts_root = os.path.join(base_game_root, "media", "scripts")
    if os.path.isdir(base_scripts_root):
        for r, _, files in os.walk(base_scripts_root):
            for f in files:
                if f.lower().endswith(".txt"):
                    results.append(("BASE", "BaseGame", "base", os.path.join(r, f)))

    workshop_root = os.path.normpath(workshop_root)
    for r, _, files in os.walk(workshop_root):
        for f in files:
            if not f.lower().endswith(".txt"):
                continue

            full = os.path.join(r, f)
            parts = os.path.normpath(full).split(os.sep)

            try:
                idx = parts.index("108600")
                workshop_id = parts[idx + 1]
                mods_idx = parts.index("mods", idx + 2)
                mod_id = parts[mods_idx + 1]
            except (ValueError, IndexError):
                continue

            source_root = "unknown"
            for p in parts:
                if p.lower().startswith("42"):
                    source_root = p
                    break

            results.append((workshop_id, mod_id, source_root, full))

    return results


# ============================================================
# PARSING HELPERS
# ============================================================

def _split_list(value: str) -> List[str]:
    return [v.strip().lower() for v in value.split(";") if v.strip()]


def _parse_slot(line: str) -> RecipeSlot:
    original = line.rstrip().rstrip(",")

    count_match = re.search(r"item\s+([\d.]+)", line, re.IGNORECASE)
    count = float(count_match.group(1)) if count_match else 1.0

    items, tags, flags = [], [], []
    mapper = None
    mode = None

    bracket_items = re.search(r"\[([^\]]+)\]", line)
    if bracket_items:
        items = _split_list(bracket_items.group(1))
    else:
        direct_item = re.search(r"item\s+[\d.]+\s+([A-Za-z0-9_.:]+)", line)
        if direct_item:
            items = [direct_item.group(1).lower()]

    tag_match = re.search(r"tags\[(.*?)\]", line, re.IGNORECASE)
    if tag_match:
        tags = _split_list(tag_match.group(1))

    flag_match = re.search(r"flags\[(.*?)\]", line, re.IGNORECASE)
    if flag_match:
        flags = _split_list(flag_match.group(1))

    mapper_match = re.search(
        r"mappers?\[([^\]]+)\]|mapper:([A-Za-z0-9_]+)",
        line,
        re.IGNORECASE,
    )
    if mapper_match:
        mapper = (mapper_match.group(1) or mapper_match.group(2)).lower()

    mode_match = re.search(r"mode:([A-Za-z]+)", line, re.IGNORECASE)
    if mode_match:
        mode = mode_match.group(1).lower()

    return RecipeSlot(count, items, tags, flags, mapper, mode, original)


# ============================================================
# RECIPE PARSER
# ============================================================

def parse_recipes(files: List[tuple]):
    recipes, errors = [], []

    for workshop_id, mod_id, source_root, path in files:
        if workshop_id != "BASE" and not source_root.lower().startswith("42"):
            continue

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as ex:
            errors.append(RecipeParseError(path, None, None, str(ex)))
            continue

        current_module = None
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.lower().startswith("module "):
                current_module = line.split()[1]
                i += 1
                continue

            if line.lower().startswith("craftrecipe "):
                recipe_name = line.split()[1]

                if i + 1 >= len(lines) or lines[i + 1].strip() != "{":
                    errors.append(RecipeParseError(path, current_module, recipe_name, "Missing opening brace"))
                    i += 1
                    continue

                raw_lines, effective, inputs, outputs, mappers = [], {}, [], [], []
                brace_depth = 1
                i += 2

                while i < len(lines) and brace_depth > 0:
                    raw = lines[i].rstrip()
                    stripped = raw.strip()
                    raw_lines.append(RawLine(raw))

                    brace_depth += stripped.count("{")
                    brace_depth -= stripped.count("}")

                    if "=" in stripped and brace_depth == 1:
                        k, v = stripped.split("=", 1)
                        effective[k.strip().lower()] = v.rstrip(",").strip().lower()

                    elif stripped.lower() == "inputs":
                        i += 2
                        while lines[i].strip() != "}":
                            if lines[i].strip().lower().startswith("item"):
                                inputs.append(_parse_slot(lines[i]))
                            i += 1

                    elif stripped.lower() == "outputs":
                        i += 2
                        while lines[i].strip() != "}":
                            if lines[i].strip().lower().startswith("item"):
                                outputs.append(_parse_slot(lines[i]))
                            i += 1

                    elif stripped.lower().startswith("itemmapper "):
                        name = stripped.split()[1].lower()
                        mappings, raw_map = {}, []
                        i += 2
                        while lines[i].strip() != "}":
                            raw_map.append(lines[i].rstrip())
                            if "=" in lines[i]:
                                k, v = lines[i].split("=", 1)
                                mappings[k.strip().lower()] = v.rstrip(",").strip().lower()
                            i += 1
                        mappers.append(ItemMapper(name, mappings, raw_map))

                    i += 1

                identity = f"{workshop_id}.{mod_id}.{current_module}.{recipe_name}"
                recipes.append(
                    RecipeDefinition(
                        identity, workshop_id, mod_id, current_module,
                        recipe_name, path, source_root,
                        raw_lines, effective, inputs, outputs, mappers
                    )
                )
                continue

            i += 1

    return recipes, errors


# ============================================================
# DISPLAY + NORMALIZATION
# ============================================================

def normalize_value(val: Any):
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        if val.replace(".", "", 1).isdigit():
            return float(val)
        return val.lower()
    if isinstance(val, list):
        return [normalize_value(v) for v in val]
    return val


def build_display(recipes):
    return [
        {
            "identity": r.identity,
            "recipe_name": r.recipe_name,
            "module": r.module,
            "file_path": r.file_path,
            "inputs": [asdict(s) for s in r.inputs],
            "outputs": [asdict(s) for s in r.outputs],
        }
        for r in recipes
    ]


def build_normalized(recipes):
    return [
        {
            "identity": r.identity,
            "recipe_name": r.recipe_name.lower(),
            "module": r.module.lower(),
            "properties": {
                k: normalize_value(v)
                for k, v in r.effective_properties.items()
            },
            "inputs": [
                {
                    "count": s.count,
                    "items": s.items,
                    "tags": s.tags,
                    "flags": s.flags,
                    "mapper": s.mapper,
                    "mode": s.mode,
                }
                for s in r.inputs
            ],
            "outputs": [
                {
                    "count": s.count,
                    "items": s.items,
                    "tags": s.tags,
                    "flags": s.flags,
                    "mapper": s.mapper,
                    "mode": s.mode,
                }
                for s in r.outputs
            ],
            "item_mappers": [
                {"name": m.name, "mappings": m.mappings}
                for m in r.item_mappers
            ],
        }
        for r in recipes
    ]


# ============================================================
# VOCAB
# ============================================================

def build_vocab(recipes):
    vocab = defaultdict(lambda: defaultdict(int))

    for r in recipes:
        for k in r.effective_properties:
            vocab["properties"][k] += 1

        for s in r.inputs + r.outputs:
            for i in s.items:
                vocab["items"][i] += 1
            for t in s.tags:
                vocab["tags"][t] += 1
            for f in s.flags:
                vocab["flags"][f] += 1
            if s.mapper:
                vocab["mappers"][s.mapper] += 1

        for m in r.item_mappers:
            vocab["item_mappers"][m.name] += 1

    return {k: dict(v) for k, v in vocab.items()}

# ============================================================
# BUILD
# ============================================================
def build_recipe_search(
    template_path: str = "template.html",
    output_path: str = "recipe-search.html",
    recipes_path: str = "output/recipes_normalized.json",
    vocab_path: str = "output/recipe_vocab.json",
):
    SCRIPT_DIR = Path(__file__).resolve().parent
    OUTPUT_PATH = SCRIPT_DIR.parent / output_path

    template = Path(template_path).read_text(encoding="utf-8")

    recipes_payload = compress_json(Path(recipes_path))
    vocab_payload = compress_json(Path(vocab_path))

    if "__RECIPES_PAYLOAD__" not in template:
        raise RuntimeError("Missing __RECIPES_PAYLOAD__ marker in template")

    if "__RECIPE_VOCAB_PAYLOAD__" not in template:
        raise RuntimeError("Missing __RECIPE_VOCAB_PAYLOAD__ marker in template")

    rendered = (
        template
        .replace("/*__RECIPES_PAYLOAD__*/", recipes_payload)
        .replace("/*__RECIPE_VOCAB_PAYLOAD__*/", vocab_payload)
    )

    Path(OUTPUT_PATH).write_text(rendered, encoding="utf-8")

    print(f"Built {output_path}")
    print(f"Recipes payload size: {len(recipes_payload):,} chars")
    print(f"Recipe vocab payload size: {len(vocab_payload):,} chars")

def compress_json(path: Path) -> str:
    raw = path.read_bytes()
    compressed = gzip.compress(raw, compresslevel=9)
    return base64.b64encode(compressed).decode("ascii")

# ============================================================
# MAIN
# ============================================================

def main():
    files = discover_script_files(ROOT_WORKSHOP_PATH, BASE_GAME_ROOT)
    recipes, errors = parse_recipes(files)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "recipes.json"), "w") as f:
        json.dump([asdict(r) for r in recipes], f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "recipes_display.json"), "w") as f:
        json.dump(build_display(recipes), f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "recipes_normalized.json"), "w") as f:
        json.dump(build_normalized(recipes), f, separators=(",", ":"))

    with open(os.path.join(OUTPUT_DIR, "recipe_vocab.json"), "w") as f:
        json.dump(build_vocab(recipes), f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "recipe_errors.json"), "w") as f:
        json.dump([asdict(e) for e in errors], f, indent=2)
    build_recipe_search()
    print(f"Recipes: {len(recipes)} | Errors: {len(errors)}")


if __name__ == "__main__":
    main()
