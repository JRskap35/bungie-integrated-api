#!/usr/bin/env bash
# Rebuild Bungie-Integrated-API from TheAegisRelic's live sheet (PvE), Pride Eternal's PvP sheet and Bungie's Destiny 2 API into site/index.html
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build site
python3 -I kit/fetch.py build/new.pdf build/full.pdf
python3 -I kit/extract.py build/new.pdf build/raw.json
python3 -I kit/shape.py build/raw.json build/data.json build/icons.json
python3 -I kit/extract_icons.py build/full.pdf build/trait_icons.json
python3 -I kit/enrich.py build/data.json build/trait_icons.json build/data_e.json build/ticons.json
python3 -I kit/check.py build/data_e.json build/icons.json
# PvP mode: Pride Eternal / Finnald's Destiny 2 PvP Spreadsheet (legendary + exotic weapons, Shopping List, set bonuses)
python3 -I kit/pvp_fetch.py build/pvp_raw.json
python3 -I kit/pvp.py build/data_e.json build/pvp_raw.json build/data_ep.json
# PvP cross check: Pride's sheet is the baseline; Bungie's roll pools, Hugo's WeaponStat Chart (PvP TTK) and the Destiny Data
# Compendium win where they disagree. Fixes the lists, then audits them; stops the deploy if a rule still breaks
python3 -I kit/hugo_fetch.py build/hugo.json assets/hugo_cache.json
python3 -I kit/crosscheck.py build/data_ep.json build/hugo.json "${BUNGIE_CACHE:-build/bungie_cache}" build/data_epx.json build/crosscheck.txt
{ echo '## PvP cross check'; echo '```'; cat build/crosscheck.txt; echo '```'; } >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true
# PvP tiers and perks from what players actually use: Bungie's match reports (Trials and the rest of PvP, last four closed
# weeks) and the public loadouts of those players, plus DIM's community wish list for creators' PvP picks.
# The weeks already counted come back from the published site (pvp_usage.json), so each build only samples the new week
python3 -I kit/bungie_hashes.py build/data_epx.json "${BUNGIE_CACHE:-build/bungie_cache}" build/hashes_pvp.json
if ! curl -sSfL --compressed --retry 3 --max-time 300 -o build/wishlist.txt https://raw.githubusercontent.com/48klocs/dim-wish-list-sources/master/voltron.txt; then
  echo "WARNING: DIM wish list not reachable; ranking without creators' picks"; : > build/wishlist.txt
fi
python3 -I kit/pvp_usage.py build/hashes_pvp.json bungie/config.json "${PVP_STORE_URL:-https://endgameapi.pages.dev/pvp_usage.json}" assets/pvp_usage_seed.json build/pvp_use.json build/pvp_perks.json site/pvp_usage.json
python3 -I kit/pvp_rank.py build/data_epx.json build/data_ep.json build/pvp_use.json build/pvp_perks.json build/wishlist.txt build/hashes_pvp.json build/data_epr.json build/pvp_rank.txt
{ echo '## PvP ranking from players'; echo '```'; cat build/pvp_rank.txt; echo '```'; } >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true
# swap in Bungie's official icons (weapons, frames, perks, barrels, mags, masterwork, origin traits, energy, stun, armor sets)
python3 -I kit/bungie.py build/data_epr.json build/icons.json build/ticons.json assets/elements.json build/bungie "${BUNGIE_CACHE:-build/bungie_cache}"
cat build/bungie/report.txt >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true
# Bungie-Integrated-API: report card and location icons, then the hash maps that read a signed in Bungie account
python3 -I kit/mode_icons.py build/bungie/icons.json build/icons_bia.json "${BUNGIE_CACHE:-build/bungie_cache}"
python3 -I kit/bungie_hashes.py build/bungie/data.json "${BUNGIE_CACHE:-build/bungie_cache}" build/hashes.json
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
# what changed since the last published version (shown on the workflow run page)
if [ -n "${SITE_URL:-}" ] && curl -sSfL --max-time 60 "$SITE_URL" -o build/prev.html; then
  { echo '## What changed on the sheet'; echo '```'; python3 -I kit/diff.py build/prev.html build/data.json; echo '```'; } >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true
fi
