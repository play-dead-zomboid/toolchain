# mod-crawl

Turn a list of workshop mods into a searchable HTML mod page. Three steps; you
can start at step 2 if you already have the mod IDs.

## 1. collection_extractor.py  (optional)

Scrapes a Steam *collection* page for the mods in it. Needs Chrome + selenium.

    python collection_extractor.py --collection-id 2490220997 --output urls.txt

## 2. steam_mod_crawler.py

Fetches each mod's workshop page for title, description, Mod ID, tags, and
dependencies — then recursively crawls those dependencies too.

    python steam_mod_crawler.py --input mods.txt --output mods.json

    --input-mode ids    (default) mods.txt is semicolon-separated workshop IDs
    --input-mode urls   input is one workshop URL per line (step 1's output)
    --delay             seconds between requests, default 30

Merges into the output file, so re-running only adds what's missing, and you can
stop and resume. **Don't drop `--delay` much below 20 or Steam throttles you.**

## 3. page_injector.py

Injects the crawled JSON into `page.html` (included here — Vue + bootstrap,
searchable table).

    python page_injector.py --mods mods.json --output PlayDeadMods.html

## Files

    page.html     the template, required by step 3
    mods.txt      you supply this — workshop IDs separated by semicolons
