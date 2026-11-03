"""Add the PvE and PvP report card icons to a bungie.py icons.json (Bungie-Integrated-API only).
Usage: python3 -I mode_icons.py icons.json OUT_icons.json CACHE_DIR
Both come from Bungie's Destiny 2 API, Collections presentation nodes, as a matching pair of shield badges:
  PvE  "Vanguard" node 547854723   PvP  "Crucible" node 927333320
They are stored under icons.json "n" as "mpve" and "mpvp" and drawn as masks, so the page colors them green, yellow or grey.
Also adds, recolored from Bungie's light grey into the gold the Weapons tab icon shows on screen (Joe's picks, 2026-11-01):
  "post"  Kadi 55-30 the Postmaster's vendor icon (the diamond), for the New Drops tab
  "vloc"  the Vault vendor's icon (the diamond), for the location tiles and the Send to menu
The gold is measured from icons.json "n" "weapons" each build, so the three always match.
The icon path is read from the manifest each build, so new art from Bungie comes through on its own."""
import json, sys, os, io, base64, subprocess
import numpy as np
from PIL import Image

ICONS, OUT, CACHE = sys.argv[1:4]
NODES = {"mpve": "547854723", "mpvp": "927333320"}
GILD = [("post", "3161908920"), ("vloc", "1037843411")]   # vendor icons: Kadi 55-30 (Postmaster), Vault
BASE = "https://www.bungie.net"

def curl(url, path):
    subprocess.run(["curl", "-sS", "--fail", "--retry", "3", "--max-time", "120", "-o", path, url], check=True)

man = json.load(open(os.path.join(CACHE, "manifest.json")))["Response"]
ver = man["version"]
p = os.path.join(CACHE, f"DestinyPresentationNodeDefinition-{ver}.json")
if not os.path.exists(p): curl(BASE + man["jsonWorldComponentContentPaths"]["en"]["DestinyPresentationNodeDefinition"], p)
nodes = json.load(open(p))
icons = json.load(open(ICONS))
os.makedirs(os.path.join(CACHE, "img"), exist_ok=True)
for key, h in NODES.items():
    path = nodes[h]["displayProperties"]["icon"]
    f = os.path.join(CACHE, "img", os.path.basename(path))
    if not os.path.exists(f): curl(BASE + path, f)
    icons["n"][key] = "data:image/png;base64," + base64.b64encode(open(f, "rb").read()).decode()
    print(f"{key}: {nodes[h]['displayProperties']['name']} {path}")
# the Weapons tab icon's gold as it shows on the page's dark background
BG = np.array([18, 20, 23.])
w = np.array(Image.open(io.BytesIO(base64.b64decode(icons["n"]["weapons"].split(",")[1]))).convert("RGBA")).reshape(-1, 4).astype(float)
m = (w[:, 3] > 60) & ((w[:, :3].max(1) - w[:, :3].min(1)) > 25)
shown = np.median(w[m][:, :3] * (w[m][:, 3:] / 255) + BG * (1 - w[m][:, 3:] / 255), 0) if m.any() else np.array([142, 127, 61.])
HI = 0.75                                            # the vendor icons' solid lines sit near this opacity
GOLDC = np.clip((shown - BG * (1 - HI)) / HI, 0, 255)
p = os.path.join(CACHE, f"DestinyVendorDefinition-{ver}.json")
if not os.path.exists(p): curl(BASE + man["jsonWorldComponentContentPaths"]["en"]["DestinyVendorDefinition"], p)
vendors = json.load(open(p))
for key, h in GILD:
    dp = vendors[h]["displayProperties"]
    f = os.path.join(CACHE, "img", os.path.basename(dp["icon"]))
    if not os.path.exists(f): curl(BASE + dp["icon"], f)
    a = np.array(Image.open(f).convert("RGBA")).astype(float)
    lum = np.clip(a[:, :, :3].mean(2) / 224.0, 0, 1.1)  # Bungie draws these in one light grey; keep any shading
    for i in range(3): a[:, :, i] = np.clip(GOLDC[i] * lum, 0, 255)
    a[:, :, 3] = np.clip(a[:, :, 3] * 1.25, 0, 255)       # thin lines read dimmer at tab size; same lift the Armor helmet got
    buf = io.BytesIO(); Image.fromarray(a.astype("uint8"), "RGBA").save(buf, "PNG")
    icons["n"][key] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    print(f"{key}: {dp['name']} {dp['icon']} in gold {GOLDC.round().astype(int).tolist()}")
json.dump(icons, open(OUT, "w"))
