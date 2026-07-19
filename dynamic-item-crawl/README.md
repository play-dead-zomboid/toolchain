# dynamic-item-crawl

Scans the base game + every installed workshop mod for item definitions, then
builds the searchable item browser page.

    python Item-extractor.py

One command does everything. Takes a while — it parses every script file in
every mod.

## Output

    ../play-dead.html    the searchable item browser (this is the deliverable)
    output/items.json                 every item, full raw + resolved properties
    output/items_display.json         trimmed for the browser
    output/property_vocabulary.json   every property name seen, for the filters
    output/errors.json                files that failed to parse

The HTML is written one level up, into `toolchain/`, next to the other pages.
Item data is gzipped and base64'd into `template.html`, so the page is a single
self-contained file you can open or hand to anyone.

## Paths to edit on a different machine

**Two places, not one:**

    line 11   ROOT_WORKSHOP_PATH   ...steamapps\workshop\content\108600
    in main() base_game_root       ...steamapps\common\ProjectZomboid

The base-game path is hardcoded inline inside `main()` rather than up top with
the other constant. Easy to miss.

## Files

    template.html   required — needs the __ITEMS_PAYLOAD__ and
                    __PROPERTY_VOCAB_PAYLOAD__ markers, don't remove them
