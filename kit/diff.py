"""Compare the data inside two Vault builds and report what changed.
Usage: python3 -I diff.py OLD NEW [NEW_FULL]   (each is a data.json or a built the-vault.html)
NEW_FULL is the finished build's data (bungie.py output); with it, PvP changes are listed too: what Pride changed on his
sheet (weapons, his tiers) and what moved on the site after the player ranking (tiers and perk lists)."""
import json, re, sys
def load(p):
    s = open(p, encoding="utf-8").read()
    if p.endswith(".html"):
        m = re.search(r'<script id="vault-data" type="application/json">(.*?)</script>', s, re.S)
        s = m.group(1).replace("<\\/", "</")
    return json.loads(s)
old, new = load(sys.argv[1]), load(sys.argv[2])
ow = {w["id"]: w for w in old["weapons"]}; nw = {w["id"]: w for w in new["weapons"]}
os_ = {s["id"]: s for s in old["sets"]}; ns = {s["id"]: s for s in new["sets"]}
added = [nw[k] for k in nw if k not in ow]; removed = [ow[k] for k in ow if k not in nw]
print(f"Weapons: {len(ow)} -> {len(nw)}   Sets: {len(os_)} -> {len(ns)}")
print(f"\nNEW WEAPONS ({len(added)})"); [print(f"  {w['arch']}: {w['name']} {w['var']} [{w['tier']}]") for w in added]
print(f"\nREMOVED OR RENAMED WEAPONS ({len(removed)})  <- saved marks on these ids would be orphaned"); [print(f"  {w['arch']}: {w['name']} {w['var']}") for w in removed]
print("\nTIER CHANGES")
for k in nw:
    if k in ow and ow[k]["tier"] != nw[k]["tier"]:
        print(f"  {nw[k]['arch']}: {nw[k]['name']}  {ow[k]['tier']} -> {nw[k]['tier']}")
print("\nPERK / ORIGIN / SOURCE CHANGES")
for k in nw:
    if k in ow:
        diffs = [f for f in ("p1","p2","barrel","mag","origin","source","frame","element") if ow[k].get(f) != nw[k].get(f)]
        if diffs: print(f"  {nw[k]['arch']}: {nw[k]['name']}  ({', '.join(diffs)})")
print(f"\nNEW SETS: {[ns[k]['name'] for k in ns if k not in os_]}")
print(f"REMOVED SETS: {[os_[k]['name'] for k in os_ if k not in ns]}")
for k in ns:
    if k in os_:
        a = [(b['pcs'], b['tier']) for b in os_[k]['bonuses']]; b = [(x['pcs'], x['tier']) for x in ns[k]['bonuses']]
        if a != b: print(f"  bonus tier change: {ns[k]['name']} {a} -> {b}")

# ---------- PvP: Pride's sheet and the player ranking (2026-11-04) ----------
if len(sys.argv) > 3:
    full = load(sys.argv[3])
    op = {w["id"]: w for w in (old.get("pvp") or {}).get("weapons", [])}; np_ = {w["id"]: w for w in (full.get("pvp") or {}).get("weapons", [])}
    if op and np_:
        nm = lambda w: f"{w['arch']}: {w['name']}"
        print(f"\nPVP WEAPONS: {len(op)} -> {len(np_)}")
        print(f"NEW PVP WEAPONS ({sum(1 for k in np_ if k not in op)})"); [print(f"  {nm(np_[k])} [{np_[k]['tier']}]") for k in np_ if k not in op]
        print(f"REMOVED PVP WEAPONS ({sum(1 for k in op if k not in np_)})"); [print(f"  {nm(op[k])}") for k in op if k not in np_]
        pr = lambda w: (w.get("pr") or [None])[0]
        print("PRIDE'S TIER CHANGES (his sheet)")
        for k in np_:
            if k in op and pr(op[k]) and pr(np_[k]) and pr(op[k]) != pr(np_[k]): print(f"  {nm(np_[k])}  {pr(op[k])} -> {pr(np_[k])}")
        print("PVP TIER CHANGES ON THE SITE (player ranking)")
        for k in np_:
            if k in op and op[k].get("tier") != np_[k].get("tier"): print(f"  {nm(np_[k])}  {op[k].get('tier')} -> {np_[k].get('tier')}")
        print("PVP PERK CHANGES ON THE SITE")
        names = lambda a: [x[0] if isinstance(x, list) else x for x in (a or [])]
        for k in np_:
            if k in op:
                diffs = [f for f in ("p1", "p2", "barrel", "mag") if names(op[k].get(f)) != names(np_[k].get(f))] + (["mw"] if op[k].get("mw") != np_[k].get("mw") else [])
                if diffs: print(f"  {nm(np_[k])}  ({', '.join(diffs)})")
