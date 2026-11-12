#!/usr/bin/env bash
# Rebuild Endgame API from TheAegisRelic's live sheet (PvE), Pride Eternal's PvP sheet and Bungie's Destiny 2 API into site/
# Straight line (2026-11-04): download every source first, then build offline, then sample Bungie's match reports
# (the only slow step) once nothing else can stop the build, then put the page together.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build site
CACHE="${BUNGIE_CACHE:-build/bungie_cache}"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"
# step tracking for the update report (kit/status_report.py): each step is marked ok when the next starts, and the
# step running when the script stops is marked failed. The log carries "===== step: id =====" lines between steps.
STEPS=build/steps.tsv; : > "$STEPS"; CUR=""
step(){ [ -n "$CUR" ] && printf '%s\tok\n' "$CUR" >> "$STEPS"; CUR="$1"; echo; echo "===== step: $1 ====="; }
trap 'rc=$?; [ -n "$CUR" ] && printf "%s\t%s\n" "$CUR" "$([ $rc -eq 0 ] && echo ok || echo failed)" >> "$STEPS"' EXIT

# ---------- 1. Every source, downloaded up front ----------
step sources
# A source that is down stops the build (or falls back to a saved copy) here, before any work is done.
python3 -I kit/fetch.py build/new.pdf build/full.pdf                    # TheAegisRelic's Endgame Analysis
python3 -I kit/pvp_fetch.py build/pvp_raw.json                          # Pride Eternal / Finnald's PvP sheet
python3 -I kit/hugo_fetch.py build/hugo.json assets/hugo_cache.json     # Hugo's WeaponStat Chart + Destiny Data Compendium (saved copy if down)
python3 -I kit/bungie_manifest.py "$CACHE"                              # Bungie's manifest, every part the build reads
export BUNGIE_MANIFEST_READY=1
if ! curl -sSfL --compressed --retry 3 --max-time 300 -o build/wishlist.txt https://raw.githubusercontent.com/48klocs/dim-wish-list-sources/master/voltron.txt; then
  echo "WARNING: DIM wish list not reachable; ranking without creators' picks"; : > build/wishlist.txt
fi
PVP_STORE_URL="${PVP_STORE_URL:-https://endgameapi.pages.dev/pvp_usage.json}"
rm -f build/pvp_store_prev.json build/prev.html
curl -sSfL --max-time 60 "$PVP_STORE_URL" -o build/pvp_store_prev.json || echo "No published PvP store yet; the repo copy is used"
if [ -n "${SITE_URL:-}" ]; then curl -sSfL --max-time 60 "$SITE_URL" -o build/prev.html || rm -f build/prev.html; fi   # for "what changed"

# ---------- 2. Aegis's sheet (PvE): read, then check ----------
step aegis
python3 -I kit/extract.py build/new.pdf build/raw.json
python3 -I kit/shape.py build/raw.json build/data.json build/icons.json
python3 -I kit/extract_icons.py build/full.pdf build/trait_icons.json
python3 -I kit/enrich.py build/data.json build/trait_icons.json build/data_e.json build/ticons.json
python3 -I kit/check.py build/data_e.json build/icons.json             # stops the build if the sheet changed shape

# ---------- 3. Pride's sheet (PvP), then the cross check ----------
step pride
python3 -I kit/pvp.py build/data_e.json build/pvp_raw.json build/data_ep.json
# Bungie's roll pools, Hugo's TTK data and the Compendium fix Pride's lists (spellings, columns, perks that can't roll,
# TTK numbers), then audit them; stops the build if a rule still breaks
python3 -I kit/crosscheck.py build/data_ep.json build/hugo.json "$CACHE" build/data_epx.json build/crosscheck.txt
{ echo '## PvP cross check'; echo '```'; cat build/crosscheck.txt; echo '```'; } >> "$SUMMARY" || true
# PvP weapons take Aegis's section, ammo type, energy, frame, season and source (Aegis's sheet is the basis)
python3 -I kit/align.py build/data_epx.json build/data_epx.json build/align.txt

# ---------- 4. Bungie item and perk hashes for every weapon on both sheets (built once) ----------
step hashes
python3 -I kit/bungie_hashes.py build/data_epx.json "$CACHE" build/hashes.json

# ---------- 5. PvP from players: Bungie's match reports and loadouts, then tiers and perks ----------
step pvp
python3 -I kit/pvp_usage.py build/hashes.json bungie/config.json build/pvp_store_prev.json assets/pvp_usage_seed.json build/pvp_use.json build/pvp_perks.json site/pvp_usage.json
python3 -I kit/pvp_rank.py build/data_epx.json build/data_ep.json build/pvp_use.json build/pvp_perks.json build/wishlist.txt build/hashes.json build/data_epr.json build/pvp_rank.txt
{ echo '## PvP ranking from players'; echo '```'; cat build/pvp_rank.txt; echo '```'; } >> "$SUMMARY" || true
# Joe's manual edits from the perk editor (assets/perk_overrides.json): they win over the sheets and the player data
python3 -I kit/overrides.py build/data_epr.json assets/perk_overrides.json build/data_epo.json build/perk_sheet.json | tee -a "$SUMMARY"

# ---------- 6. Bungie's official icons and the account sync maps ----------
step icons
python3 -I kit/bungie.py build/data_epo.json build/icons.json build/ticons.json assets/elements.json build/bungie "$CACHE"
cat build/bungie/report.txt >> "$SUMMARY" || true
python3 -I kit/mode_icons.py build/bungie/icons.json build/icons_bia.json "$CACHE"
# the hash map from step 4 fits as long as the icon step kept every weapon's name; otherwise it is rebuilt
python3 -I - build/data_epx.json build/bungie/data.json <<'PY' || python3 -I kit/bungie_hashes.py build/bungie/data.json "$CACHE" build/hashes.json
import json, re, sys
nn = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("’", "'"))
keys = lambda p: {w["arch"] + "|" + nn(w["name"]) for d in [json.load(open(p))] for w in d["weapons"] + (d.get("pvp") or {}).get("weapons", [])}
same = keys(sys.argv[1]) == keys(sys.argv[2])
print("Bungie hash maps: reused from step 4" if same else "Weapon names changed in the icon step; rebuilding the hash maps")
sys.exit(0 if same else 1)
PY

# ---------- 7. The page ----------
step page
# progress sync: cloud/deploy.sh (run by the workflow when the Cloudflare secrets are set) leaves the worker's address here
python3 -I - build/bungie_config.json <<'PY'
import json, os, sys
c = json.load(open("bungie/config.json"))
if os.path.exists("build/vault_api.txt"):
    c["vaultApi"] = open("build/vault_api.txt").read().strip()
    print("Progress sync on:", c["vaultApi"])
else:
    print("Progress sync off (no Cloudflare secrets): hand-entered progress stays in each browser")
json.dump(c, open(sys.argv[1], "w"))
PY
python3 -I kit/assemble.py src/template.html build/bungie/data.json build/icons_bia.json site/index.html assets/stat_icons.json build/bungie/ticons.json build/bungie/elements.json assets/brand.json build/bungie_config.json build/hashes.json
# what changed since the last published version (shown on the workflow run page): Aegis's sheet, then PvP
if [ -s build/prev.html ]; then
  python3 -I kit/diff.py build/prev.html build/data.json build/bungie/data.json > build/changes.txt || echo "WARNING: the change list could not be made"
fi

# ---------- 8. Joe's perk editor: a Claude page built from the same data (kept with the run, never put on the website) ----------
step editor
mkdir -p build/editor
python3 -I kit/perk_pools.py build/bungie/data.json build/bungie/ticons.json "$CACHE" assets/perk_overrides.json build/perk_sheet.json assets/editor_config.json build/editor.json build/editor_ticons.json
python3 -I kit/assemble.py --editor build/editor.json src/template.html build/bungie/data.json build/icons_bia.json build/editor/perk-editor.html assets/stat_icons.json build/editor_ticons.json build/bungie/elements.json assets/brand.json
