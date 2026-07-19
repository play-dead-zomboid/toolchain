# dynamic-vehicle-crawl

Scans the base game + all workshop mods for vehicle definitions and dumps them
to one JSON file.

    python extractor.py        ->  writes vehicle_summary.json

Picks up `vehicle`, `template vehicle`, and vehicle-related item blocks, tracks
which mod each came from, and resolves template inheritance.

Edit `SEARCH_ROOTS` at the top if Steam isn't at the default path. Everything
else is self-contained — no input files needed.

Output lands in whatever directory you run it from, so `cd` here first.
