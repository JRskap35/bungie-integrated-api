#!/usr/bin/env bash
# The site moved to Cloudflare Pages (endgameapi.pages.dev). When that publish worked, GitHub Pages serves only a small page
# that forwards the old address (jrskap35.github.io/bungie-integrated-api) there; if it didn't, GitHub keeps the full site.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf build/ghsite && mkdir -p build/ghsite
if [ -s build/pages_url.txt ]; then
  url="$(cat build/pages_url.txt)/"
  cat > build/ghsite/index.html <<HTML
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Endgame API has moved</title>
<link rel="canonical" href="$url"><meta http-equiv="refresh" content="0; url=$url">
<script>location.replace("$url" + location.hash);</script>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0c0e10;color:#e9e4d6;font:16px/1.5 system-ui,sans-serif;text-align:center}
a{color:#c9b277}</style></head>
<body><p>Endgame API has moved to <a href="$url">$url</a></p></body></html>
HTML
  cp build/ghsite/index.html build/ghsite/404.html
  echo "GitHub Pages forwards to $url"
else
  cp -r site/. build/ghsite/
  echo "Cloudflare Pages publish didn't run; GitHub Pages keeps the full site"
fi
