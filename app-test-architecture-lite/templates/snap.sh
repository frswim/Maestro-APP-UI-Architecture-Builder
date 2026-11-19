#!/usr/bin/env bash
# M12 抓元素工具：截圖 + 解析畫面上所有元素（text / id / clickable / bounds），寫定位器時最常用
# 用法：
#   ./scripts/snap.sh [device]          Android：adb serial（預設 emulator-5554）
#   PLATFORM=ios ./scripts/snap.sh <udid>   iOS 模擬器：simctl udid（實機截圖改用 Xcode / idevicescreenshot）
# 輸出：snapshots/screen_<時間>.png、screen_<時間>.json（原始 hierarchy）、elements_<時間>.txt（可讀元素表）
# 需要：maestro CLI、python3；Android 另需 adb
set -e
cd "$(dirname "$0")/.."

if [ -z "${ANDROID_HOME:-}" ]; then
  case "$(uname -s)" in Darwin) ANDROID_HOME="$HOME/Library/Android/sdk" ;; *) ANDROID_HOME="$HOME/Android/Sdk" ;; esac
fi
export PATH="${JAVA_HOME:+$JAVA_HOME/bin:}$ANDROID_HOME/platform-tools:$HOME/.maestro/bin:$PATH"

PLATFORM="${PLATFORM:-android}"
DEVICE="${1:-emulator-5554}"

mkdir -p snapshots
TS=$(date +%Y%m%d_%H%M%S)
PNG="snapshots/screen_${TS}.png"
JSON="snapshots/screen_${TS}.json"
TXT="snapshots/elements_${TS}.txt"

if [ "$PLATFORM" = "ios" ]; then
  xcrun simctl io "$DEVICE" screenshot "$PNG" >/dev/null 2>&1 || echo "⚠️ 截圖失敗（實機請改用 Xcode 或 idevicescreenshot），繼續抓 hierarchy"
else
  adb -s "$DEVICE" exec-out screencap -p > "$PNG"
fi
maestro --device "$DEVICE" hierarchy > "$JSON" 2>/dev/null

python3 - "$JSON" > "$TXT" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    tree = json.load(f)
rows = []
def walk(node):
    a = node.get("attributes", {}) or {}
    text = (a.get("text") or "").strip()
    rid = (a.get("resource-id") or a.get("identifier") or "").strip()
    hint = (a.get("hintText") or "").strip()
    acc = (a.get("accessibilityText") or a.get("label") or "").strip()
    clickable = a.get("clickable") == "true"
    bounds = a.get("bounds", "")
    if clickable or text or rid or hint or acc:
        rows.append((text or hint or acc, rid, clickable, bounds))
    for c in node.get("children", []) or []:
        walk(c)
walk(tree)
print(f"{'idx':<5}{'click':<7}{'text / label':<32}{'id':<45}bounds")
print("-" * 130)
for i, (t, rid, click, b) in enumerate(rows):
    print(f"{i:<5}{'✓' if click else '':<7}{t[:30]:<32}{rid.split('/')[-1][:43]:<45}{b}")
PY

echo "✅ snapshot (platform=$PLATFORM, device=$DEVICE)"
echo "   screenshot: $PNG"
echo "   elements:   $TXT"
