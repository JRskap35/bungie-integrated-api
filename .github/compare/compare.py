"""Temporary check for the build order rework: the old build (main) and the new one (this branch), run back to back
on the same day's sources, must make the same page, apart from the PvP weapons Pride misspelled (now matched to
Bungie and given their player data) and the ranks that shift around them."""
import json, re, sys
def blocks(p):
    s = open(p, encoding="utf-8").read()
    return {m.group(1): m.group(2) for m in re.finditer(r'<script id="([a-z-]+)" type="application/json">(.*?)</script>', s, re.S)}, s
(a, sa), (b, sb) = blocks(sys.argv[1]), blocks(sys.argv[2])
strip = lambda s: re.sub(r'<script id="vault-data" type="application/json">.*?</script>', "", s, flags=re.S)
print("Whole page identical:", sa == sb)
print("Page outside the weapon data identical:", strip(sa) == strip(sb))
for k in sorted(set(a) | set(b)):
    print(f"  block {k}: {'same' if a.get(k) == b.get(k) else 'DIFFERENT'}")
da = json.loads(a["vault-data"].replace("<\\/", "</")); db = json.loads(b["vault-data"].replace("<\\/", "</"))
print("PvE weapons identical:", da["weapons"] == db["weapons"], "| armor sets identical:", da["sets"] == db["sets"])
print("Other top level keys that differ:", [k for k in set(da) | set(db) if k not in ("pvp",) and da.get(k) != db.get(k)])
print("PvP keys that differ:", [k for k in set(da["pvp"]) | set(db["pvp"]) if k != "weapons" and da["pvp"].get(k) != db["pvp"].get(k)])
pa = {w["id"]: w for w in da["pvp"]["weapons"]}; pb = {w["id"]: w for w in db["pvp"]["weapons"]}
print("PvP weapon ids identical:", set(pa) == set(pb))
fields, renamed, other = {}, [], []
for k in pa:
    x, y = pa[k], pb.get(k, {})
    ks = sorted(f for f in set(x) | set(y) if x.get(f) != y.get(f))
    for f in ks: fields[f] = fields.get(f, 0) + 1
    if "name" in ks: renamed.append(f"{x['name']} -> {y['name']}: {', '.join(ks)}")
    elif ks and set(ks) - {"rank", "tier", "tierBy"}: other.append(f"{x['name']}: {', '.join(ks)}")
print("PvP weapons with any difference:", sum(1 for k in pa if pa[k] != pb.get(k)), "| fields:", fields)
print("Renamed (Pride's misspellings):"); [print("  " + r) for r in renamed]
print("Differences beyond rank or tier on weapons that were not renamed:", other or "none")
