#!/usr/bin/env bash
# Deploy the progress sync worker to Cloudflare and write its address to build/vault_api.txt for the site build.
# Needs CLOUDFLARE_API_TOKEN (permissions: Workers Scripts Edit, Workers KV Storage Edit, Account Settings Read)
# and CLOUDFLARE_ACCOUNT_ID, both saved as GitHub repository secrets. Safe to run every build: it reuses the namespace.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CLOUDFLARE_API_TOKEN:?}" "${CLOUDFLARE_ACCOUNT_ID:?}"
API="https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID"
H=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json")
NS_TITLE="bia-progress"
id=$(curl -sS "${H[@]}" "$API/storage/kv/namespaces?per_page=100" | jq -r --arg t "$NS_TITLE" '.result[]? | select(.title==$t) | .id' | head -1)
if [ -z "$id" ]; then
  id=$(curl -sS "${H[@]}" -X POST "$API/storage/kv/namespaces" -d "{\"title\":\"$NS_TITLE\"}" | jq -r '.result.id // empty')
  echo "Created KV namespace $NS_TITLE"
fi
[ -n "$id" ] || { echo "Could not find or create the KV namespace (check the token's permissions)"; exit 1; }
key=$(jq -r '.apiKey' bungie/config.json)
origins=$(jq -r '(.siteOrigins // ["https://jrskap35.github.io"]) | join(",")' bungie/config.json)
borigin=$(jq -r '.bungieOrigin // "https://jrskap35.github.io"' bungie/config.json)
mkdir -p build/cloud
sed -e "s/__KV_ID__/$id/" -e "s/__BUNGIE_API_KEY__/$key/" -e "s#__SITE_ORIGINS__#$origins#" -e "s#__BUNGIE_ORIGIN__#$borigin#" cloud/wrangler.toml > build/cloud/wrangler.toml
cp cloud/worker.js build/cloud/worker.js
(cd build/cloud && npx --yes wrangler@4 deploy)
sub=$(curl -sS "${H[@]}" "$API/workers/subdomain" | jq -r '.result.subdomain // empty')
[ -n "$sub" ] || { echo "No workers.dev subdomain yet: open Workers & Pages in the Cloudflare dashboard once to pick one"; exit 1; }
echo "https://bia-progress.$sub.workers.dev" > build/vault_api.txt
echo "Progress sync: $(cat build/vault_api.txt)"
