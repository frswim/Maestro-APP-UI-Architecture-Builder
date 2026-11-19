#!/usr/bin/env bash
# M11：只重跑上次失敗的 flow（讀 .last_run_status.json），依每筆記錄的 target 還原環境變數後重跑
# 用法：./scripts/run_failed.sh [-- <maestro_args>]
#   只重跑某台裝置：ONLY_DEVICE=<id> ./scripts/run_failed.sh
# 只適用 Maestro 版 runner；非 Maestro 用測試框架自己的重跑（Lite 只支援 Maestro）
# 重跑報表另存 ./report_rerun.html；狀態檔合併更新；BLOCKED 不重跑（要先處理環境）
set -e
cd "$(dirname "$0")/.."
[ ! -f .last_run_status.json ] && echo "❌ 找不到 .last_run_status.json，先跑 run_suite.sh" && exit 1
# 每行輸出：BRAND|TARGET_ENV|PLATFORM|LOCALE|FLAGS|FORM_FACTOR|DEVICE|DEVICE_MODEL|TIMEOUT_SCALE|path1 path2 ...
PLAN=$(python3 - <<'PY'
import json, os
d = json.load(open('.last_run_status.json'))
only = os.environ.get('ONLY_DEVICE', '')
groups, missing = {}, []
for k, v in d.items():
    if v.get('passed') or v.get('blocked'):
        continue
    if only and v.get('device') != only:
        continue
    if not v.get('path'):
        missing.append(k); continue
    t = v.get('target') or {}
    key = '|'.join(t.get(x, '') for x in ('BRAND', 'TARGET_ENV', 'PLATFORM', 'LOCALE', 'FLAGS', 'FORM_FACTOR', 'DEVICE', 'DEVICE_MODEL', 'TIMEOUT_SCALE'))
    groups.setdefault(key, set()).add(v['path'])
for key, paths in groups.items():
    print(key + '|' + ' '.join(sorted(paths)))
if missing:
    print('MISSING|' + ','.join(missing))
PY
)
if echo "$PLAN" | grep -q '^MISSING|'; then
  echo "❌ 有失敗的 flow 找不到 yaml 路徑，無法重跑（不是全綠！）：$(echo "$PLAN" | grep '^MISSING|' | cut -d'|' -f2)"; exit 2
fi
[ -z "$PLAN" ] && echo "🎉 上次沒有失敗的 flow，不需重跑" && exit 0
RC=0
while IFS='|' read -r B E P L F FF D DM TS PATHS; do
  [ -z "$B" ] && B=default
  echo "🔁 重跑 [$B/$E/$P/$L/$F/$FF/$D]：$PATHS"
  # shellcheck disable=SC2086
  RERUN=1 TARGET_ENV="$E" PLATFORM="$P" LOCALE="$L" FLAGS="$F" FORM_FACTOR="$FF" DEVICE="$D" DEVICE_MODEL="$DM" TIMEOUT_SCALE="${TS:-1}" \
    ./scripts/run_suite.sh "$B" $PATHS "$@" || RC=1
done <<< "$PLAN"
exit $RC
