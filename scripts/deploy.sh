#!/usr/bin/env bash
# 部署到 Cloudflare Pages（项目 xyzhzz-rpg → https://rpg.xyzhzz.com）
set -euo pipefail
: "${CLOUDFLARE_API_TOKEN:?请先设置 CLOUDFLARE_API_TOKEN}"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPTS")"
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-f57ee3b3ec6a868c05a73c1b2b54d531}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT/.cache}"
mkdir -p "$XDG_CACHE_HOME"
PROJECT="${PROJECT:-xyzhzz-rpg}"
DIST="${DIST:-$ROOT/public}"

if [[ "${SKIP_PARSE:-0}" != "1" ]]; then
  python3 "$ROOT/tools/parse-script.py"
  python3 "$ROOT/tools/synthesize-extra.py"
fi

if [[ ! -x "$ROOT/node_modules/.bin/wrangler" ]]; then
  (cd "$ROOT" && npm install --no-audit --no-fund wrangler@4.30.0 >/dev/null)
fi
WRANGLER="$ROOT/node_modules/.bin/wrangler"

echo "部署 $DIST → $PROJECT …"
"$WRANGLER" pages deploy "$DIST" --project-name "$PROJECT" --branch main --commit-dirty=true 2>&1 | grep -v -i token
echo "检查线上…"
sleep 2
curl -s -o /dev/null -w "xyzhzz-rpg.pages.dev -> HTTP %{http_code}\n" https://xyzhzz-rpg.pages.dev/ || true
curl -s -o /dev/null -w "rpg.xyzhzz.com -> HTTP %{http_code}\n" https://rpg.xyzhzz.com/ || true
