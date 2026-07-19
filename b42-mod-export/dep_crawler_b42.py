"""
dep_crawler_b42.py

Reads the workshop IDs from modexport.md, fetches each mod's Steam
Workshop page, and reports which required dependencies are NOT already in
the mod list.  Also fetches pages for missing deps to catch transitive gaps.

Output:
  dep_cache_b42.json   — cached page results (reused on re-runs)
  dep_report_b42.json  — full structured report
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
import random

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEXPORT     = os.path.join(SCRIPT_DIR, "modexport.md")
CACHE_FILE    = os.path.join(SCRIPT_DIR, "dep_cache_b42.json")
OUTPUT_FILE   = os.path.join(SCRIPT_DIR, "dep_report_b42.json")

# ── tuning ─────────────────────────────────────────────────────────────────────
DELAY_MIN  = 15   # seconds between requests (min)
DELAY_MAX  = 15   # seconds between requests (max)


# ── parsing ────────────────────────────────────────────────────────────────────

def parse_modexport(filepath):
    print("parse_modexport")
    """Return a list of workshop ID strings found in the modexport md file.
    Workshop IDs appear as bare numeric lines (7-12 digits), not in comments."""
    ids = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if re.match(r"^\d{7,12}$", line):
                ids.append(line)
    return ids


# ── steam scraping ─────────────────────────────────────────────────────────────

def id_to_url(mod_id):
    print("id_to_url")
    return f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"


def fetch_mod_page(mod_id, cache):
    print("fetch_mod_page")
    """Fetch and parse a Steam Workshop page.  Returns a dict and updates cache."""
    if mod_id in cache:
        return cache[mod_id]

    url = id_to_url(mod_id)
    print(f"  GET  [{mod_id}]  {url}")

    try:
        resp = requests.get(url, timeout=15)
    except Exception as exc:
        print(f"  FAIL [{mod_id}]  {exc}")
        result = {"id": mod_id, "title": "FETCH_ERROR", "dependencies": [], "error": str(exc)}
        cache[mod_id] = result
        return result

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} [{mod_id}]")
        result = {"id": mod_id, "title": "HTTP_ERROR", "dependencies": [], "error": f"HTTP {resp.status_code}"}
        cache[mod_id] = result
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.select_one(".workshopItemTitle")
    title = title_el.text.strip() if title_el else "Unknown"

    deps = []
    req_container = soup.select_one("div.requiredItemsContainer#RequiredItems")
    if req_container:
        for a in req_container.find_all("a", href=True):
            m = re.search(r"id=(\d+)", a["href"])
            if not m:
                continue
            dep_id = m.group(1)
            name_el = a.find("div", class_="requiredItem")
            dep_name = name_el.text.strip() if name_el else "Unknown"
            deps.append({"id": dep_id, "name": dep_name})

    result = {"id": mod_id, "title": title, "dependencies": deps}
    cache[mod_id] = result
    dep_note = f"{len(deps)} dep(s)" if deps else "no deps"
    print(f"  OK   [{mod_id}]  {title}  ({dep_note})")
    return result


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    # Load known IDs from the modexport file
    known_ids = set(parse_modexport(MODEXPORT))
    print(f"Loaded {len(known_ids)} workshop IDs from modexport.\n")

    # Load existing cache so we don't re-fetch on re-runs
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Cache: {len(cache)} entries already stored.\n")

    # ── pass 1: fetch all mods in the list ────────────────────────────────────
    print("=== Pass 1: fetching modexport mods ===")
    for mod_id in sorted(known_ids):
        fetch_mod_page(mod_id, cache)
    save_cache(cache)

    # ── collect missing deps ───────────────────────────────────────────────────
    # missing_deps[dep_id] = {"name": str, "required_by": [{"id", "title"}, ...]}
    missing_deps = {}

    for mod_id in known_ids:
        info = cache.get(mod_id, {})
        for dep in info.get("dependencies", []):
            dep_id = dep["id"]
            if dep_id not in known_ids:
                if dep_id not in missing_deps:
                    missing_deps[dep_id] = {"name": dep["name"], "required_by": []}
                missing_deps[dep_id]["required_by"].append(
                    {"id": mod_id, "title": info.get("title", "?")}
                )

    # ── pass 2: fetch missing dep pages for transitive gaps ───────────────────
    if missing_deps:
        print(f"\n=== Pass 2: fetching {len(missing_deps)} missing dependency pages ===")
        for dep_id in sorted(missing_deps.keys()):
            info = fetch_mod_page(dep_id, cache)
            for sub_dep in info.get("dependencies", []):
                sub_id = sub_dep["id"]
                if sub_id not in known_ids and sub_id not in missing_deps:
                    missing_deps[sub_id] = {
                        "name": sub_dep["name"],
                        "required_by": [{"id": dep_id, "title": info.get("title", "?")}],
                    }
        save_cache(cache)

    # ── write report ───────────────────────────────────────────────────────────
    report = {
        "known_mod_count": len(known_ids),
        "missing_dependency_count": len(missing_deps),
        "missing_dependencies": missing_deps,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ── print summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MISSING DEPENDENCIES  ({len(missing_deps)} total)")
    print(f"{'='*60}")

    # Sort by how many mods require each dep (most-needed first)
    for dep_id, info in sorted(missing_deps.items(),
                                key=lambda x: len(x[1]["required_by"]),
                                reverse=True):
        print(f"\n  [{dep_id}]  {info['name']}")
        print(f"  {id_to_url(dep_id)}")
        for req in info["required_by"]:
            print(f"    <- [{req['id']}]  {req['title']}")

    print(f"\nReport saved to {OUTPUT_FILE}")
    print(f"Cache  saved to {CACHE_FILE}")


if __name__ == "__main__":
    print("main")
    main()
