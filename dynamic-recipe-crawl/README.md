# dynamic-recipe-crawl

Scans the base game + every installed workshop mod for crafting recipes, then
builds the searchable recipe browser page.

    python recipe-extractor.py

One command does everything. Parses recipe inputs/outputs, tags, flags, and
item mappers.

## Output

    ../recipe-search.html    the searchable recipe browser (this is the deliverable)
    output/recipes.json              every recipe, full detail
    output/recipes_display.json      trimmed for the browser
    output/recipes_normalized.json   compact form embedded in the page
    output/recipe_vocab.json         vocabulary for the filters
    output/recipe_errors.json        recipes that failed to parse

The HTML is written one level up, into `toolchain/`. Recipe data is gzipped and
base64'd into `template.html`, so the page is a single self-contained file.

## Paths to edit on a different machine

Both are constants at the top of the file:

    line 16   ROOT_WORKSHOP_PATH   ...steamapps\workshop\content\108600
    line 17   BASE_GAME_ROOT       ...steamapps\common\ProjectZomboid

## Files

    template.html   required — needs the __RECIPES_PAYLOAD__ and
                    __RECIPE_VOCAB_PAYLOAD__ markers, don't remove them
