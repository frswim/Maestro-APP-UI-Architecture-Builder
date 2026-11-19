# 核心模組規格（Lite：M1～M7、M9、M11～M15）

模組編號與完整版一致（Lite 沒有 M8、M10、M16～M20），日後升級不用重新對照。程式範例見 `reference-implementation.md`，模板在 `../templates/`。

## 目錄總覽

```
<project>/
├── config/
│   ├── brands/<brand>.yaml          # M2 扁平 key: value（實檔不進版控，只放 .example）
│   ├── env/<env>.yaml               # M2 環境疊加（TARGET_ENV）
│   ├── test_data/<brand>/*.js       # M2/M4 帳號 → case（active → <brand>）
│   ├── selectors/<platform>/<brand>/*.js   # M3 定位器（active → <platform>/<brand>）
│   └── selector_labels.json         # M9 定位器 key → 人類可讀名稱
├── flows/config.yaml                # Maestro workspace：flows: ["**"]（模板 flows-config.yaml；沒有它子資料夾的 flow 不會被執行）
├── flows/<domain>/<flow>.yaml       # 主流程
├── subflows/common/                 # M5/M6 共用片段與 helper
├── subflows/<domain>/               # 業務專屬：導航、variant_body_<type>.yaml
├── api/scripts/                     # M7
├── scripts/                         # run_suite.sh、run_failed.sh、failure_rules.py、generate_report.py、
│                                    # _summarize_results.py、flow_index.py、snap.sh、notify.sh、notify_payload.py
├── docs/                            # M13 手冊、intake、ADR
├── test-results/                    # 產出（不進版控）
└── report.html                      # 最新報表（不進版控）
```

---

## M1 單一執行入口

`./scripts/run_suite.sh <brand> <flow 或資料夾>... [-- <maestro 原生參數>]`（模板 `templates/run_suite.sh`）

做的事：驗證參數與設定檔 → 品牌設定轉 `-e KEY=VALUE`（`TARGET_ENV` 疊加）→ 切 `active` → 明確指定輸出目錄 `test-results/<ts>_<device>/` → 裝置鎖 → watchdog（`MAESTRO_TIMEOUT_MIN`，預設 60 分，0 關閉）→ 執行 → 重跑名單 → 報表 → 通知 → exit code。

常用環境變數：`TARGET_ENV`、`PLATFORM`（覆寫 device_type）、`DEVICE`、`LOCALE`、`TIMEOUT_SCALE`、`MAESTRO_TIMEOUT_MIN`、`REPORT_LANG`、`REPORT_INLINE_ASSETS`、`NOTIFY_*`（完整清單在腳本檔頭）。

坑：少打 `--` 會把 `-e x=y` 當成 flow 路徑（runner 會擋並提示）；密碼含 `!!` → runner 已 `set +H`，必要時拆兩段變數；設定檔只能扁平 `key: value`，清單 / 物件放測試資料；Windows 用 WSL2。

驗證：故意給錯品牌名、少 `--`、`MAESTRO_TIMEOUT_MIN=1` 跑長流程 → 都有清楚訊息且仍產出報表。

## M2 設定分層

| 層 | 內容 | 版控 |
|---|---|---|
| 品牌 / 環境設定 | `device_type`（必填）、app_id、裝置、後台網址、預設金額、表單假資料 | 只放 `.example` |
| 機密 | 帳密、token | 本機或 CI secret，永不進版控 |
| 測試資料 | 帳號 → case 清單（`.js`，設定 `output.xxx`） | 含真帳密就不進 |

單一 App：brand 固定 `default`，仍保留結構。

## M3 定位器外置

- `config/selectors/<platform>/<brand>/<page>.js`，掛在 `output.selector.<page>`；`active` 由 runner 切。
- 優先序：**id / testID / accessibilityIdentifier > 文字 > 百分比座標**（座標只在 WebView 無 id 時用，旁邊註解原因）。
- 動態 id 用 regex（例如 `v-.*-input`）並註明可能誤配。
- 各平台 / 品牌同頁同檔名、同 key 名。只在主 flow 載入定位器，子片段直接用 `output.*`。
- 每個 leaf 用 `{ text }` / `{ id }` / `{ point }`，flow 內寫完整路徑 —— 報表反查需要。新增 key 同步補 `selector_labels.json`。
- 框架提醒：Flutter 用 `Semantics(identifier:)`；Jetpack Compose 開 `testTagsAsResourceId`；SwiftUI 用 `.accessibilityIdentifier`；WebView 的 `data-testid` Maestro 看不到。

## M4 資料驅動迴圈

```
資料檔：accounts = [{ user, pw, cases: [{ type, variant, account_id, ... }] }]
主 flow：載入資料 → 外層（帳號）→ 內層（case：設 output.current* → 共用前置 → 依 type 分派 variant_body_<type> → 共用收尾）
```
- UI 步驟不同的變體才拆 `variant_body_<type>`；只差參數就不拆。
- 迴圈變數名照契約（`output.currentCase`、`output.currentType`）。
- 欄位缺省要 fallback 並避免殘留上一輪的值。暫停某 case：資料檔註解掉該行。
- Maestro 不支援動態檔名 → 每個 type 一個 `when` 分支。

## M5 共用片段

- 片段只管「怎麼到達 / 離開某頁」；斷言留在主 flow 或變體片段。
- 參數用 `runFlow: { file, env }` 覆寫；開頭註解前置條件、讀哪些變數、結束停在哪頁。
- 每支主 flow 冷啟動一次（`stopApp`），session 保留，只在切帳號時重登；結束時回到下一支 flow 能接手的頁面。

## M6 韌性

- `wait_anchor_or_dismiss`：（選擇性先點）→ 分段等錨點 → 等不到才清彈窗 → **確實關掉才重點** → 牆鐘截止 → 逾時 assert 並寫明在等什麼。錨點三選一：`anchor_text` / `anchor_id` / `gone_text`（原頁按鈕消失 = 已跳轉）；`confirm_text`：流程本來就要點的確認鈕；`settle_ms`：錨點出現後再掃一次彈窗。
- `dismiss_blocking_popups`：讀定位器的 `blocking_dismiss_ids` 與 `blocking_dismiss_by_title`（按鈕要在已知標題下方才點）。
- `retry_tap_until_visible`：loading mask 吃點擊時重點，有次數上限。
- 只套在階段切換點；不要每步都「先檢查有沒有彈窗」（沒彈窗也會白等約 7 秒）；動態迴圈次數先算成合法整數並封頂。
- 新彈窗 SOP：抓 hierarchy → 有 id 加 id 清單、沒 id 加「標題 + 按鈕」→ 不改 flow。系統 ANR 對話框也可加進清單。
- 低階裝置：`TIMEOUT_SCALE` 等比放大 helper 的等待上限。

## M7 後台 / API hook（基本）

- 整輪登入一次，session 存共享變數；網址與帳密來自 M2。
- 能從畫面取得單號就用單號查，取不到才用帳號查最新一筆（並寫明是 fallback）。
- 任何失敗要 **throw**，報表才會判 FAIL；環境問題（帳號失效等）訊息以 `[BLOCKED]` 開頭。
- OTP：優先測試環境固定碼 / 白名單，其次後台查碼 API（有重試與逾時）。詳見 `capability-catalog.md`。

## M9 結果判定 + 報表

- 判定（`failure_rules.py`，報表與重跑共用）：阻斷錯誤 → FAIL；watchdog 標記 → FAIL「執行未完成」；沒有 `commands.json` → FAIL「被中斷」；含 `[BLOCKED]` → BLOCKED（不算缺陷，exit code 仍非 0）；optional 指令的 warning 不算失敗。
- 錯誤情境：從 log 找失敗步驟的定位器路徑 → `selector_labels.json` 翻成「流程 / 階段 / 目標」；共用 helper 內失敗時從呼叫端 env 反查；加上 case tag 與失敗截圖。
- 報表：單檔 HTML、圖片內嵌、卡片預設收合、列印時自動展開；`REPORT_LANG`；不得連外時 `REPORT_INLINE_ASSETS=1`。
- 驗證：拿幾份歷史 log 回放，看判定與情境是否正確。

## M11 只重跑失敗

`_summarize_results.py` 產 `.last_run_status.json`（key `<flow>@<target>`）；`run_failed.sh` 只跑失敗的、依紀錄還原目標維度；重跑報表另存 `report_rerun.html`；只有重跑才通過的標 flaky。

## M12 開發工具

- `scripts/snap.sh [device]`（iOS：`PLATFORM=ios`）：截圖 + 元素表，寫定位器最常用。
- 安裝說明寫進 README：JDK、Android SDK / Xcode、Maestro CLI、Python 3.9+ 與 `requirements.txt`。
- 上傳類流程：預先推送測試檔並授權（`adb push`、`adb install -g`）。

## M13 知識層

- 使用者操作手冊（不寫程式的人看得懂：每次測試步驟、改哪個資料檔、怎麼看報表、什麼要回報）。
- 維護說明（運作原理、新增 flow / 品牌 / 變體、除錯）。
- 子系統設計文件（含踩過的坑）、release note（新增 / 修改 / 刪除、如何驗證、未驗證範圍）、ADR。

## M14 版控

`.gitignore`（範本在 `templates/config-examples.md`）：機密與品牌實設定、`active` symlink、test-results、報表、截圖、log；需要共享的二進位資產用例外規則救回。

## M15 CI（GitHub Actions）

`templates/ci-github-actions.yml`：PR 跑 `smoke`（目標 < 15 分鐘）、夜間跑回歸；品牌設定由 secrets 產生；上傳 `report.html` 與 `test-results/`；以 runner exit code 決定成敗。其他 CI：在 job 裡執行同一行 `run_suite.sh` 即可。
