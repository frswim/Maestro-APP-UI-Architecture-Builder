# 架構模組規格（M1～M20）

每個模組：目的 / 何時納入 / 最小檔案集 / 設計規則 / 常見坑 / 驗證方式。
路徑以 Maestro 版為例；其他工具的對應寫法見文末對照表。完整程式範例見 `reference-implementation.md`，模板在 `../templates/`。

建議目錄總覽（只建有納入的部分）：

```
<project>/
├── config/
│   ├── env/<env>.yaml               # M2 環境疊加（TARGET_ENV）
│   ├── flags/<profile>.json         # feature flag 組合（FLAGS）
│   ├── report_mask.json             # M9 遮罩規則（合規時）
│   ├── brands/<brand>.yaml          # M2 品牌/環境設定（扁平 key: value，不進版控或只進 .example）
│   ├── brands/<brand>.yaml.example  # M2 範本（進版控）
│   ├── test_data/<brand>/*.js       # M2/M4 測試資料（帳號 → case），active → <brand>
│   ├── selectors/<platform>/<brand>/*.js   # M3 定位器，active → <platform>/<brand>
│   ├── selector_labels.json         # M9 定位器 key → 人類可讀名稱
│   └── ui_baseline/<baseline_key>/<checkpoint>/   # M10 基線圖 + settings.yaml（進版控）；baseline_key = brand/platform/form_factor[/locale][/flags][/model]
├── flows/<domain>/<flow>.yaml       # 主流程（可單獨執行）
├── subflows/
│   ├── common/                      # M5/M6 跨業務共用：登入、回首頁、等錨點、清彈窗、重試
│   ├── <domain>/                    # 業務專屬：導航、variant_body_<type>.yaml
│   └── ui_diff/checkpoint.yaml      # M10
├── api/scripts/                     # M7 後台 API hook
├── mocks/                           # M8
├── scripts/
│   ├── run_suite.sh                 # M1 單一入口
│   ├── failure_rules.py             # M9 判定規則（報表與重跑共用）
│   ├── generate_report.py           # M9
│   ├── run_failed.sh / _summarize_results.py   # M11
│   ├── ui_diff_check.py / ui_diff_define_ignore.py  # M10
│   └── snap.sh / debug_flow.sh / setup_test_files.sh # M12
├── setup/setup.sh                   # M12
├── docs/                            # M13 使用手冊、維護教學、intake、ADR
├── .claude/skills/<subsystem>/SKILL.md   # M13 子系統設計與坑
├── test-results/                    # 產出（不進版控）
└── report.html                      # 最新報表（不進版控）
```

---

## M1 單一執行入口（runner）

**目的**：一行指令跑任何測試；把設定載入、資源切換、輸出管理、超時保護、報表、exit code 收在一處。

**最小檔案集**：`scripts/run_suite.sh`（模板 `templates/run_suite.sh`）。

**介面**：`./scripts/run_suite.sh <brand> <flow 檔或資料夾>... [-- <傳給測試工具的原生參數>]`
- `--` 之前是 runner 自己的參數，之後原封不動傳給工具。文件要特別強調「少打 `--` 會把 `-e x=y` 當成檔案路徑」。

**執行順序**：
1. 驗證參數與設定檔存在（缺什麼就明確報錯：「brand config not found」「尚未建立測試資料」「Selector directory not found」「device_type 未設定」）。
2. 讀品牌設定 → 轉成工具的環境變數參數（Maestro：`-e KEY=VALUE`）。
3. 切換 `active` 指向（test_data、selectors）。
4. 決定輸出目錄 `test-results/<timestamp>/`（**一定要明確指定**，很多工具預設寫到家目錄，會散落看不到的垃圾）。
5. 啟動 watchdog（背景 subshell：超過 `TIMEOUT_MIN` 分鐘 → 結束測試程序 → 寫 `.watchdog_timeout` 標記 → exit 124）。
6. 前景跑測試（Ctrl-C 要照常有效）；測試失敗不能讓 runner 立刻 `exit`（`set +e`），後面還要產報表。
7. 選配：視覺比對（M10）。
8. 產報表（M9），複製一份到根目錄 `report.html`。
9. 最終 exit code = 功能測試失敗 OR 視覺檢查失敗（建立基線模式不影響 exit code）。

**雲端裝置農場模式（Q-P5-1=c）**：本機的 symlink 切換、`pkill` watchdog、直接讀本機結果檔都不能用。分兩種：
- **客戶端驅動**（BrowserStack App Automate、Sauce：測試在你的機器 / CI 跑，透過遠端 WebDriver 連雲端裝置）→ runner 結構同本機，只是 capabilities 指向雲端；受測環境（staging）不對外公開時要開農場的 tunnel（BrowserStack Local、Sauce Connect），並確認公司網路政策允許；
- **伺服器端執行**（AWS Device Farm、Maestro Cloud；Firebase Test Lab 只跑 instrumentation / Robo / Game Loop，**不能跑 Appium / Maestro**，見 `interview-pipeline.md` P5.5 相容表）→ 下面步驟。AWS Device Farm 例：`aws devicefarm create-upload`（APK、測試包、test spec）→ PUT presigned URL → `schedule-run --device-pool-arn …` → 輪詢 `get-run` → `list-artifacts` 下載；Appium Python 要先 `pip wheel` 成 wheelhouse 一起打包；單次 run 有時間上限；模板 `templates/azure-pipelines.yml` 有完整骨架。
原生框架上雲（Sauce / BrowserStack 跑 Espresso / XCUITest）屬於伺服器端執行：例 Sauce `saucectl run`（`.sauce/config.yml` 指定 app、testApp、裝置、並行數）→ 下載 JUnit / 截圖 → 轉 §3.1 JSON 給報表。
伺服器端執行步驟：
1. 準備：同上產生設定、把 `active/` **實體化**（`cp -R`，上傳包不保留 symlink）、打包 flows/subflows/config。
2. 上傳 App（Android `.apk`；iOS 實機要**已簽章的 `.ipa`**，模擬器才用 `.app`）與測試包，指定裝置清單與並行數。
3. 輪詢狀態，設上限（取代 watchdog；逾時就呼叫農場 API 停止並標 `.watchdog_timeout`）。
4. 下載每台裝置的 log / 截圖 / 結果，**轉成本機相同的目錄結構**（`test-results/<ts>/<device>/<flow>/logs/...`），讓 M9/M11 不用改。
5. exit code = 農場回報狀態 OR `failure_rules` 判定。
先用一條 hello-world flow 實測該農場支援的工具版本與指令（例如 AI 擷取、HTTP、runScript 是否可用），結果寫進 ADR。

**目標維度**：brand（白牌；單一 App 用 `default`）× env（`TARGET_ENV`）× platform（`PLATFORM`）× locale（`LOCALE`）。模板 `templates/run_suite.sh` 已實作這四個維度與 env 疊加覆寫。

**常見坑**：
- macOS 沒有 `timeout` 指令 → 用背景 subshell + `pgrep/pkill -f "<device> test"`。
- 密碼含 `!!` 被 bash history expansion 吃掉 → runner 開頭 `set +H`；必要時密碼拆兩段變數。
- 扁平設定解析不懂巢狀 YAML → 設定檔規定只能 `key: value`，清單/物件一律放測試資料檔。

**驗證**：故意給錯品牌名、少 `--`、把 `TIMEOUT_MIN=1` 跑長流程，三種都要有清楚訊息且仍產出報表。

---

## M2 設定分層

**目的**：flow 不寫死任何環境值；換環境/品牌只換設定；機密不進版控。

**三層**：
| 層 | 內容 | 格式 | 版控 |
|---|---|---|---|
| 品牌/環境設定 | app_id、裝置、平台 `device_type`、後台網址、預設金額、表單假資料 | 扁平 `key: value` | `.example` 進版控，實檔不進 |
| 機密 | 帳密、token、後台帳密 | 本機設定或 CI secret 注入 | 永不進版控 |
| 測試資料 | 帳號 → case 清單（可巢狀） | 工具能直接載入的格式（Maestro 用 `.js`，設定 `output.xxx`） | 依資安規定；含真帳密就不進 |

**設計規則**：
- `device_type`（android/ios）必填、不給預設值，缺了 runner 直接失敗。
- 敏感字元（如 `!!`）的處理方式寫進設定檔註解。
- 多環境：`config/env/<env>.yaml` 疊加在品牌設定之上（同 key 覆寫），runner 用 `TARGET_ENV=<env>` 選擇。
- 多語系：runner `LOCALE=<x>` → flow 收到 `${locale}`；測試資料可放 `test_data/<brand>/<locale>/`（有就自動選用）；App 語系切換方式（launch argument、裝置語系、雲端 capability）寫進 ADR。
- 單一 App：品牌參數固定 `default`，仍保留結構，未來加品牌不用重構。
- **Vault 變體**（Q-P5-3=f）：執行時由 CI plugin（Jenkins Vault plugin、GitHub OIDC → Vault）或 `vault agent` 注入成環境變數；設定檔只放 secret path 或變數名；本機開發用個人 token 拉取，不落地成檔案。

---

## M3 定位器外置

**目的**：App 改版只改定位器檔；同一 flow 跑多平台多品牌。

**結構**：`config/selectors/<platform>/<brand>/<page>.js`，每檔掛在 `output.selector.<page>`；`active → <platform>/<brand>` 由 runner 切換。

**設計規則**：
- 定位優先序：**id / testID / accessibilityId > 文字 > 百分比座標**。座標只在 WebView 無 id 且文字不可用時用，旁邊註解為什麼。
- 動態 id（框架自動編號）用 regex（例如 `v-.*-input`），並註明可能誤配。
- 所有平台/品牌同頁同檔名、同 key 名；值不同而已。
- **Jetpack Compose**：`Modifier.testTag()` 預設**不會**變成 resource-id，Appium / Maestro / UiAutomator 看不到 → 在根 composable 設 `Modifier.semantics { testTagsAsResourceId = true }`（Compose 1.2+）；Compose UI test（原生）則直接用 `onNodeWithTag`。**SwiftUI**：用 `.accessibilityIdentifier("...")`（不要用 `accessibilityLabel` 當定位器）。
- **白牌很多（例如 10+ 品牌）**：定位器不要每品牌整份複製 → `selectors/<platform>/_base/` 放共用，`selectors/<platform>/<brand>/` 只放差異（主 flow 先載 `_base` 再載 `active`；品牌目錄不存在時 runner 自動指向 `_base`）。
- 跨平台框架（RN / Flutter）兩平台 testID 相同時：用 `selectors/shared/<page>.js` 放共用值，`selectors/<platform>/<brand>/<page>.js` 只放差異（主 flow 先載 shared 再載 active，後者覆寫）。RN 的 `testID` 在 Android 對應 resource-id（需確認有開啟對應設定）、iOS 對應 accessibilityIdentifier。**Flutter：Widget `Key` 不會進 accessibility tree，外部工具看不到**；要用 `Semantics(identifier: 'checkout_submit')`（Flutter 3.19+，對應 resource-id / accessibilityIdentifier，不會被翻譯）。不要拿 `semanticsLabel` 當定位器（那是給讀屏的文字，會隨語系變、會被 a11y 修正改掉）。注意 Semantics 合併子節點（`MergeSemantics`、按鈕內文字）會讓內層元素消失，用抓元素工具確認；無限動畫（loading、Lottie）會讓「等畫面穩定」一直等，要在測試版關掉或用明確錨點。
- 多語系且只能用文字定位時：定位器值依語系分（`{ text: { en: "...", zh_TW: "..." } }` 或語系子目錄），彈窗清單同理。
- 只在主 flow 載入定位器，子片段直接用（Maestro 的 `output` 全域共享），省掉大量重複載入。
- 每個 leaf 用物件 `{ text: "..." }` / `{ id: "..." }` / `{ point: "x%,y%" }`，引用時寫完整路徑 `${output.selector.page.section.key.text}` —— 報表反查需要這個完整路徑（M9）。
- 新增 key 時同步補 `selector_labels.json`（報表的人類可讀名稱）。

**驗證**：腳本掃所有品牌的定位器檔，比對 key 集合是否一致、labels 是否有缺（範例指令見 `reference-implementation.md` §3）。

---

## M4 資料驅動迴圈

**目的**：N 種變體 × M 組帳號不用寫 N×M 支腳本。

**結構**：
```
資料檔：accounts = [{ user, pw, cases: [{ type, variant_name, account_id, currency, ... }] }]
主 flow：載入資料 → 外層迴圈（帳號：登入 → 內層 → 登出）
                      → 內層迴圈（case：設定 current* 變數 → 共用前置 → 依 type 分派 variant_body_<type> → 共用收尾）
```

**設計規則**：
- 變體 UI 步驟不同 → 每個 type 一個 `variant_body_<type>` 片段（唯一來源）；步驟相同只差參數 → 不拆檔。
- 迴圈裡把目前 case 的欄位寫成 `output.currentX`，子片段直接讀；報表的 case tag 靠這些變數名稱反查（M9）。
- 欄位缺省要有 fallback（例如金額：case 有帶用 case 的，否則依幣別用設定檔預設），並避免殘留上一輪的值。
- 不同業務線（例如入金/出金）各自一支迴圈 flow，第三次重複才抽共用骨架。
- 多帳號切換需要真的登出/登入片段；若登出還沒做，文件明寫「只能單帳號」。
- 暫時不跑某 case：資料檔註解掉該行，不改 flow。

**常見坑**：工具不支援「動態決定要載入哪個檔案」→ 只能 runner 先切 `active`，flow 讀固定路徑。

---

## M5 共用片段

**目的**：登入、回首頁、切 tab、關第三方頁、結果頁返回等重複操作只寫一次。

**設計規則**：
- 片段只負責「怎麼到達 / 怎麼離開某頁」，驗證點（含視覺 checkpoint）留在主 flow 或變體片段的明確位置。
- 片段參數用工具的子流程 env 覆寫（Maestro：`runFlow: { file, env: {...} }`），不改片段本身。
- 片段開頭註解：前置條件、讀哪些變數、結束時停在哪一頁。
- 每支主 flow 冷啟動一次（`stopApp`），session 保留（不清資料），只在切帳號時重登。
- 每個 flow 結束要把 App 帶回下一個 flow 能接手的狀態（通常是首頁）。

---

## M6 韌性層

**目的**：不穩定（彈窗、載入慢、點擊被吃掉）不再讓測試失敗；任何等待都會結束。

**元件**：
1. **`wait_anchor_or_dismiss`**（核心 helper）：（選擇性先點）→ 分段等錨點 → 等不到就清阻擋型彈窗 → **確實關掉彈窗才重點** → 直到牆鐘截止 → 逾時 assert 失敗並寫明在等什麼。
   - 錨點三選一：文字出現 / id 出現 / 文字消失（用於「已跳到第三方頁」）。
   - `confirm_text`：流程本來就要點的確認鈕，等不到錨點時若在畫面上就點它，不當彈窗關、也不重點。
   - `settle_ms`：錨點出現後再掃一次彈窗（處理「頁面先出現、彈窗隨後跳出」）。
2. **`dismiss_blocking_popups`**：讀定位器的彈窗清單（id 清單 + 「標題 + 按鈕」配對），一次 regex 判斷涵蓋全部；按鈕必須在已知標題下方才點，避免誤點正常頁面的 Close。
3. **`retry_tap_until_visible`**：給「loading mask 吃點擊」的 WebView：重點直到下一頁錨點出現，有次數上限。
4. **watchdog**：在 M1。

**系統對話框**：ANR（「App 沒有回應」標題 + 「等待」按鈕）、系統更新提示、權限對話框也加進彈窗清單（多語系文字都要列）；低階機常見。
**等待上限放大**：runner `TIMEOUT_SCALE`（以 `-e timeout_scale` 傳入），`wait_anchor_or_dismiss` 模板會等比放大 `timeout_ms`；低階裝置 profile 設 1.5～2。
**彈窗處理優先序**：①測試版 flag 關掉（Q-P2-6=b）②測試帳號設定不觸發（例如已評分、已看過引導）③M6 清單自動關 ④報表顯示等待目標 + 截圖，人工補清單。系統層 UI（iOS 評分對話框、Android In-App Review、系統權限對話框）不一定在 App hierarchy 裡，不要只依賴 ③。

**設計規則**：
- 只套在「階段切換點」（點擊 → 換頁 → 等下一頁），不套在同頁輸入步驟。
- 不要每一步前都「先檢查有沒有彈窗」：多數工具的條件判斷在元素不存在時會等滿內部 timeout，沒彈窗也白等。
- 所有動態迴圈次數要先算成合法整數並封頂（有些工具非法次數會靜默變無限）。
- 新彈窗 SOP：抓 hierarchy → 有 id 加 id 清單、沒 id 加「標題 + 按鈕」→ 所有品牌都加 → 不改 flow。
- 跟前端約定通用關閉鈕 id（預留在清單，前端還沒做時無副作用）。

**已知限制要寫進文件**：點到彈窗的 CTA 跳頁救不回來；不在清單的彈窗仍會逾時失敗（報表會寫明等的元素 + 截圖）。

---

## M7 後台 / API hook

**目的**：需要後台動作的流程全自動（審批、改狀態、發碼、補資料）。

**設計規則**：
- 整輪測試開始時登入後台一次，session（cookie/token）存在共享變數，所有 case 共用。
- 後台網址、帳密來自 M2；密碼雜湊等處理在腳本內完成（工具 JS 環境不能 `require` 外部模組時就內嵌實作）。
- 查單策略：畫面能取到單號 → 用單號查；取不到（第三方頁無畫面）→ 用帳號查最新一筆並寫明這是 fallback。
- 單號擷取：優先元素文字；拿不到才用 OCR/AI 擷取，並在擷取前等畫面穩定、清彈窗。
- 任何失敗要 **throw**（讓工具記成阻斷錯誤 → 報表判 FAIL），不要只 log。
- **OTP 變體**：優先序 ①測試環境固定 OTP / 白名單 ②查碼 API（送出後輪詢，設次數與逾時上限，取到後 inputText）③測試版 bypass flag ④測試信箱 API ⑤硬體 token / TOTP：seed 放機密庫、測試內計算或呼叫 token 模擬 API、處理時鐘偏移與一碼一次。正式環境不自動化 OTP（或專用帳號 + 長效 session）。
- **金流 sandbox 訂單驗證**：走 sandbox 測試卡 / 3DS 測試 challenge 到完成頁後，再用 API 查訂單狀態當最終斷言（UI 完成頁 + 後端狀態雙重確認）。
- session 過期：給明確錯誤訊息與手動更新步驟（文件化）。

---

## M8 Mock

**目的**：到達難以準備的狀態（特定會員等級、錯誤回應）。

**作法**：代理（例如 mitmproxy）+ profile JSON（URL regex → 回應 body）；`run_case.sh <profile> <flow>` 起代理 → 設裝置 proxy → 跑 → trap 還原 proxy。需要一次性安裝代理 CA 到模擬器系統憑證。
**規則**：mock 的 flow 用 tag 區分，報表標示「mock 情境」；不在 mock 下驗證真實金流結果。

---

## M9 結果判定 + 報表

**目的**：結果可信（不誤判）、失敗看得懂、可轉寄。

**判定規則（`failure_rules.py`，報表與重跑共用一份）**，依序：
1. 阻斷錯誤 → FAIL：log 有工具的「指令失敗」標記，或結果檔中任一步驟狀態 FAILED。
2. watchdog 標記存在 → FAIL「執行未完成：超過時間上限」。
3. 結果檔（例如 Maestro 的 `commands.json`，只有正常結束才會寫）不存在 → FAIL「執行未完成：被中斷」。
4. 其他 → PASS。optional 指令的 warning 不算失敗。

**錯誤情境分析（純事後解析 log，不改 flow）**：
- 找最後一個阻斷錯誤行 → 往前找最近一個 FAILED 步驟裡的定位器路徑 `output.selector.<page>.<...>.<leaf>`。
- 路徑拆段：第一段 = 流程、最後一段 = 動作/目標、中間 = 階段；查 `selector_labels.json` 翻成人話，查不到用 Title Case fallback。
- 失敗在共用 helper 內（只看得到中繼變數）→ 改從「呼叫 helper 那一行」的 env 參數反查定位器。
- case tag：數迴圈跑到第幾個 case、最後一次 type 分派的值。
- 截圖挑選：錯誤截圖 > 編號最大的步驟截圖 > 任一張。

**結果三態 + flaky**：PASS / FAIL / BLOCKED（環境或資料問題，訊息以 `[BLOCKED]` 開頭，見 `templates/failure_rules.py`），重跑才通過標 flaky。BLOCKED 不算缺陷率，但 exit code 仍非 0。
**遮罩**（Q-P5-3=d）：`config/report_mask.json` —— `text`（regex 取代，套用在所有輸出到報表的字串）與 `screenshot_rects`（嵌入前塗黑）；遮罩失敗就不嵌圖。`inputText` 的密碼 / OTP 也會出現在 log，要加規則。
**語言**：`REPORT_LANG=zh-Hant|ja|en|ko`（模板內建四種，字串表在 `generate_report.py` 的 `_I18N`；未知語言退回 en 並警告 —— 讀者用其他語言（例如 ms、ta、zh-Hans、pt-BR）時，複製 `en` 那份翻譯後加進 `_I18N`，`failure_rules.py` 的 `_REASONS` 同步補）；`selector_labels.json` 用讀者語言填。
**通知與發佈**：`templates/notify.sh`（webhook URL 只從環境變數 / CI secret 讀）；CI 上把 `report.html` 當 artifact 上傳，通知附 run 連結。
**可攜性限制**：模板報表的圖片 base64 內嵌；Bootstrap 預設從 CDN 載入 —— 內網 / 資料駐留 / 證據長期保存時設 `REPORT_INLINE_ASSETS=1`，並把 bootstrap 檔放 `config/vendor/`（找不到檔案時改用無外部資源的陽春版） —— 讀者離線或公司擋 CDN 時排版會跑掉、卡片無法展開。需要完全離線時，把 Bootstrap 檔案內嵌進 `<style>` / `<script>`（約 +250KB）。

**報表內容**：總覽（數量、圓餅）→ 每個 flow 卡片（預設收合，按鈕顏色=狀態）→ 失敗卡片：case tag、三行情境（流程/階段/目標）、可摺疊的詳細資料（定位器路徑、實際值、錯誤原文、log 路徑）、右側失敗截圖 → 視覺回歸區塊。單檔 HTML、圖片 base64 內嵌。

**驗證**：拿歷史 log 回放，新舊判定做差異表（哪些 FAIL→PASS、PASS→FAIL、原因），寫進 release note。

---

## M10 視覺回歸（UI Diff）

**目的**：抓跑版、文案錯、非預期畫面變化。

**兩層旗標**：`ui_diff_enabled`（主開關，關閉時連截圖都不做）→ `ui_diff_capture_baseline`（true = 建立/更新基線模式，不比對；否則 = 檢查模式）。

**狀態**：建立基線模式只有 `NO_BASELINE`（首次建立，資訊性）/ `UPDATED` / `ERROR`；檢查模式有 `PASS` / `FAIL` / `LAYOUT_MISMATCH` / `MISSING_BASELINE` / `ERROR`。兩種模式的結果不放同一份統計。

**設計規則**：
- checkpoint 在 flow 裡只是「設定名稱 + 呼叫共用 checkpoint 片段」兩行；參數不寫在 flow。
- 基線 key = 會讓畫面不同的維度組合：模板 runner 組成 `<brand>/<platform>/<form_factor>[/<locale>][/<flags>][/<device_model>]`（`DEVICE_MODEL` 在多型號 / 雲端多裝置時必設），否則基線互相覆蓋。
- 每個 checkpoint 一個資料夾：`config/ui_baseline/<baseline_key>/<checkpoint>/current.png + settings.yaml`（threshold、failOnDiff、color_tolerance、ignore 矩形），**不共用樣板**（每張基線都被個別檢查過）。
- 隨變體不同的畫面 → 名稱帶 type；不隨變體變的畫面 → 同輪只截一次（片段內維護已截清單）。
- 比對：套忽略遮罩後逐像素比對（不用 SSIM：平均化指標會吃掉小範圍異常），預設 0 容忍。
- 全域忽略區（系統狀態列）寫在程式常數，不用每個 checkpoint 框。
- 差異圖：分群後畫外框 + 箭頭，不逐像素塗色（會蓋掉內容）。
- 忽略區塊用框選工具產生（百分比座標），不手算。
- 動態內容長度改變造成版面位移 → 已知限制：用最壞情況長度的資料建基線、縮小比對範圍、或人工判斷。
- 「元素在不在」用功能斷言，不要靠像素比對。
- 尺寸不同 = `LAYOUT_MISMATCH`，failOnDiff=true 時算失敗（模板已這樣判）；不同型號一定要分基線（`DEVICE_MODEL`）。
- **小螢幕 / 字型縮放跑版**：基線本身若已截字，像素比對抓不到 → 另加「字型縮放（Android font scale、iOS Dynamic Type）× 最小螢幕」測試矩陣，配功能斷言：關鍵文字完整出現（不含「…」省略號）、元素 bounds 未超出父容器 / 螢幕。
- 基線是持久資產要進版控（`.gitignore` 的 `*.png` 規則要加例外）；更新基線由固定一人負責，避免二進位衝突。
- 檢查模式最終判定：任一 failOnDiff=true 的 checkpoint 命中 FAIL/ERROR/MISSING_BASELINE → 失敗。

---

## M11 只重跑失敗 / flaky

- `templates/_summarize_results.py`（rglob 掃描、與報表同一份判定規則）產 `.last_run_status.json`；`templates/run_failed.sh` 只跑 `passed=false`，全綠直接結束。runner 結尾自動呼叫 summarize。
- 前次失敗、這次通過 → `flaky: true`，通知與報表要顯示，不當成乾淨的 PASS。

---

## M12 開發與環境工具

| 工具 | 用途 |
|---|---|
| `setup/setup.sh` | 逐項檢查/安裝（已存在略過、失敗記錄不中斷、最後列未完成項 + log），寫環境變數前備份 |
| `scripts/snap.sh` | 截圖 + 元素表（text / id / clickable / bounds），寫定位器最常用。**沒有本機裝置時**：本機開 Android Emulator（Windows / macOS 皆可）抓元素；或雲端農場的 remote access session + Appium Inspector |
| `scripts/hierarchy_snapshot.sh` | 截圖 + 原生 hierarchy XML + 目前 Activity |
| `scripts/debug_flow.sh` | 以除錯模式跑單支 flow（同 runner 的設定載入） |
| `scripts/setup_test_files.sh` | 推送上傳用測試檔到裝置多個位置 + 授權（套件名可參數化） |

---

## M13 知識層

- `docs/<專案>_使用者操作手冊.md`：給不寫程式的人（每次測試的標準步驟、改哪個資料檔、怎麼看報表、遇到什麼自己處理/什麼要回報）。
- `docs/<專案>_使用教學.md`：給維護者（運作原理、目錄、核心概念、新增品牌/渠道/flow、除錯、已知限制）。
- `.claude/skills/<子系統>/SKILL.md`：每個子系統的設計脈絡、工具實測行為、坑、移植清單；description 寫清楚觸發情境。
- `release-notes/YYYY-MM-DD-<主題>.md`：背景 → 新增/修改/刪除 → 行為變化 → 如何驗證（含「尚未實跑」的範圍）。
- `archive/`：過時文件封存並標「只供查歷史」，不刪除。
- 文件互相矛盾時，在較新的文件寫明以誰為準。

---

## M14 協作與版控

- `.gitignore`：機密、品牌實設定、測試資料、產出（test-results、截圖、log、報表、暫存比對區）、IDE/OS 垃圾；**例外救回**基線圖。範本在 `templates/config-examples.md` 的 `.gitignore` 段。
- 不能用線上 remote 時：git bundle 增量交換（`git bundle create update.bundle last-sync..main` → 對方 `git fetch update.bundle main:<name>-update` → merge → 雙方 `git tag -f last-sync main`）；基準對不上就用 `--all` 全量包。永遠在工作分支改、commit 前看 `git status`。
- 二進位資產（基線）指定擁有者。

---

## M15 CI 整合

- 冒煙 tag 當 merge gate（目標 < 15 分鐘）、完整回歸夜間排程。
- CI 步驟：安裝依賴 → 啟動模擬器（或連裝置農場）→ 注入 secret 產生品牌設定 → `run_suite.sh` → 上傳 `test-results/` 與 `report.html` artifact → 以 runner exit code 決定成敗 → 通知摘要。
- 無法在 CI 跑裝置時，CI 至少跑：語法檢查、定位器 key 一致性、labels 完整性。

---

## M16 規格匯入與追溯

- 先問清：檔案、sheet、欄位對照、哪些狀態值代表「不做」。
- 過濾掉不做的列並在原檔標色 + 註記原因；合併儲存格代表同一情境（取左上角值）。
- 每 N 支（例如 20）一個 batch，全綠才交付；flow 帶 case id tag 方便追溯。
- 語意不明的測項立刻問，不要做完再一次丟。
- **受控文件不可改**（法規文件、正式測項表）：改用「既有對應模式」—— 原檔唯讀，另產生對照表 `docs/traceability.csv`（需求 ID ↔ 測項列 ↔ 自動化 test id ↔ 狀態：已自動化 / 不做（原因）/ 人工），不在原檔標色。
- 已有自動化時先做**缺口分析**：既有測試對應到哪些測項列、哪些測項沒有自動化，排出下一批。
- 非 ASCII（日文全形、中文）測項：讀檔指定編碼（CSV 用 UTF-8 BOM / Shift_JIS 要確認），test id 用 ASCII，顯示名稱保留原文。

- **Azure Test Plans 回寫**：flow / test 用 `TC<id>` tag；REST API 建 test run（指定 plan / suite 的 test points）→ 更新 results（outcome：Passed / Failed / Blocked / NotExecuted）；Azure 的「associated automation」只支援 .NET，其他語言一律走 REST 或用 PublishTestResults 上傳 JUnit 後手動關聯。PAT 放 variable group。
- **TestRail 回寫**：flow 用 `C<id>` tag；`templates/push_testrail.py` 依 `.last_run_status.json` 建 run（名稱帶 target + build）→ `add_results_for_cases`（PASS→Passed、FAIL→Failed、BLOCKED→Blocked、flaky 加註解）。Zephyr 同理，改 API。
- **Zephyr Scale 回寫**：test case 用 `zephyr:PROJ-T123` tag（或測試名稱含 case key）；用 Zephyr Scale API 的 automations 端點直接上傳 JUnit XML（可自動建 test cycle）或 custom format；token 放 CI secret。
- **Xray 回寫**：test issue 用 `xray:PROJ-456` tag；用 Xray REST `POST /api/v2/import/execution/junit`（Cloud，client_id/secret 換 token）上傳 JUnit，或 `/import/execution` 上傳 Xray JSON（可指定 testExecutionKey、testPlanKey、環境）；Test Execution issue 本身就是持久的歷史紀錄。也可用工具的 JUnit 輸出（Maestro `--format junit`）匯入。

---

## M17 稽核證據與追溯（受監管產業）

**何時納入**：Q-P5-3=e（法規要求證據與保存年限）。
**內容**：
- 每個 case 的證據包：每一步截圖（**PASS 也要**，不只失敗截圖）、步驟清單、App build 版本、裝置型號 / OS、環境、開始結束時間、結果。
- 遮罩後才歸檔（同 M9 規則）。
- `manifest.json`：每個檔案 SHA-256；整包再算一次 hash 記錄在 CI 紀錄 → 防竄改。
- 轉存內網保存區（WORM 或有保存年限設定的儲存），`test-results/` 只是暫存。模板 `templates/archive_evidence.sh`。
- 追溯矩陣：需求 ID ↔ 測項 ↔ 自動化 test id ↔ 每次執行結果與證據包位置（M16 的對照表 + 執行結果合併）。
**證據報告變體**（Q-P6-1=f，驗收機關要正式文件）：
- 列印用版面：報表加 `@media print`（模板已內建：列印時所有卡片展開、隱藏按鈕）；PASS 的 case 也要有關鍵步驟截圖（證據模式下逐步 `takeScreenshot` / Listener 每步截圖，報表全部內嵌）；封面頁放 App build、環境、裝置清單、執行期間、追溯矩陣摘要。
- 轉 PDF：內網 headless Chromium（`chromium --headless --print-to-pdf`）或 Playwright `page.pdf()`；要長期保存用 PDF/A；**內嵌字型**（Noto 系列涵蓋 CJK、泰米爾、天城文等），否則非拉丁文字會變方框。
- 簽章：PAdES 數位簽章（例如 pyHanko），私鑰放 HSM / 機密庫，憑證用驗收方信任的 CA（資料駐留要求時用境內 CA），加時間戳（TSA）。SHA-256 manifest 只能證明沒被竄改，**不能**證明是誰簽的。
- 區分「系統產出的簽章」（證明報告是自動化產出、未被修改）與「人員 sign-off」（測試負責人 / 驗收人簽核，通常走機關自己的流程）。
- 格式、簽章方式、保存位置都先跟驗收方確認，寫 ADR。
**注意**：Maestro 的步驟截圖要開啟對應輸出（或在關鍵步驟 `takeScreenshot`）；Appium 由 Listener 每步截圖。

---

## M18 裝置池與並行執行

**何時納入**：Q-P5-1=b/d/e 且 ≥ 2 台裝置，或執行時間超過預算。
**規則**：
- 鎖裝置：CI（Jenkins Lockable Resources / GitHub concurrency group）或 runner 的裝置鎖（模板 `run_suite.sh` 用 `.locks/<device>`）。
- 每台獨立輸出：`test-results/<ts>_<device>/`；狀態檔 key `<flow>@<device>`（模板已實作）；最後合併報表（讀多個 run 目錄）。
- 同一 checkout 不能同時跑「不同 target」（會搶 `active` 切換）→ 用 git worktree / 不同 agent。
- **品牌 × 平台矩陣抽樣**（白牌多時組合數爆炸）：PR 只跑 1～2 個代表品牌（功能最多 / 最常出事）× 雙平台 smoke；夜間輪替不同品牌的回歸；發版前全品牌 smoke + 代表品牌完整回歸；品牌專屬功能（features 旗標）由有該功能的品牌負責。
- 分配策略：smoke 跑 1～2 台代表性裝置；回歸把 case 分散到所有裝置（依 tag 或 case 分片），相容性矩陣（OS × 螢幕）另排夜間。
- 健康檢查：開跑前檢查電量、解鎖、網路、空間、系統更新彈窗；不健康的裝置排除並在報表標示。
- **受測硬體池**（IoT / 周邊裝置，`capability-catalog.md` #14）：硬體也要獨佔鎖（CI resource_group / runner 鎖，命名 `hw-<id>`）、健康檢查（在線、韌體版本）、每輪前重置到已知狀態（解綁、恢復出廠、斷電重開）；手機 × 硬體的配對關係寫在設定檔。
- Appium：每個 session 不同埠（見 `appium-pitfalls.md` #7）；一台 Mac 驅動的 iOS 實機數有限。
- 狀態檔 key 是 `<flow>@<target>`（brand/env/platform/locale/flags/form_factor/device），`run_failed.sh` 依每筆 target 還原環境重跑。

---

## M19 無障礙（a11y）自動檢查

**何時納入**：Q-P4-6 勾 a11y，或有法規 / 合約要求（WCAG 2.1 AA、各國無障礙法規）。
**三層**：
1. **App repo 內的稽核測試**（最有效，跟開發 CI 一起跑）：Flutter widget test `expect(tester, meetsGuideline(labeledTapTargetGuideline / textContrastGuideline / androidTapTargetGuideline / iOSTapTargetGuideline))`；Android Espresso `AccessibilityChecks.enable()`（ATF）；iOS XCUITest `try app.performAccessibilityAudit()`（Xcode 15+）。
2. **UI 流程中的 hierarchy 掃描**（需 spike）：Maestro flow 內沒有 dump hierarchy 的指令 → 由 runner / 主機端在 flow 停在目標頁時跑 `maestro hierarchy`（或 Appium `getPageSource`）再分析；WebView 頁面用 axe-core（Appium webview context 注入或 Playwright 測 Web 層）。在主流程經過的每頁抓 hierarchy，檢查可點元素都有 accessibility label、尺寸 ≥ 48dp / 44pt、沒有重複 label；輸出違規清單。
3. **字型縮放 × 最小螢幕矩陣**：最大字型（Android font scale 2.0 / iOS AX5）跑主流程，斷言關鍵文字完整、無截字（見 M10）。
**報表**：a11y 結果獨立一區（違規數、頁面、元素），不混進功能 PASS/FAIL；先觀察、再把「新增違規」設成門檻。
**限制**：顏色對比、讀屏順序只能部分自動化，剩下列人工檢查清單（逐項對應 WCAG 準則編號，例如 1.4.3、2.5.5）。**法規強制時，門檻以第 1 層（App repo 內的 ATF / `performAccessibilityAudit` / `meetsGuideline`）為主**，第 2、3 層補流程覆蓋。

---

## 跨工具對照表

| 概念 | Maestro | Appium | Detox | Espresso / XCUITest | Playwright（Web/Hybrid） |
|---|---|---|---|---|---|
| 子流程 / 共用片段 | `runFlow` + `env` | Page Object / helper 函式 | helper 函式 | Robot pattern | Page Object / fixture |
| 定位器外置 | `runScript` 載入 JS 設 `output.selector` | JSON/YAML + Page Object | testID 常數檔 | resource id / accessibilityIdentifier 常數 | locator 檔 |
| 資料驅動 | `repeat.while` + `output` | 參數化測試（pytest/TestNG/JUnit） | `describe.each` | 參數化 / XCTest 迴圈 | `test.describe` 迴圈 |
| 平台/品牌切換 | runner 切 `active` symlink | capabilities + 設定檔選擇 | configurations | build flavor / scheme | project config |
| 等錨點 + 清彈窗 | `extendedWaitUntil optional` + 條件 | WebDriverWait + 自訂 ExpectedCondition | `waitFor().withTimeout` | IdlingResource / `waitForExistence` | `locator.waitFor` + `page.on('dialog')` |
| 後台 API | `runScript` 內 `http.post` | 測試語言的 HTTP client | Node fetch | OkHttp / URLSession | `request` fixture |
| 截圖 | `takeScreenshot` | `getScreenshotAs` | `device.takeScreenshot` | `ScreenshotProvider` / `XCUIScreen` | `page.screenshot` |
| 原生結果 | `commands.json` + `maestro.log` | 測試框架報告 | Jest 報告 | JUnit XML / xcresult | JSON / HTML reporter |

不論工具，M1、M2、M9、M10、M11、M13、M14 的設計原則都相同；只有「片段 / 定位器 / 等待」的寫法換成該工具語法。

---

## M20 結果歷史與趨勢

**何時納入**：Q-P6-1=e，或 CI artifact 保留期短、要回顧品質趨勢。
- `templates/_summarize_results.py` 每次 run 追加一行到 `history/runs.jsonl`（時間、target、build、total / failed / blocked / flaky、每支 flow 狀態）。
- `templates/trend_report.py`：每週通過率（排除 BLOCKED）、最常失敗 / 最常 flaky 的 flow → `history/trend.csv` + `trend.html`（無外部資源）。
- `history/` 要放持久位置：進版控（小檔可）、雲端儲存、CI cache，或改寫入 TCM（Xray Test Execution、TestRail run 本身就是歷史）/ 試算表。
- 通知可附上本週通過率與相較上週的變化。
