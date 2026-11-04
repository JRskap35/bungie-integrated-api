"""Download Bungie's Destiny 2 manifest and every part of it the build reads, once, at the start of the build.
Usage: python3 -I bungie_manifest.py CACHE_DIR
Parts already in CACHE_DIR for the current manifest version are kept (the workflow caches the folder between runs);
older versions are deleted. crosscheck.py, bungie_hashes.py, bungie.py and mode_icons.py then read them from CACHE_DIR."""
import json, os, sys, subprocess
CACHE = sys.argv[1]; os.makedirs(CACHE, exist_ok=True)
BASE = "https://www.bungie.net"
PARTS = ["DestinyInventoryItemDefinition", "DestinyPlugSetDefinition", "DestinyEquipableItemSetDefinition",
         "DestinySandboxPerkDefinition", "DestinyDamageTypeDefinition", "DestinyBreakerTypeDefinition",
         "DestinyPresentationNodeDefinition", "DestinyVendorDefinition", "DestinyLoadoutIconDefinition",
         "DestinyRecordDefinition", "DestinyCollectibleDefinition", "DestinySeasonDefinition"]
def curl(url, path):
    subprocess.run(["curl", "-sS", "--fail", "--compressed", "--retry", "3", "--retry-delay", "5", "--max-time", "600", "-o", path, url], check=True)
mpath = os.path.join(CACHE, "manifest.json")
curl(BASE + "/Platform/Destiny2/Manifest/", mpath)
man = json.load(open(mpath))["Response"]; ver = man["version"]; paths = man["jsonWorldComponentContentPaths"]["en"]
got = 0
for k in PARTS:
    p = os.path.join(CACHE, f"{k}-{ver}.json")
    if os.path.exists(p): continue
    for old in os.listdir(CACHE):
        if old.startswith(k + "-"): os.remove(os.path.join(CACHE, old))
    curl(BASE + paths[k], p); got += 1
print(f"Bungie manifest {ver}: {len(PARTS) - got} parts reused, {got} downloaded")
