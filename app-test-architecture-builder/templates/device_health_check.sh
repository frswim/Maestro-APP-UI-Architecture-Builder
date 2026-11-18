#!/usr/bin/env bash
# M18 裝置健康檢查（Android 版模板；iOS 用 xcrun devicectl / idevice* 對應改寫）
# 用法：scripts/device_health_check.sh [<serial> ...]   沒給就檢查所有 adb devices
# 輸出：健康的 serial 一行一個到 stdout（給 CI 分配用）；不健康的原因印到 stderr；全部不健康時 exit 1
# 純內網 lab：設 HEALTH_PING_HOST=<內網受測環境主機>（預設 8.8.8.8 在沒有外網時會把所有裝置判成 no network）
# iOS 實機（Xcode 15+）：xcrun devicectl list devices --json-output - 取 connectionProperties / 狀態；
#   電量：xcrun devicectl device info details --device <udid>；舊版用 libimobiledevice 的 ideviceinfo -k BatteryCurrentCapacity
MIN_BATTERY="${MIN_BATTERY:-30}"; MIN_FREE_MB="${MIN_FREE_MB:-1024}"
SERIALS="$*"; [ -z "$SERIALS" ] && SERIALS=$(adb devices | awk 'NR>1 && $2=="device"{print $1}')
OK=0
for s in $SERIALS; do
  bad=""
  [ "$(adb -s "$s" get-state 2>/dev/null)" = "device" ] || bad="offline"
  if [ -z "$bad" ]; then
    lvl=$(adb -s "$s" shell dumpsys battery 2>/dev/null | awk -F': ' '/level/{print $2; exit}' | tr -d '\r')
    [ -n "$lvl" ] && [ "$lvl" -lt "$MIN_BATTERY" ] && bad="battery ${lvl}%"
    free=$(adb -s "$s" shell df /data 2>/dev/null | awk 'NR==2{print int($4/1024)}')
    [ -n "$free" ] && [ "$free" -lt "$MIN_FREE_MB" ] && bad="${bad:+$bad, }free ${free}MB"
    adb -s "$s" shell dumpsys window 2>/dev/null | grep -q 'mDreamingLockscreen=true\|isStatusBarKeyguard=true' && bad="${bad:+$bad, }locked"
    adb -s "$s" shell ping -c 1 -W 3 "${HEALTH_PING_HOST:-8.8.8.8}" >/dev/null 2>&1 || bad="${bad:+$bad, }no network"
  fi
  if [ -n "$bad" ]; then echo "✘ $s: $bad" >&2; else echo "$s"; OK=$((OK+1)); fi
done
[ "$OK" -gt 0 ]
