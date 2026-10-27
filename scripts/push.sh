#!/usr/bin/env bash
# 提交并推送到 GitHub（默认 origin = https://github.com/ftmg12138/hzz-rpg1.git）
# 用法：GITHUB_BACKUP_TOKEN=... scripts/push.sh "提交说明"
set -euo pipefail
: "${GITHUB_BACKUP_TOKEN:?请先设置 GITHUB_BACKUP_TOKEN}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
unset GIT_TRACE GIT_TRACE_CURL GIT_CURL_VERBOSE GIT_TRACE_PACKET
BRANCH="${BRANCH:-main}"
MSG="${1:-Update $(date -u +%Y-%m-%dT%H:%MZ)}"
EXPECTED="https://github.com/ftmg12138/hzz-rpg1.git"

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$EXPECTED"
fi
url="$(git remote get-url origin)"
case "$url" in
  *@github.com*) echo "origin 地址包含凭据，已拒绝推送" >&2; exit 1;;
esac
if [[ "$url" != "$EXPECTED" && "$url" != "${EXPECTED%.git}" && "$url" != "https://github.com/ftmg12138/hzz-rpg1" ]]; then
  echo "将 origin 从 $url 改为 $EXPECTED"
  git remote set-url origin "$EXPECTED"
fi

git add -A
leak=0
for v in GITHUB_BACKUP_TOKEN CLOUDFLARE_API_TOKEN; do
  val="${!v:-}"
  [ -n "$val" ] && git grep -q --cached -F -e "$val" && { echo "暂存区中发现 $v 的值，已中止" >&2; leak=1; }
done
git grep -q --cached -E -e '(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,})' && { echo "暂存区中发现疑似 GitHub 令牌，已中止" >&2; leak=1; }
[ "$leak" = 0 ] || { git reset -q; exit 1; }
if git diff --cached --quiet; then echo "没有需要提交的改动"; else git commit -q -m "$MSG" && echo "已提交：$(git log -1 --format='%h %s')"; fi
git -c credential.helper= \
    -c credential.helper='!f(){ test "$1" = get || exit 0; echo username=x-access-token; echo "password=$GITHUB_BACKUP_TOKEN"; }; f' \
    push -u origin "HEAD:$BRANCH" 2>&1 | grep -v -i -e token -e password
exit "${PIPESTATUS[0]}"
