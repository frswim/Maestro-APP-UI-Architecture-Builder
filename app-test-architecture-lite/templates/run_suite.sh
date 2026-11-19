#!/usr/bin/env bash
# =============================================================================
# 單一執行入口（模組 M1，本機 / 自架裝置模式）—— 模板（Maestro 版）
#
# 用法：
#   ./scripts/run_suite.sh <brand> <flow_or_folder>... [-- <maestro_args>]
#   單一 App 沒有品牌概念 → brand 用 default（config/brands/default.yaml）
#
# 目標維度（選填環境變數，沒給就不套用）：
#   多租戶（同 App、依城市 / 地區 / 客戶切換）：用 brand 參數當 tenant（config/brands/<tenant>.yaml + test_data/<tenant>/），
#   租戶專屬的可預期值（價格表、啟用服務）放 config/brands/<tenant>.yaml 或 test_data。
#   TARGET_ENV=staging   疊加 config/env/<env>.yaml（同 key 覆寫品牌設定）
#   PLATFORM=ios         覆寫品牌檔的 device_type（同一品牌跑雙平台）
#   LOCALE=en            傳 -e locale=<locale> 給 flow；test_data 可放 <brand>/<locale>/ 子目錄
#   DEVICE=<udid>        覆寫品牌檔的 device
#   FLAGS=<profile>      （進階，完整版有完整做法）feature flag 組合：config/flags/<profile>.json，以 -e flags_profile=<profile> 傳給 flow；
#                        實際套用方式（測試用戶 targeting / launch argument / SDK 測試資料源）依 ADR
#   TIMEOUT_SCALE=2      低階裝置 / 慢網路時放大所有 helper 等待上限（依裝置效能 profile 設定）
#   FORM_FACTOR=tablet   phone（預設）/ tablet：傳 -e form_factor=...，定位器 override 層 selectors/<platform>/<brand>/<form_factor>/
#   MAESTRO_TIMEOUT_MIN  watchdog 分鐘數（預設 60，0 = 關閉）
#   NOTIFY_WEBHOOK_URL   有設就呼叫 scripts/notify.sh 送摘要（URL 放 CI secret，不進版控）
#   NOTIFY_FORMAT        slack（預設）| teams | line | email；email 用 SMTP_HOST / SMTP_PORT / MAIL_FROM / MAIL_TO / MAIL_ALLOWED_DOMAINS，不需 webhook
#   NOTIFY_AUTH_TOKEN / NOTIFY_TO / NOTIFY_ALLOWED_HOSTS  見 scripts/notify.sh
#   REPORT_INLINE_ASSETS=1  報表不連外（內嵌 config/vendor/ 的 bootstrap）
#   APP_BUILD            受測 App 版本（寫進歷史、證據、TCM 回寫）
#   RERUN=1              由 run_failed.sh 設定：報表存 ./report_rerun.html，不覆蓋整輪報表
#   REPORT_LANG          報表語言 zh-Hant / ja / en / ko（未知語言退回 en）
#
# 裝置池並行：同一個 checkout 內，「相同 brand/platform/locale」可以多台裝置同時跑（各自 DEVICE=...），
#   每台有自己的輸出目錄與裝置鎖；「不同 target」會互搶 active symlink → 用不同 checkout / git worktree，
#   或由 CI 把每個 target 分到不同 agent。（裝置池 / 結果合併：完整版 M18）
#
# 範例：
#   ./scripts/run_suite.sh brand_a flows/ -- --include-tags smoke
#   PLATFORM=ios LOCALE=en TARGET_ENV=staging ./scripts/run_suite.sh default flows/checkout/
#   （視覺回歸 UI Diff 屬完整版；Lite 沒有 ui_diff_check.py 時旗標會被略過）
#
# `--` 之前是 runner 參數；之後原封不動傳給 maestro test。少打 `--` 會把 -e 當成 flow 路徑。
#
# 雲端裝置農場（BrowserStack / Sauce / Firebase…）不能用這支的「本機執行」段：
#   （完整版 M1「雲端模式」）—— 改成 打包(實體化 active) → 上傳 → 輪詢 → 下載結果 → 同樣的報表段。
# 只適用 Maestro。換工具不是「改兩段」：入口、等待 helper、結果格式都要換（其他工具的寫法在完整版）。
# Windows：Git Bash 沒有 pgrep/pkill（watchdog 失效）、symlink 會變複製 → 建議在 WSL2 執行，或改寫成 Python runner。
# 需要：bash 3.2+、Python 3.9+（報表腳本）。
# =============================================================================
set -e
set +H   # 關 history expansion，避免密碼含 !! 被吃掉
cd "$(dirname "$0")/.."

# ---- 依執行機調整（皆可由環境變數覆寫）----
if [ -z "${ANDROID_HOME:-}" ]; then
  case "$(uname -s)" in Darwin) ANDROID_HOME="$HOME/Library/Android/sdk" ;; *) ANDROID_HOME="$HOME/Android/Sdk" ;; esac
fi
export ANDROID_HOME
[ -z "${JAVA_HOME:-}" ] && [ -d "/Applications/Android Studio.app/Contents/jbr/Contents/Home" ] && \
  export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export PATH="${JAVA_HOME:+$JAVA_HOME/bin:}$ANDROID_HOME/platform-tools:$HOME/.maestro/bin:$PATH"

BRAND="${1:?Missing brand (single-app projects use: default)}"; shift
BRAND_CFG="config/brands/${BRAND}.yaml"
[ ! -f "$BRAND_CFG" ] && echo "❌ brand config not found: $BRAND_CFG（從 ${BRAND_CFG}.example 複製並填值）" && exit 1
ENV_CFG=""
if [ -n "${TARGET_ENV:-}" ]; then
  ENV_CFG="config/env/${TARGET_ENV}.yaml"
  [ ! -f "$ENV_CFG" ] && echo "❌ env config not found: $ENV_CFG" && exit 1
fi

# ---- 1. 拆參數 ----
FLOW_TARGETS=(); EXTRA=(); SEP=0
for a in "$@"; do
  if [ "$a" = "--" ]; then SEP=1; continue; fi
  if [ $SEP -eq 0 ]; then FLOW_TARGETS+=("$a"); else EXTRA+=("$a"); fi
done
[ ${#FLOW_TARGETS[@]} -eq 0 ] && echo "❌ 未指定 flow 檔或資料夾" && exit 1
for t in "${FLOW_TARGETS[@]}"; do
  case "$t" in -*) echo "❌ '$t' 看起來是參數不是 flow 路徑：maestro 參數請放在 -- 之後" && exit 1 ;; esac
done

UI_DIFF="false"; UI_BASELINE="false"; USER_OUT=""; FILTERED=(); SKIP=0
for i in "${!EXTRA[@]}"; do
  [ $SKIP -eq 1 ] && SKIP=0 && continue
  a="${EXTRA[$i]}"
  case "$a" in
    -e) n="${EXTRA[$((i+1))]}"
        case "$n" in ui_diff_enabled=*) UI_DIFF="${n#*=}";; ui_diff_capture_baseline=*) UI_BASELINE="${n#*=}";; esac
        FILTERED+=("$a" "$n"); SKIP=1 ;;
    --test-output-dir=*) USER_OUT="${a#*=}" ;;
    *) FILTERED+=("$a") ;;
  esac
done
EXTRA=("${FILTERED[@]}")

# ---- 2. 設定 → -e（只支援扁平 key: value；env 檔後讀 = 覆寫）----
ENV_ARGS=()
set_env() {  # set_env <key> <val>：同 key 後設定者覆寫前者（不重複傳 -e）
  local out=() i
  for ((i=0; i<${#ENV_ARGS[@]}; i+=2)); do
    case "${ENV_ARGS[$((i+1))]}" in "$1="*) ;; *) out+=("${ENV_ARGS[$i]}" "${ENV_ARGS[$((i+1))]}") ;; esac
  done
  ENV_ARGS=(${out[@]+"${out[@]}"} -e "$1=$2")
}
read_flat() {
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue; [ "${line:0:1}" = "#" ] && continue
    key=$(echo "$line" | sed -E 's/^([a-zA-Z_][a-zA-Z_0-9]*):[[:space:]]*.*/\1/')
    [ -z "$key" ] || [ "$key" = "$line" ] && continue
    val=$(echo "$line" | sed -E 's/^[a-zA-Z_][a-zA-Z_0-9]*:[[:space:]]*"?([^"]*)"?[[:space:]]*(#.*)?$/\1/')
    set_env "$key" "$val"
  done < "$1"
}
cfg_get() {  # cfg_get <key>：env 檔優先，其次品牌檔
  local v=""
  [ -n "$ENV_CFG" ] && v=$(grep -E "^$1:" "$ENV_CFG" | head -1 | sed -E "s/^$1:[[:space:]]*\"?([^\"#]*)\"?.*/\1/" | xargs)
  [ -z "$v" ] && v=$(grep -E "^$1:" "$BRAND_CFG" | head -1 | sed -E "s/^$1:[[:space:]]*\"?([^\"#]*)\"?.*/\1/" | xargs)
  echo "$v"
}
read_flat "$BRAND_CFG"
[ -n "$ENV_CFG" ] && read_flat "$ENV_CFG"     # env 檔同 key 覆寫品牌檔
DEVICE="${DEVICE:-$(cfg_get device)}"; DEVICE="${DEVICE:-emulator-5554}"
DEVICE_TYPE="${PLATFORM:-$(cfg_get device_type)}"
[ -z "$DEVICE_TYPE" ] && echo "❌ device_type 未設定（品牌檔加 device_type: android|ios，或 PLATFORM=...）" && exit 1
set_env device_type "$DEVICE_TYPE"
[ "$UI_DIFF" != "true" ] && set_env ui_diff_enabled false   # 讓 flow 永遠有這個變數
[ -n "${LOCALE:-}" ] && set_env locale "$LOCALE"
if [ -n "${FLAGS:-}" ]; then
  [ ! -f "config/flags/${FLAGS}.json" ] && echo "❌ flag profile not found: config/flags/${FLAGS}.json" && exit 1
  set_env flags_profile "$FLAGS"
fi
FORM_FACTOR="${FORM_FACTOR:-phone}"; set_env form_factor "$FORM_FACTOR"
set_env timeout_scale "${TIMEOUT_SCALE:-1}"   # 低階裝置設 1.5～2：helper 的等待上限等比放大

# ---- 3. 切換 active（測試資料 / 定位器）----
TD_SRC="$BRAND"; [ -n "${LOCALE:-}" ] && [ -d "config/test_data/$BRAND/$LOCALE" ] && TD_SRC="$BRAND/$LOCALE"
[ ! -d "config/test_data/$TD_SRC" ] && echo "❌ 尚未建立測試資料：config/test_data/$TD_SRC/" && exit 1
SEL_SRC="$DEVICE_TYPE/$BRAND"
# 白牌很多、多數品牌定位器相同時：建 selectors/<platform>/_base/，品牌目錄只放差異（主 flow 先載 _base 再載 active 覆寫）
#   品牌目錄不存在 → active 指向 _base
if [ ! -d "config/selectors/$SEL_SRC" ] && [ -d "config/selectors/$DEVICE_TYPE/_base" ]; then
  echo "ℹ️  config/selectors/$SEL_SRC 不存在，使用 $DEVICE_TYPE/_base"; SEL_SRC="$DEVICE_TYPE/_base"
fi
[ ! -d "config/selectors/$SEL_SRC" ] && echo "❌ Selector directory not found: config/selectors/$SEL_SRC" && exit 1
for pair in "config/test_data:$TD_SRC" "config/selectors:$SEL_SRC"; do
  base="${pair%%:*}"; src="${pair#*:}"
  [ -d "$base/active" ] && [ ! -L "$base/active" ] && rm -rf "$base/active"
  ln -sfn "$src" "$base/active"
  # 不支援 symlink（Windows / 部分 CI / 雲端上傳打包）→ 改成：rm -rf "$base/active" && cp -R "$base/$src" "$base/active"
done
# 定位器若採「shared + 平台 override」：主 flow 先 runScript selectors/shared/<page>.js 再 runScript selectors/active/<page>.js
# 平板 override：selectors/<platform>/<brand>/tablet/<page>.js（主 flow 用 when: ${form_factor == "tablet"} 多載一次）

# 視覺基線 key：依實際會讓畫面不同的維度組合（品牌 × 平台 × 語系），避免互相覆蓋
BASELINE_KEY="$BRAND/$DEVICE_TYPE/$FORM_FACTOR${LOCALE:+/$LOCALE}${FLAGS:+/$FLAGS}${DEVICE_MODEL:+/$DEVICE_MODEL}"
export BRAND TARGET_ENV="${TARGET_ENV:-}" PLATFORM="$DEVICE_TYPE" LOCALE="${LOCALE:-}" FLAGS="${FLAGS:-}" FORM_FACTOR DEVICE
export DEVICE_MODEL="${DEVICE_MODEL:-}" TIMEOUT_SCALE="${TIMEOUT_SCALE:-1}"
export TARGET_ID="$BRAND/${TARGET_ENV:-}/$DEVICE_TYPE/${LOCALE:-}/${FLAGS:-}/$FORM_FACTOR/$DEVICE"   # 多種裝置型號 / 解析度時設 DEVICE_MODEL

# 裝置鎖：同一台裝置同時只能有一個 run
LOCK=".locks/${DEVICE//[^A-Za-z0-9._-]/_}"; mkdir -p .locks
if ! mkdir "$LOCK" 2>/dev/null; then echo "❌ 裝置 $DEVICE 正在被另一個 run 使用（$LOCK）；確定沒有在跑就刪掉這個資料夾" && exit 1; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
# 執行 id 帶裝置，避免並行時同一秒起跑撞目錄
TS="$(date +%Y%m%d_%H%M%S)_${DEVICE//[^A-Za-z0-9]/_}"
if [ "$UI_DIFF" = "true" ]; then
  RUN_DIR="ui_compare/${BASELINE_KEY}/${TS}"; EXTRA+=(--test-output-dir="./${RUN_DIR}/_raw"); FUNC_DIR="${RUN_DIR}/_raw"
elif [ -n "$USER_OUT" ]; then
  RUN_DIR="$USER_OUT"; EXTRA+=(--test-output-dir="$USER_OUT"); FUNC_DIR="$USER_OUT"
else
  RUN_DIR="test-results/${TS}"; EXTRA+=(--test-output-dir="./${RUN_DIR}"); FUNC_DIR="$RUN_DIR"
fi
mkdir -p "$RUN_DIR"
echo "▶️  Brand: $BRAND | Env: ${TARGET_ENV:-(none)} | Platform: $DEVICE_TYPE | Locale: ${LOCALE:-(default)} | Device: $DEVICE"
echo "   Flows: ${FLOW_TARGETS[*]} | Out: $RUN_DIR"

# ---- 4. watchdog + 本機執行 ----
set +e
TIMEOUT_MIN="${MAESTRO_TIMEOUT_MIN:-60}"
MARKER="${RUN_DIR}/.watchdog_timeout"; rm -f "$MARKER"; WD=""
if [ "$TIMEOUT_MIN" -gt 0 ] 2>/dev/null && ! command -v pkill >/dev/null; then
  echo "⚠️ 這台機器沒有 pkill（Windows Git Bash？），watchdog 無法運作 → 改用 CI 層 timeout 或在 WSL2 執行"
fi
if [ "$TIMEOUT_MIN" -gt 0 ] 2>/dev/null && command -v pkill >/dev/null; then
  ( sleep $((TIMEOUT_MIN*60))
    if pgrep -f -- "--device ${DEVICE} test" >/dev/null; then
      echo "⏰ 超過 ${TIMEOUT_MIN} 分鐘，watchdog 強制結束"; touch "$MARKER"
      pkill -TERM -f -- "--device ${DEVICE} test"; sleep 10; pkill -KILL -f -- "--device ${DEVICE} test"
    fi ) &
  WD=$!
fi

maestro --device "$DEVICE" test "${ENV_ARGS[@]}" "${EXTRA[@]}" "${FLOW_TARGETS[@]}"
TEST_EXIT=$?

[ -n "$WD" ] && { pkill -P "$WD" 2>/dev/null; kill "$WD" 2>/dev/null; wait "$WD" 2>/dev/null; }
[ -f "$MARKER" ] && [ "$TEST_EXIT" -eq 0 ] && TEST_EXIT=124

# ---- 5. 視覺比對（選配，M10 屬完整版；Lite 沒有 ui_diff_check.py 時自動略過）----
DIFF_EXIT=0
if [ "$UI_DIFF" = "true" ] && [ ! -f scripts/ui_diff_check.py ]; then
  echo "⚠️ 帶了 ui_diff_enabled=true，但沒有 scripts/ui_diff_check.py（視覺回歸模組未安裝），略過比對"
  UI_DIFF="skipped"
fi
if [ "$UI_DIFF" = "true" ]; then
  if [ "$UI_BASELINE" = "true" ]; then python3 scripts/ui_diff_check.py "$RUN_DIR" "$BASELINE_KEY" --capture-baseline
  else python3 scripts/ui_diff_check.py "$RUN_DIR" "$BASELINE_KEY"; DIFF_EXIT=$?; fi
fi

# ---- 6. 重跑名單（M11，先跑：報表要讀 flaky）+ 報表（M9）+ 通知 ----
python3 scripts/_summarize_results.py "$FUNC_DIR" || echo "⚠️ 狀態檔有警告（見上）"
OUT=$(python3 scripts/generate_report.py "$FUNC_DIR"); RG=$?
echo "$OUT"
REPORT=""
ROOT_REPORT="./report.html"; [ "${RERUN:-0}" = "1" ] && ROOT_REPORT="./report_rerun.html"
if [ $RG -eq 0 ]; then REPORT=$(echo "$OUT" | tail -1); [ -f "$REPORT" ] && cp "$REPORT" "$ROOT_REPORT" && echo "   → $ROOT_REPORT"
else echo "⚠️  報表產生失敗（exit=$RG），./report.html 維持上次內容"; fi

FINAL=0; [ "$TEST_EXIT" -ne 0 ] && FINAL=1; [ "$DIFF_EXIT" -ne 0 ] && FINAL=1
{ [ -n "${NOTIFY_WEBHOOK_URL:-}" ] || [ "${NOTIFY_FORMAT:-}" = "email" ]; } && [ -x scripts/notify.sh ] && \
  RUN_DIR_ABS="$(cd "$FUNC_DIR" && pwd)" scripts/notify.sh "$FINAL" "$TARGET_ID" "${REPORT_URL:-$REPORT}" || true
[ $FINAL -ne 0 ] && echo "❌ 最終結果：失敗（test_exit=$TEST_EXIT, ui_diff_exit=$DIFF_EXIT）"
exit $FINAL
