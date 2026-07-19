#!/usr/bin/env python3
"""
mod_exporter.py
Reads installed PZ workshop mods from the Steam workshop content directory and
writes modexport.md for use with the server string builder app.

Data sources (all local, no network required):
  - Workshop ID    : folder name under WORKSHOP_BASE
  - Mod ID(s)      : id= field in each mod's mod.info
  - Name/summary   : name= and description= from mod.info
  - URL            : constructed from workshop ID
  - Map folders    : subdirectory names under any */media/maps/ path
"""

import re
from pathlib import Path

WORKSHOP_BASE = Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600")
OUTPUT_FILE = Path(__file__).parent / "modexport.md"

_COLOR_TAG = re.compile(r'<[^>]+>')


def clean_text(text: str) -> str:
    """Strip PZ color/formatting tags and excess whitespace."""
    return _COLOR_TAG.sub('', text).strip()


def read_mod_info(path: Path) -> dict:
    """Parse a mod.info file into a lowercase-keyed dict."""
    data = {}
    try:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if '=' in line:
                key, _, val = line.partition('=')
                data[key.strip().lower()] = val.strip().strip("'\"")
    except OSError:
        pass
    return data


def best_mod_info(mod_subdir: Path) -> dict:
    """
    Return parsed mod.info for a mod subfolder, preferring common/ over
    version-numbered subfolders (42/, 42.15/, etc.).
    """
    common = mod_subdir / 'common' / 'mod.info'
    if common.exists():
        return read_mod_info(common)
    # Fall back to any mod.info found, sorted for determinism
    for info_path in sorted(mod_subdir.rglob('mod.info')):
        data = read_mod_info(info_path)
        if data:
            return data
    return {}


def find_map_folders(workshop_dir: Path) -> list:
    """
    Return map folder names from any */media/maps/ subtree.
    Deduplicates in case multiple version dirs exist.
    """
    seen = set()
    result = []
    for maps_dir in sorted(workshop_dir.rglob('maps')):
        if maps_dir.is_dir() and maps_dir.parent.name == 'media':
            for sub in sorted(maps_dir.iterdir()):
                if sub.is_dir() and sub.name not in seen:
                    seen.add(sub.name)
                    result.append(sub.name)
    return result


def process_workshop(workshop_dir: Path) -> dict:
    """
    Process one workshop folder. Returns a dict of entry data, or None if
    the folder can't be resolved to a usable mod entry.
    """
    workshop_id = workshop_dir.name
    if not workshop_id.isdigit():
        return None

    mods_dir = workshop_dir / 'mods'
    if not mods_dir.is_dir():
        print(f"  [skip] {workshop_id} — no mods/ directory ({workshop_dir})")
        return None

    mod_ids = []
    first_folder_name = None
    name = None
    description = None

    for mod_subdir in sorted(mods_dir.iterdir()):
        if not mod_subdir.is_dir():
            continue
        if first_folder_name is None:
            first_folder_name = mod_subdir.name
        info = best_mod_info(mod_subdir)
        mod_id = clean_text(info.get('id') or mod_subdir.name)
        if mod_id and mod_id not in mod_ids:
            mod_ids.append(mod_id)
        if name is None and info.get('name'):
            name = clean_text(info['name'])
        if description is None and info.get('description'):
            description = clean_text(info['description'])

    if not mod_ids:
        print(f"  [skip] {workshop_id}: no mod IDs found")
        return None

    return {
        'workshop_id': workshop_id,
        'mod_ids': mod_ids,
        'map_folders': find_map_folders(workshop_dir),
        'name': name or first_folder_name or workshop_id,
        'description': description or '',
        'url': f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
    }


def main():
    if not WORKSHOP_BASE.exists():
        print(f"Workshop directory not found:\n  {WORKSHOP_BASE}")
        return

    print(f"Scanning {WORKSHOP_BASE} ...")
    entries = []
    skipped = 0

    for workshop_dir in sorted(WORKSHOP_BASE.iterdir()):
        if not workshop_dir.is_dir():
            continue
        entry = process_workshop(workshop_dir)
        if entry:
            entries.append(entry)
        else:
            skipped += 1

    entries.sort(key=lambda e: e['name'].lower())

    lines = []
    for e in entries:
        lines.append(f"# {e['name']}")
        if e['description']:
            lines.append(f"# {e['description']}")
        lines.append(f"# {e['url']}")
        lines.append(e['workshop_id'])
        lines.append(';'.join('\\' + mid for mid in e['mod_ids']) + ';')
        if e['map_folders']:
            lines.append(';'.join(e['map_folders']) + ';')
        lines.append('')

    OUTPUT_FILE.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Done. {len(entries)} entries written to:\n  {OUTPUT_FILE}")
    if skipped:
        print(f"  ({skipped} folders skipped — see [skip] lines above)")


if __name__ == '__main__':
    main()
