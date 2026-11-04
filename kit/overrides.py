"""Joe's manual perk edits from the perk editor (2026-11-04), applied on top of the sheets and the player ranking.
Usage: python3 -I overrides.py data.json overrides.json OUT.json SHEET_OUT.json      apply
       python3 -I overrides.py --check overrides.json                              check the file's shape only

overrides.json (assets/perk_overrides.json, written by the perk editor's UPDATE task):
  {"v": 1, "pve": {weapon id: {"barrel": [...], "mag": [...], "p1": [...], "p2": [...]}}, "pvp": {...}}
Only the columns Joe changed are listed; every other column keeps following the sheets and the player data. An edit
stays through every weekly update until Joe resets it in the editor. Weapons no longer on a sheet are skipped (and
named in the report). SHEET_OUT.json keeps what each edited column would have been without the edit, so the editor can
show what Reset goes back to."""
import json, os, sys

COLS = ("barrel", "mag", "p1", "p2")

def check(o):
    bad = []
    if not isinstance(o, dict): return ["not a JSON object"]
    for mode in ("pve", "pvp"):
        m = o.get(mode, {})
        if not isinstance(m, dict): bad.append(f"{mode} is not an object"); continue
        for wid, cols in m.items():
            if not isinstance(cols, dict) or not cols: bad.append(f"{mode} {wid}: no columns"); continue
            for c, v in cols.items():
                if c not in COLS: bad.append(f"{mode} {wid}: unknown column {c}")
                elif not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                    bad.append(f"{mode} {wid} {c}: must be a list of perk names (an empty list leaves the column blank)")
                elif len(set(v)) != len(v): bad.append(f"{mode} {wid} {c}: a perk is listed twice")
    return bad

if sys.argv[1] == "--check":
    o = json.load(open(sys.argv[2])); bad = check(o)
    if bad: print("Perk overrides file is not valid:"); [print("  " + b) for b in bad]; sys.exit(1)
    print(f"Perk overrides valid: {sum(len(o.get(m, {})) for m in ('pve', 'pvp'))} weapons"); sys.exit(0)

DATA, OVR, OUT, SHEET = sys.argv[1:5]
d = json.load(open(DATA))
o = json.load(open(OVR)) if os.path.exists(OVR) else {"v": 1, "pve": {}, "pvp": {}}
bad = check(o)
if bad: print("STOPPING, the perk overrides file is not valid:"); [print("  " + b) for b in bad]; sys.exit(1)
lists = {"pve": d["weapons"], "pvp": (d.get("pvp") or {}).get("weapons", [])}
sheet, applied, missing = {"pve": {}, "pvp": {}}, 0, []
for mode in ("pve", "pvp"):
    by = {w["id"]: w for w in lists[mode]}
    for wid, cols in o.get(mode, {}).items():
        w = by.get(wid)
        if not w: missing.append(f"{mode} {wid}"); continue
        sheet[mode][wid] = {c: w.get(c, []) for c in cols}
        for c, v in cols.items(): w[c] = list(v)
        applied += 1
json.dump(d, open(OUT, "w"), ensure_ascii=False)
json.dump(sheet, open(SHEET, "w"), ensure_ascii=False)
print(f"Perk editor: {applied} edited weapons applied" + (f"; not on the sheets any more, skipped: {', '.join(missing)}" if missing else ""))
