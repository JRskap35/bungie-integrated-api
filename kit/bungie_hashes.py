"""Hash maps that let the page read a Bungie account's weapons (Bungie-Integrated-API).
Usage: python3 -I bungie_hashes.py data.json CACHE_DIR OUT_hashes.json
data.json is bungie.py's output (both modes). CACHE_DIR holds Bungie's manifest (bungie.py downloads it).
Writes {"v": manifest version,
        "w": {item hash: weapon key},            every copy of every weapon on either sheet, adept / harrowed / timelost included
        "p": {plug hash: [name, kind]}}          every plug those weapons can roll; kind is
             "perk" (trait columns), "barrel", "mag", "mw" (masterwork, name without "Masterworked: "), "frame", "origin"
The weapon key is the same one the page builds (section + "|" + the name in lower case letters and digits), so an
owned copy lands on the right row in both PvE and PvP."""
import json, sys, os, re, collections

DATA, CACHE, OUT = sys.argv[1:4]
man = json.load(open(os.path.join(CACHE, "manifest.json")))["Response"]
ver = man["version"]
comp = lambda k: json.load(open(os.path.join(CACHE, f"{k}-{ver}.json")))
items = comp("DestinyInventoryItemDefinition"); plugsets = comp("DestinyPlugSetDefinition")
d = json.load(open(DATA))
nn = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("’", "'"))
base_name = lambda s: re.sub(r"\s*\((adept|harrowed|timelost|baroque)\)\s*$", "", s or "", flags=re.I)
key = lambda arch, name: arch + "|" + nn(name)

# the page's weapon keys, by name (one name can sit in two sections only in rare cases; both are kept)
wanted = collections.defaultdict(set)
for w in d["weapons"] + (d.get("pvp") or {}).get("weapons", []):
    wanted[nn(w["name"])].add(key(w["arch"], w["name"]))

BARREL = {"barrels", "tubes", "bowstrings", "blades", "hafts", "scopes", "v950.new.sword0.blades"}
MAG = {"magazines", "magazines_gl", "arrows", "batteries", "guards", "v950.new.sword0.guards"}
def kind(p):
    cat = (p.get("plug") or {}).get("plugCategoryIdentifier", "") or ""
    name = p["displayProperties"].get("name", "")
    if cat == "frames": return "perk"
    if cat in BARREL: return "barrel"
    if cat in MAG: return "mag"
    if cat == "intrinsics": return "frame"
    if cat == "origins": return "origin"
    if "masterworks.stat" in cat or name.startswith("Masterworked:"): return "mw"
    return None

W, P = {}, {}
for h, it in items.items():
    if it.get("itemType") != 3: continue
    n = it.get("displayProperties", {}).get("name")
    # an exact sheet name wins ("Drang (Baroque)" has its own row); otherwise Adept, Harrowed, Timelost and Baroque
    # copies count as the base weapon (Joe, 2026-11-11)
    keys = wanted.get(nn(n)) or wanted.get(nn(base_name(n)))
    if not keys: continue
    W[h] = sorted(keys)[0] if len(keys) == 1 else sorted(keys)
    for se in it.get("sockets", {}).get("socketEntries", []):
        hs = [se.get("singleInitialItemHash")] + [x["plugItemHash"] for x in se.get("reusablePlugItems", [])]
        for k in ("randomizedPlugSetHash", "reusablePlugSetHash"):
            if se.get(k): hs += [x["plugItemHash"] for x in plugsets.get(str(se[k]), {}).get("reusablePlugItems", [])]
        for ph in hs:
            p = items.get(str(ph))
            if not p or not p.get("plug") or str(ph) in P: continue
            kd = kind(p)
            if not kd: continue
            name = p["displayProperties"].get("name", "")
            if not name: continue
            if kd == "mw": name = re.sub(r"^Masterworked:\s*", "", name)
            P[str(ph)] = [name, kd]

json.dump({"v": ver, "w": W, "p": P}, open(OUT, "w"), separators=(",", ":"))
found = len({k for v in W.values() for k in ([v] if isinstance(v, str) else v)})
total = len({k for ks in wanted.values() for k in ks})
print(f"Bungie hash maps: {len(W)} weapon item hashes covering {found}/{total} sheet weapons, {len(P)} plugs, "
      f"{round(os.path.getsize(OUT) / 1024)} KB")
if found < 0.9 * total:
    print("STOPPING: fewer than 90 percent of the sheet weapons were found in Bungie's manifest"); sys.exit(1)
