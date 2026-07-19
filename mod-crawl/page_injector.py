"""
page_injector.py  —  consolidated replacement for the per-season
SteamModCrawlerV3_pageInjector.py forks.

Injects a crawled mods JSON into the page.html template, producing the
standalone browsable mod page for a season.

Run:
    python page_injector.py --mods mods.json --output PlayDeadMods_s01.html
"""

import argparse
import json

PLACEHOLDER = "mods: [],  // This will be filled dynamically"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mods", default="mods.json",
                    help="crawled mods JSON (default: mods.json)")
    ap.add_argument("--template", default="page.html",
                    help="HTML template containing the placeholder (default: page.html)")
    ap.add_argument("--output", required=True,
                    help="HTML file to write")
    args = ap.parse_args()

    with open(args.mods, "r", encoding="utf-8") as f:
        mod_data = json.load(f)

    # Accept both the {"mod_data": [...]} wrapper and a bare list.
    if isinstance(mod_data, dict) and "mod_data" in mod_data:
        mods_list = mod_data["mod_data"]
    else:
        mods_list = mod_data

    mod_data_json = json.dumps(mods_list, ensure_ascii=False, indent=4)

    with open(args.template, "r", encoding="utf-8") as f:
        html_content = f.read()

    if PLACEHOLDER not in html_content:
        raise RuntimeError(f"Placeholder not found in template: {args.template}")

    html_content = html_content.replace(PLACEHOLDER, f"mods: {mod_data_json},")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Page generated successfully: {args.output} ({len(mods_list)} mods)")


if __name__ == "__main__":
    main()
