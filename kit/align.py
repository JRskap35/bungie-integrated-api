"""PvP weapons follow Aegis's sheet (Joe, 2026-11-11): a PvP weapon that is also on Aegis's sheet takes Aegis's section,
ammo type, energy, frame, season and source, so both modes file and describe every weapon the same way.
Usage: python3 -I align.py data.json OUT.json REPORT.txt

Runs after the cross check (which uses Pride's own frame names for Hugo's kill times) and before the hash map and the
player ranking, so the ranking places each weapon in Aegis's section. A weapon Aegis lists twice under one name (High
Albedo: an Adaptive Burst sidearm and a Micro-Missile rocket sidearm) is matched by frame. Weapon ids stay as they are,
so saved marks keep working. PvP weapons Aegis doesn't list keep Pride's details and are named in the report."""
import json, re, sys, collections

IN, OUT, REPORT = sys.argv[1:4]
d = json.load(open(IN))
nn = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("’", "'"))
def fnorm(s):
    s = re.sub(r"\s*\(.*?\)", "", s or "").strip()
    s = re.sub(r"\s*(frame|glaive|sword frame|sword|heat weapon|weapon)$", "", s, flags=re.I)
    return nn(s).replace("rapidfire", "rapid")
FIELDS = ("a", "arch", "element", "frame", "frameNote", "season", "source", "srcX")
pve = collections.defaultdict(list)
for w in d["weapons"]: pve[nn(w["name"])].append(w)
moved, changed, orphans = [], collections.Counter(), []
for p in d["pvp"]["weapons"]:
    cands = pve.get(nn(p["name"]))
    if not cands: orphans.append(f"{p['arch']}: {p['name']}"); continue
    t = sorted(cands, key=lambda w: (fnorm(w.get("frame")) != fnorm(p.get("frame")), w["arch"] != p["arch"]))[0]
    if t["arch"] != p["arch"]: moved.append(f"{p['name']}: {p['arch']} to {t['arch']}")
    for f in FIELDS:
        if f in t and p.get(f) != t[f]: changed[f] += 1; p[f] = t[f]
json.dump(d, open(OUT, "w"), ensure_ascii=False)
names = {"a": "ammo type", "arch": "section", "element": "energy", "frame": "frame", "frameNote": "frame note", "season": "season", "source": "source", "srcX": "source flag"}
with open(REPORT, "w") as f:
    f.write(f"PvP weapons lined up with Aegis's sheet: {sum(1 for p in d['pvp']['weapons']) - len(orphans)} matched; "
            + (", ".join(f"{names[k]} {v}" for k, v in changed.items()) or "nothing to change") + "\n")
    if moved: f.write("Moved to Aegis's section: " + "; ".join(moved) + "\n")
    if orphans: f.write(f"PvP weapons Aegis doesn't list ({len(orphans)}, kept with Pride's details): " + ", ".join(orphans) + "\n")
print(open(REPORT).read().strip())
