#!/usr/bin/env bash
# Publish the built site (site/) to Cloudflare Pages as the project "endgameapi", so it lives at https://endgameapi.pages.dev
# (Cloudflare adds a few letters to the name if that one is taken). Uses the same two secrets as deploy.sh; the API token
# also needs Account > Cloudflare Pages > Edit. Writes the address to build/pages_url.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CLOUDFLARE_API_TOKEN:?}" "${CLOUDFLARE_ACCOUNT_ID:?}"
PROJECT="${PAGES_PROJECT:-endgameapi}"
API="https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/pages/projects"
H=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json")
got=$(curl -sS "${H[@]}" "$API/$PROJECT")
if [ "$(echo "$got" | jq -r '.success')" != "true" ]; then
  made=$(curl -sS "${H[@]}" -X POST "$API" -d "{\"name\":\"$PROJECT\",\"production_branch\":\"main\"}")
  if [ "$(echo "$made" | jq -r '.success')" != "true" ]; then
    echo "Could not create the Pages project: $(echo "$made" | jq -c '.errors')"
    echo "The API token needs Account > Cloudflare Pages > Edit (My Profile > API Tokens > edit the token)."
    exit 1
  fi
  echo "Created Pages project $PROJECT"
  got=$(curl -sS "${H[@]}" "$API/$PROJECT")
fi
npx --yes wrangler@4 pages deploy site --project-name "$PROJECT" --branch main --commit-dirty=true
sub=$(echo "$got" | jq -r '.result.subdomain // empty')
echo "https://${sub:-$PROJECT.pages.dev}" > build/pages_url.txt
echo "Site: $(cat build/pages_url.txt)"
{ echo "## Site"; echo "Published to $(cat build/pages_url.txt)"; } >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true
