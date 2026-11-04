"""Everything the perk editor needs on top of the finished site data (Joe, 2026-11-04).
Usage: python3 -I perk_pools.py data.json ticons.json CACHE overrides.json sheet.json editor_config.json OUT_editor.json OUT_ticons.json

data.json       the finished build (bungie.py output, edits already applied)
ticons.json     the site's perk icons (bungie.py output); icons the pools add are drawn the same way and merged in
overrides.json  Joe's edits as they stand on the site (assets/perk_overrides.json)
sheet.json      what each edited column would be without the edit (overrides.py output), for Reset
editor_config   {"task": scheduled task id UPDATE fires, "artifact": the editor's claude.ai address}

For every weapon on either sheet, the barrels, magazines and perks that roll in each column on Bungie (every random
roll copy of the weapon, newest first, enhanced copies left out), each with its icon. Writes OUT_editor.json for the
page's "vault-editor" block and OUT_ticons.json, the site's perk icons plus the new ones."""
import json, os, re, sys, io, base64, hashlib, subprocess, collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import numpy as np
from PIL import Image

DATA, TICONS, CACHE, OVR, SHEET, CFG, OUT, OUT_T = sys.argv[1:9]
BASE = "https://www.bungie.net"
nn = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("’", "'"))
rkey = lambda w: w["arch"] + "|" + re.sub(r"[^a-z0-9]", "", str(w["name"]).lower())   # the page's rkeyOf
man = json.load(open(os.path.join(CACHE, "manifest.json")))["Response"]; ver = man["version"]
comp = lambda k: json.load(open(os.path.join(CACHE, f"{k}-{ver}.json")))
items = comp("DestinyInventoryItemDefinition"); plugsets = comp("DestinyPlugSetDefinition")
d = json.load(open(DATA)); ticons = json.load(open(TICONS))

WEAP = collections.defaultdict(list)
for it in items.values():
    n = (it.get("displayProperties") or {}).get("name")
    if n and it.get("itemType") == 3: WEAP[nn(n)].append(it)
BARREL = {"barrels", "tubes", "bowstrings", "blades", "hafts", "scopes", "rails", "v950.new.sword0.blades"}
MAG = {"magazines", "magazines_gl", "arrows", "batteries", "guards", "bolts", "v950.new.sword0.guards"}
def sockets(it):
    """(plug category, [(name, icon path)]) per socket in game order, enhanced copies left out (crosscheck.py's columns)"""
    out = []
    for se in it.get("sockets", {}).get("socketEntries", []):
        hs = [se["singleInitialItemHash"]] if se.get("singleInitialItemHash") else []
        hs += [x["plugItemHash"] for x in se.get("reusablePlugItems", [])]
        for k in ("randomizedPlugSetHash", "reusablePlugSetHash"):
            if se.get(k): hs += [x["plugItemHash"] for x in plugsets.get(str(se[k]), {}).get("reusablePlugItems", [])]
        got, cat = {}, None
        for h in hs:
            p = items.get(str(h))
            if not p or not p.get("plug"): continue
            dp = p.get("displayProperties") or {}; n = dp.get("name", "")
            if not n or "enhanced" in (p.get("itemTypeDisplayName") or "").lower() or re.match(r"^empty ", n, re.I): continue
            cat = cat or p["plug"].get("plugCategoryIdentifier", ""); got.setdefault(n, dp.get("icon", ""))
        if got: out.append((cat, list(got.items())))
    return out
def pools(name):
    copies = sorted(WEAP.get(nn(name), []), key=lambda it: (bool(it.get("screenshot")), bool(it.get("iconWatermark")), it.get("index", 0)), reverse=True)
    cols = {c: {} for c in ("barrel", "mag", "p1", "p2")}
    for it in copies:
        traits = 0
        for cat, plugs in sockets(it):
            col = None
            if cat == "frames" and traits < 2: col = ("p1", "p2")[traits]; traits += 1
            elif cat in BARREL or (cat or "").startswith("v950.new.sword") and "blade" in cat: col = "barrel"
            elif cat in MAG or (cat or "").startswith("v950.new.sword") and "guard" in cat: col = "mag"
            if col:
                for n, ic in plugs: cols[col].setdefault(n, ic)
    return cols

# ---------- pools per weapon (PvE and PvP twins share one entry) ----------
P, need = {}, set()
for w in d["weapons"] + (d.get("pvp") or {}).get("weapons", []):
    k = rkey(w)
    if k in P: continue
    cols = pools(w["name"])
    P[k] = cols; need.update(ic for c in cols.values() for ic in c.values() if ic)

# ---------- icons, drawn exactly like bungie.py's perk glyphs so shared ones keep the same id ----------
os.makedirs(os.path.join(CACHE, "img"), exist_ok=True)
def fetch(p):
    f = os.path.join(CACHE, "img", os.path.basename(p))
    if not os.path.exists(f) or os.path.getsize(f) == 0:
        r = subprocess.run(["curl", "-sS", "--fail", "--retry", "3", "--max-time", "120", "-o", f, BASE + p])
        if r.returncode: return p, None
    return p, f
with ThreadPoolExecutor(12) as ex: files = dict(ex.map(fetch, sorted(need)))
def uri(im, fmt="PNG", **kw):
    b = io.BytesIO(); im.save(b, fmt, **kw); return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()
def glyph(im, size=56):
    a = np.asarray(im).astype(float); alpha = a[..., 3] / 255.0
    lum = a[..., :3].mean(axis=2) / 255.0
    if alpha.min() > 0.95:
        alpha = np.clip((lum - 0.15) / 0.75, 0, 1)
    ys, xs = np.where(alpha > 0.12)
    if ys.size:
        alpha = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]; lumc = lum[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        h, w = alpha.shape; side = int(max(h, w) / 0.9); box = np.zeros((side, side)); oy, ox = (side - h) // 2, (side - w) // 2
        box[oy:oy + h, ox:ox + w] = alpha; alpha = box
    rgba = np.zeros((*alpha.shape, 4), np.uint8); rgba[..., :3] = 255; rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return uri(Image.fromarray(rgba, "RGBA").resize((size, size), Image.LANCZOS), optimize=True)
tid = lambda u: "b" + hashlib.md5(u.encode()).hexdigest()[:10]
ID, added = {}, 0
for p, f in files.items():
    if not f: continue
    try: u = glyph(Image.open(f).convert("RGBA"))
    except Exception: continue
    k = tid(u); ID[p] = k
    if k not in ticons: ticons[k] = u; added += 1

out_pools = {k: {c: [[n, ID.get(ic, "")] for n, ic in plugs.items()] for c, plugs in cols.items()} for k, cols in P.items()}
ovr = json.load(open(OVR)) if os.path.exists(OVR) else {}
cfg = json.load(open(CFG)) if os.path.exists(CFG) else {}
editor = {"pools": out_pools, "overrides": {m: ovr.get(m, {}) for m in ("pve", "pvp")}, "sheet": json.load(open(SHEET)),
          "task": cfg.get("task", ""), "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
json.dump(editor, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(ticons, open(OUT_T, "w"), separators=(",", ":"))
empty = [k for k, c in P.items() if not any(c.values())]
print(f"Perk editor: roll pools for {len(P)} weapons ({len(empty)} not on Bungie), {len(ID)} icons, {added} new")
