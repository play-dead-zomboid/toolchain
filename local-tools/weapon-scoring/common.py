"""
Shared plumbing: parse PZ weapon scripts, read the server's mod list, and walk
the workshop folders. No scoring math here (see melee_model.py / ranged_model.py).
"""
import os, re
import config

# ---------- property access (case-insensitive; PZ scripts mix casing/styles) ----------
def num(p, k, d=0.0):
    v = p.get(k.lower())
    try: return float(v)
    except: return d
def flag(p, k): return str(p.get(k.lower(), "")).lower() == "true"
def gcat(p): return p.get("categories", "").lower()   # 'base:blunt' or 'Blunt'

# ---------- parse 'item Name { Key = Value, ... }' blocks ----------
def parse_weapon_txt(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)          # strip block comments
    items = {}
    for m in re.finditer(r"\bitem\s+([^\s{]+)\s*\{", t):
        i = m.end() - 1; depth = 0; body = ""
        for j in range(i, len(t)):
            if t[j] == '{': depth += 1
            elif t[j] == '}':
                depth -= 1
                if depth == 0: body = t[i+1:j]; break
        pr = {}
        for ln in body.split(","):
            if "=" in ln:
                k, v = ln.split("=", 1)
                pr[k.strip().lower()] = v.strip()        # keys lowercased for robustness
        items[m.group(1)] = pr
    return items

# ---------- what counts as a weapon ----------
def is_melee(p, name=""):
    if name.endswith("_Broken"): return False
    if flag(p, "Ranged"): return False
    if any(k in p for k in ("explosionpower","ammotype","explosiontimer","firestartingchance",
        "firestartingenergy","noiseduration","sensorrange")): return False
    is_wep = ("weapon" in p.get("itemtype","").lower()) or (p.get("type","").lower() == "weapon")
    return is_wep and (num(p,"MaxHitcount") >= 1 or p.get("subcategory","") in ("Swinging","Stab"))

def is_ranged(p, name=""):
    is_gun = flag(p,"Ranged") or (p.get("subcategory","") == "Firearm" and "ammotype" in p)
    if not is_gun: return False
    return (num(p,"MinDamage") + num(p,"MaxDamage")) > 0   # exclude 0-dmg cap guns

# ---------- the server's mod list (source of truth) ----------
def server_sets():
    """Returns (set of workshop IDs, set of enabled mod-folder names) from pzserver.ini."""
    txt = open(config.SERVER_INI, encoding="utf-8", errors="replace").read()
    wi = re.search(r'^WorkshopItems\s*=\s*(.*)$', txt, re.M)
    md = re.search(r'^Mods\s*=\s*(.*)$', txt, re.M)
    ids  = set(x.strip() for x in (wi.group(1).split(';') if wi else []) if x.strip())
    mods = set(x.strip().lstrip('\\') for x in (md.group(1).split(';') if md else []) if x.strip())
    return ids, mods

# ---------- walk a mod's script files (latest version + common) ----------
_VER = re.compile(r"^\d+(\.\d+)+$")
def script_roots(modpath):
    try: subs = [d for d in os.listdir(modpath) if os.path.isdir(os.path.join(modpath, d))]
    except OSError: return []
    vers = [d for d in subs if _VER.match(d)]; roots = []
    if vers: roots.append(os.path.join(modpath, max(vers, key=lambda d: tuple(int(x) for x in d.split(".")))))
    else: roots.append(modpath)
    if "common" in subs: roots.append(os.path.join(modpath, "common"))
    return roots

def find_script_txts(root):
    out = []; sp = os.path.join(root, "media", "scripts")
    if os.path.isdir(sp):
        for dp, _, fn in os.walk(sp):
            out += [os.path.join(dp, f) for f in fn if f.lower().endswith(".txt")]
    return out

def modinfo(modpath):
    info = {}; p = os.path.join(modpath, "mod.info")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            if "=" in line:
                k, v = line.split("=", 1); k = k.strip().lower()
                if k == "name" and "name" not in info: info["name"] = v.strip()
    return info

def iter_server_mods():
    """Yield (workshop_id, folder_name, modpath) for every server-enabled mod folder on disk."""
    ids, mods = server_sets()
    for wid in sorted(ids):
        modsdir = os.path.join(config.WORKSHOP_DIR, wid, "mods")
        if not os.path.isdir(modsdir): continue
        disk = [d for d in os.listdir(modsdir) if os.path.isdir(os.path.join(modsdir, d))]
        enabled = [d for d in disk if d in mods] or disk     # fall back to all if names don't match
        for fold in sorted(enabled):
            yield wid, fold, os.path.join(modsdir, fold)

def mod_weapons(modpath, predicate):
    """Return {name: props} for weapons in a mod matching predicate (is_melee/is_ranged)."""
    out = {}
    for r in script_roots(modpath):
        for txt in find_script_txts(r):
            try: items = parse_weapon_txt(txt)
            except OSError: continue
            for n, p in items.items():
                if predicate(p, n): out.setdefault(n, p)
    return out
