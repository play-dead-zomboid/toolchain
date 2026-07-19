# b42-mod-export

Build 42 mod list export + dependency gap check. Two scripts, run in order.

## 1. mod_exporter.py

Reads your installed workshop mods off disk (no network) and writes a Markdown
list of them — workshop ID, mod ID, name, summary, URL, map folders.

    python mod_exporter.py        ->  writes modexport.md

Edit `WORKSHOP_BASE` at the top if Steam isn't at the default path.

## 2. dep_crawler_b42.py

Reads a modexport file, fetches each mod's Steam Workshop page, and reports
required dependencies that are NOT already in your list — including transitive
ones (it crawls the missing deps too).

    python dep_crawler_b42.py

    reads   modexport.md          (step 1's output)
    writes  dep_report_b42.json   (the answer — read this)
            dep_cache_b42.json    (page cache; reused on re-runs, safe to delete)

Rate limited to one request per 15s. Leave it alone; it takes a while.

## Notes

Step 1's output feeds step 2 directly — same filename, no rename needed.

`modexport.md` in this folder is the last good export (Jul 2026), so you can run
step 2 on its own without re-exporting first.
