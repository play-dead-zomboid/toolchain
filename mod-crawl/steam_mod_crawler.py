"""
steam_mod_crawler.py  —  consolidated replacement for the per-season
SteamModCrawlerV3.py forks (season 1, Family Style, Starving Games, PA RP S13).

Reads a list of workshop mods, fetches each Steam Workshop page, and records
title / description / Mod ID / tags / dependencies into a JSON file. Dependencies
found on a page are themselves crawled, looping until no new ones appear.

Output is merged into the target JSON, so re-running only adds what's missing.

Input modes:
    --input-mode ids    file of semicolon-separated workshop IDs (e.g. mods.txt)
    --input-mode urls   file of one full workshop URL per line ('//' comments ok)

Run:
    python steam_mod_crawler.py --input mods.txt --output mods.json
    python steam_mod_crawler.py --input urls.txt --input-mode urls --delay 12
"""

import argparse
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

mod_data = []
mod_outliers = []
processed_urls = set()


def append_ids_to_URL(filename):
    """Semicolon-separated workshop IDs -> full workshop URLs."""
    print("Appending IDs to URLs from file.")
    urls = []
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    for id_str in content.split(";"):
        mod_id = id_str.strip()
        if not mod_id:
            continue
        urls.append(f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}")
    print("append complete. returning URLs.")
    return urls


def extract_urls_from_file(filename):
    """One URL per line; blank lines and '//' comments are skipped."""
    print("Extracting URLS from file.")
    urls = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            urls.append(line)
    print("extraction complete. returning URLs.")
    return urls


def get_id_from_url(url):
    m = re.search(r"id=(\d+)", url)
    return m.group(1) if m else ""


def process_mod_url(url, delay):
    if url in processed_urls:
        return
    processed_urls.add(url)
    mod_id = get_id_from_url(url)
    if not mod_id:
        print(f"could not extract mod ID from url: {url}")
        mod_outliers.append({"id": "unknown", "url": url,
                             "outlier_reason": "could not extract id from url"})
        return

    # Wait BEFORE the request, so failures are rate-limited too. (The old
    # per-season copies slept after a successful fetch only, which meant an
    # error run hammered Steam at full speed.)
    time.sleep(delay)

    try:
        resp = requests.get(url, timeout=10)
    except Exception:
        print(f"adding {mod_id} to outliers because there was an exception on request")
        mod_outliers.append({"id": mod_id, "url": url,
                             "outlier_reason": "exception on request"})
        return

    if resp.status_code != 200:
        print(f"adding {mod_id} to outliers because of a bad response - {resp.status_code}")
        mod_outliers.append({"id": mod_id, "url": url,
                             "outlier_reason": f"bad response {resp.status_code}"})
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.select_one(".workshopItemTitle")
    description = soup.select_one("#highlightContent")
    tags_block = soup.select_one(".rightDetailsBlock")

    title_text = title.text.strip() if title else "Unknown Title"
    description_text = description.text.strip() if description else ""

    mod_id_value = ""
    if description:
        for line in description.text.splitlines():
            mod_match = re.search(r"Mod ID:\s*([\w\d _-]+)", line)
            if mod_match:
                mod_id_value = mod_match.group(1)

    tags = [a.text.strip() for a in tags_block.find_all("a")] if tags_block else []

    if not mod_id_value:
        mod_outliers.append({"id": mod_id, "url": url,
                             "outlier_reason": "missing mod_id_value"})
        return

    new_mod = {
        "id": mod_id,
        "url": url,
        "mod_id": mod_id_value,
        "title": title_text,
        "description": description_text,
        "tags": tags,
    }

    required_items_container = soup.select_one("div.requiredItemsContainer#RequiredItems")
    if required_items_container:
        dependencies = []
        for a in required_items_container.find_all("a", href=True):
            req_item_div = a.find("div", class_="requiredItem")
            item_name = req_item_div.text.strip() if req_item_div else ""
            dependencies.append({"mod_name": item_name, "url": a["href"]})
        new_mod["dependencies"] = dependencies

    print(f"adding {mod_id} to mod_data")
    mod_data.append(new_mod)


def processed_urls_set():
    data_urls = set(mod["url"] for mod in mod_data)
    outlier_urls = set(out["url"] for out in mod_outliers)
    return data_urls | outlier_urls


def check_and_process_dependencies(delay):
    print("entered check_and_process_dependencies")
    count = 0
    urls_processed = processed_urls_set()
    for mod in mod_data:
        for dep in mod.get("dependencies", []):
            dep_url = dep["url"]
            if dep_url not in urls_processed:
                print(f"found new dependency: {dep_url}")
                process_mod_url(dep_url, delay)
                count += 1
                urls_processed = processed_urls_set()
    if count > 0:
        print("count greater than zero this run, looping")
    else:
        print("no more dependencies found")
    return count


def merge_into_output(output_file):
    """Merge this run's results into output_file without dropping prior entries."""
    if os.path.isfile(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, dict) and "mod_data" in existing:
            existing_mods = existing["mod_data"]
            existing_outliers = existing.get("mod_outliers", [])
        else:
            existing_mods = existing
            existing_outliers = []
    else:
        existing_mods = []
        existing_outliers = []

    existing_ids = set(m["id"] for m in existing_mods)
    for mod in mod_data:
        if mod["id"] not in existing_ids:
            existing_mods.append(mod)
            existing_ids.add(mod["id"])

    existing_outlier_urls = set((o["url"], o.get("id", "")) for o in existing_outliers)
    for out in mod_outliers:
        key = (out["url"], out.get("id", ""))
        if key not in existing_outlier_urls:
            existing_outliers.append(out)
            existing_outlier_urls.add(key)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"mod_data": existing_mods, "mod_outliers": existing_outliers},
                  f, indent=2, ensure_ascii=False)

    print(f"Total mod_data entries: {len(existing_mods)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="mods.txt",
                    help="input file (default: mods.txt)")
    ap.add_argument("--input-mode", choices=("ids", "urls"), default="ids",
                    help="'ids' = semicolon-separated workshop IDs; "
                         "'urls' = one URL per line (default: ids)")
    ap.add_argument("--output", default="mods.json",
                    help="output JSON, merged into if it exists (default: mods.json)")
    ap.add_argument("--delay", type=float, default=30.0,
                    help="seconds to wait before each request (default: 30)")
    args = ap.parse_args()

    if args.input_mode == "ids":
        urls = append_ids_to_URL(args.input)
    else:
        urls = extract_urls_from_file(args.input)

    urls = sorted(set(urls), key=lambda x: int(get_id_from_url(x)))
    print(f"{len(urls)} mods to crawl, {args.delay}s between requests.")

    for url in urls:
        process_mod_url(url, args.delay)

    while check_and_process_dependencies(args.delay) > 0:
        pass

    merge_into_output(args.output)


if __name__ == "__main__":
    main()
