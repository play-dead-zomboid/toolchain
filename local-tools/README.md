# local-tools

Tools that run **locally on an admin's machine** (Python scripts), as opposed to
the browser-based tools elsewhere in this repo. They read the game/mod files on
disk directly.

Each subfolder is one tool with its own README.

| Tool | What it does |
|---|---|
| [`weapon-scoring/`](weapon-scoring/) | Scores every modded melee weapon and firearm against the vanilla baseline so you can see what's out of balance. Pre-generated results are in its `output/` folder — no setup needed to read them. |

Requires Python 3 to re-run; reading the committed output needs nothing.
