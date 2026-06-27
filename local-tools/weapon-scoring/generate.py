"""
Entry point. Run:   python generate.py

Reads the server mod list, scores every melee + ranged weapon (server mods AND the
base game) against the vanilla baseline, and writes Markdown reports to ./output/.

You do not need to understand the scoring to use the output -- open the _INDEX.md
files and read the tables. Higher score = stronger; anything flagged is out of line
with vanilla. See README.md.
"""
import os
import config, common
import melee_model, ranged_model

def _detail(kind, r):
    if kind == "melee":
        return (f"- {r['cls']} / {r['hand']}  |  power {r['power']:.0f} (floor {r['floor']:.0f} -> ceil {r['ceil']:.0f})  "
                f"|  durability {r['durab']:.0f}  sustain {r['sustain']:.2f}\n"
                f"- raw: dmg {r['dmg']:.2f}  hit {r['hit']:.0f}  crit {r['crit']:.0f}  "
                f"reach {r['rng']:.2f}  weight {r['wt']:.1f}  durability {r['durv']:.0f}")
    return (f"- {r['cls']} / {r['hand']}  |  power {r['power']:.0f} (floor {r['floor']:.0f} -> ceil {r['ceil']:.0f})  "
            f"|  reliability {r['reliab']:.0f}\n"
            f"- raw: dmg {r['dmg']:.2f}  pellets {r['pellets']:.0f}  hit {r['hit']:.0f}  crit {r['crit']:.0f}  "
            f"ammo {r['ammo']}  mag {r['mag']:.0f}  range {r['rng']:.0f}  jam {r['jam']:.0f}  noise {r['sound']:.0f}")

def _table_header(kind):
    if kind == "melee":
        return ("| weapon | class | tier | head | power | floor->ceil | durab | flags |\n"
                "|---|---|:--:|---:|---:|---|---:|---|")
    return ("| weapon | class | tier | head | power | floor->ceil | ammo | flags |\n"
            "|---|---|:--:|---:|---:|---|---|---|")
def _table_row(kind, r, fl, M):
    extra = f"{r['durab']:.0f}" if kind == "melee" else r['ammo']
    return (f"| {r['name']} | {r['cls']} | {M.tier(r['head'])} | {r['head']:.0f} | {r['power']:.0f} | "
            f"{r['floor']:.0f}->{r['ceil']:.0f} | {extra} | {'WARN '+str(len(fl)) if fl else ''} |")

def generate(M, predicate, subdir, anchor_name):
    kind = M.KIND
    outdir = os.path.join(config.OUTPUT_DIR, subdir)
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.endswith(".md"): os.remove(os.path.join(outdir, f))
    cal = M.calibrate()

    # base-game reference + anchor
    base = common.parse_weapon_txt(config.BASE_WEAPON_TXT)
    base_recs = [(M.record(n, p, cal), p) for n, p in base.items() if predicate(p, n)]
    base_recs.sort(key=lambda x: -x[0]["head"])
    anchor = next((r["head"] for r, _ in base_recs if r["name"] == anchor_name), 100.0)
    _write_reference(M, base_recs, os.path.join(config.OUTPUT_DIR, f"base_{subdir}_reference.md"))

    # server mod weapons, grouped by workshop
    by_wid = {}
    for wid, fold, modpath in common.iter_server_mods():
        weps = common.mod_weapons(modpath, predicate)
        for n, p in weps.items():
            by_wid.setdefault(wid, {})[n] = p

    all_rows = []
    for wid in sorted(by_wid):
        rows = []
        for n, p in by_wid[wid].items():
            r = M.record(n, p, cal); fl = M.outlier_flags(p, cal)
            rows.append((r, fl, p)); all_rows.append((r, fl, wid))
        rows.sort(key=lambda x: -x[0]["head"])
        _write_mod(M, wid, rows, outdir)

    _write_index(M, all_rows, anchor, anchor_name, os.path.join(outdir, "_INDEX.md"))
    return len(by_wid), len(all_rows), sum(1 for r, fl, _ in all_rows if fl)

def _write_reference(M, recs, path):
    out = [f"# Base game {M.KIND} weapons - reference baseline", "",
           f"{len(recs)} vanilla weapons. 100 = top of vanilla (p95). This is the yardstick mod weapons are measured against.", "",
           _table_header(M.KIND)]
    for r, p in recs:
        out.append(_table_row(M.KIND, r, [], M))
    open(path, "w", encoding="utf-8").write("\n".join(out))

def _write_mod(M, wid, rows, outdir):
    out = [f"# Workshop {wid} - {M.KIND} weapon scores", "",
           "Scored vs vanilla (100 = top of vanilla). Tiers S/A/B/C/D. 'WARN n' = exceeds vanilla limits.", "",
           "## Ranked", "", _table_header(M.KIND)]
    for r, fl, p in rows: out.append(_table_row(M.KIND, r, fl, M))
    outl = [(r, fl) for r, fl, p in rows if fl]
    out += ["", f"## Out of line vs vanilla ({len(outl)} of {len(rows)})", ""]
    out += [f"- **{r['name']}** ({r['cls']}, {M.tier(r['head'])} {r['head']:.0f}): " + "; ".join(fl) for r, fl in outl] or ["_none_"]
    out += ["", "## Full records", ""]
    for r, fl, p in rows:
        out.append(f"### {r['name']} - {M.tier(r['head'])} ({r['head']:.0f})")
        out.append(_detail(M.KIND, r))
        if fl: out.append(f"- WARNING: " + "; ".join(fl))
        out.append("")
    open(os.path.join(outdir, f"{wid}.md"), "w", encoding="utf-8").write("\n".join(out))

def _write_index(M, all_rows, anchor, anchor_name, path):
    all_rows.sort(key=lambda x: -x[0]["head"])
    out = [f"# {M.KIND.title()} weapons - cross-mod index (server mods, worst-first)", "",
           f"Reference: vanilla {anchor_name} = {anchor:.0f}. {len(all_rows)} weapons.", "",
           f"| weapon | workshop | class | tier | head | xref | flags |", "|---|---|---|:--:|---:|---:|:--:|"]
    for r, fl, wid in all_rows:
        out.append(f"| {r['name']} | {wid} | {r['cls']} | {M.tier(r['head'])} | {r['head']:.0f} | "
                   f"{r['head']/anchor:.2f}x | {'WARN '+str(len(fl)) if fl else ''} |")
    open(path, "w", encoding="utf-8").write("\n".join(out))

if __name__ == "__main__":
    print("Scoring melee weapons...")
    m = generate(melee_model,  common.is_melee,  "melee",  "Katana")
    print(f"  melee : {m[0]} mods, {m[1]} weapons, {m[2]} out-of-line")
    print("Scoring ranged weapons...")
    r = generate(ranged_model, common.is_ranged, "ranged", "Shotgun")
    print(f"  ranged: {r[0]} mods, {r[1]} weapons, {r[2]} out-of-line")
    print(f"\nReports written under: {config.OUTPUT_DIR}")
