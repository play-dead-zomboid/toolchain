# Weapon Scoring

A tool that scores every melee weapon and firearm on our server against the
**vanilla Project Zomboid baseline**, so you can spot which modded weapons are
out of line and need balancing — without having to eyeball raw stat blocks.

It produces plain Markdown tables. **You do not need to know Python to use the
results — just open the files in [`output/`](output/) and read them.**

---

## I just want to read the results (no setup)

Open these — they're already generated and committed:

- [`output/melee/_INDEX.md`](output/melee/_INDEX.md) — every modded melee weapon, worst-first, with its score and a `xref` column (multiple of the vanilla **Katana**).
- [`output/ranged/_INDEX.md`](output/ranged/_INDEX.md) — same for firearms (multiple of the vanilla **Shotgun**).
- [`output/melee/<workshopID>.md`](output/melee/) / [`output/ranged/<workshopID>.md`](output/ranged/) — one file per mod: a ranked table, a list of anything **out of line vs vanilla**, and a full stat record per weapon.
- [`output/base_melee_reference.md`](output/base_melee_reference.md) / [`output/base_ranged_reference.md`](output/base_ranged_reference.md) — the vanilla weapons themselves, scored, so you can see the yardstick.

### How to read a score

- **head** = the headline score. **100 ≈ the strongest vanilla weapons.** Higher = stronger.
- **tier** = S / A / B / C / D bucket of the head score.
- **floor → ceil** = the weapon at skill 0 vs skill 10. A big gap (e.g. a knife) means
  it's weak when untrained but excellent once you've leveled the skill; a small gap
  (e.g. a crowbar) means it's about the same the whole way up.
- **WARN n** / "out of line" = the weapon breaks the vanilla envelope for its class
  on `n` raw stats (e.g. more damage than any vanilla long blade). These are the
  prime balance suspects.
- **xref** (in the index) = how many times the reference weapon's score it is.
  `2.15x` means more than twice as strong as the vanilla anchor.

A score is **not** "the right answer." It's a consistent, explainable yardstick.
The point is comparison: *this mod sword vs a vanilla katana, stat by stat.*

---

## How the scores are built (the short version)

Weapons aren't scored by adding up stats — value in PZ isn't linear. The models
encode how weapons actually play:

- **Melee** ([`melee_model.py`](melee_model.py)) — kills-per-swing (B42 spreads damage
  across multi-hit targets) × crit × real attack speed × **stamina sustain** (the thing
  that actually gets you killed), reported across the skill curve. Durability counts but
  can't rescue a weapon too heavy to swing. Validated against vanilla + community tier lists.
- **Ranged** ([`ranged_model.py`](ranged_model.py)) — tuned from thousands of hours of play:
  range barely matters, **noise is deadly only when you can't clear what it pulls**,
  shotgun pellets = 2-3 kills/shot, **no-magazine guns get a friction bonus** (revolvers,
  break/pump shotguns), and piercing/stopping power matter. Aiming skill is the curve.

Full assumptions are documented at the top of each model file.

---

## Re-running it (after a mod or version change)

You need **Python 3** installed. Then:

1. Open [`config.py`](config.py) and check the two Steam paths near the top match
   this machine (where Steam put the mods, and where PZ is installed).
   **That file is the only thing you should ever need to edit.**
2. Make sure `pzserver.ini` **in this folder** is current — see below.
3. From this folder, run:

   ```
   python generate.py
   ```

4. Everything under [`output/`](output/) is regenerated. Commit it if it changed.

### pzserver.ini — you must supply this, and it is NOT in the repo

This tool reads `pzserver.ini` **from this folder**, not from the live server and
not from a season folder. It only scores mods listed there (both the
`WorkshopItems=` and `Mods=` lines), so other servers' downloads sitting in your
Steam folder are ignored.

**It is deliberately gitignored and will never be committed.** The live server
config contains the Discord bot token, the RCON password, and the server join
password — none of which belong in a public repo. So:

    copy the live pzserver.ini into this folder before running.

If it's missing, `generate.py` will fail — that's intended. Don't work around it
by committing the file.

The copy here is also a **snapshot**. When the server's mod list changes, refresh
it before re-running, or you're scoring last season's mod list and won't be told.

---

## Files

| File | What it is |
|---|---|
| `config.py` | Paths. The only per-machine file to edit. |
| `pzserver.ini` | Snapshot of the server's mod list. Refresh when it changes. |
| `common.py` | Reads the script files and the server mod list. |
| `melee_model.py` | Melee scoring + assumptions. |
| `ranged_model.py` | Firearm scoring + assumptions. |
| `generate.py` | Runs everything, writes `output/`. |
| `output/` | The generated reports (read these). |

Built as a balance baseline. Tuning the actual weapon numbers and playtesting is a
separate job — this just tells you *where to look*.
