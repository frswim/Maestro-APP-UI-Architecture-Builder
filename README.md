---
name: app-test-architecture-builder
description: 為任何產業的公司「從零建立或擴充」App（Android / iOS / 跨平台 / Hybrid WebView）UI 自動化測試架構的引導式方法。先依訪談 pipeline 跟使用者對答（現行自動化現況、軟體流程、平台、測試範圍、基礎設施、報表需求），再依決策矩陣挑選架構模組、產出架構提案並分階段落地。當使用者說「幫公司建自動化測試架構」、「規劃 App 自動化」、「評估/改造現有自動化框架」、「把這套測試架構移植到新專案/新產品」、「我們要導入 UI 自動化，從哪開始」時啟動。不適用於：在既有、已定案的專案裡只修單一 flow 或單一 selector（那種情況用該專案自己的 skill）。
---

# App 自動化測試架構建構法（通用版）

這份 skill 讓 AI 依「訪談 → 決策 → 提案 → 分階段落地 → 驗證」的流程，替任何公司搭出符合其需求的 App UI 自動化測試架構。
架構是**模組化**的：不是每家公司都需要全部模組，由訪談結果決定加或減。

內容來源：一套實際上線、跨多品牌、多渠道、每天跑回歸的 Maestro 專案（已去識別化，見 `references/reference-implementation.md`）。工具換成 Appium / Detox / Espresso / XCUITest / Playwright 也適用，對照表在 `references/architecture-modules.md` 末尾。

---

## 零、使用這份 skill 的鐵則

1. **先問，再設計，最後才寫檔**。訪談沒走完（P1～P6 的 ★ 必答題 + P5.5 工具選型）不准產生架構檔案。例外：使用者明確說「先給我最小可跑的骨架」→ 走「快速模式」（見第三節）。
2. **沒把握的工具 / 平台 / 能力，先做相容性 spike 再寫進提案**：本 skill 的對照表會過時，也不可能涵蓋所有組合。遇到表上沒有、或「相容表 / 目錄」標示需查證的組合（某農場 × 某工具、某框架的定位方式、某系統能力），提案中列為「待 spike」，階段 0 用一條 hello-world 測試在實際環境驗證，結果寫 ADR；不得在未驗證下宣稱可行。
3. **能從 repo 推得出來的不問**。如果使用者給了 repo 路徑或你在 repo 裡，先掃描（第二節 P0）再問；問題要附上你看到的事實（例如「我看到你們用 GitHub Actions 跟 Appium 1.x，要沿用嗎？」）。
4. **每次最多問 4 題、選項化**（用 AskUserQuestion，沒有這個工具就用編號清單），推薦選項放第一個並標「（建議）」。不要一次丟 20 題。
5. **已有現行架構（Q-P1-1=c/d）→ 預設「增量改造」不是「重寫」**；只有零散腳本（b）→ 新建路線 + 收編盤點。評分低時走「新舊並行、逐步替換」（`references/interview-pipeline.md` 路線判定、`references/rollout-plan.md` 改造路線）；只有使用者明確要求，或「資產低且沒人熟現行工具」時才提重寫。
6. **任何範例、模板、產出檔案都不得含真實機密**：帳密、token、內部網址、真實帳號 id、真人姓名、客戶名稱。一律用 `<placeholder>` 或 `example.com`。機密走本機不進版控的檔案或 CI secret（模組 M2）。
7. **每個設計決定都要寫下「為什麼」**（ADR，模板在 `templates/architecture-decision-record.md`）。之後的 AI 才不會重新踩坑或推翻已確認的決定。
8. **不要過早抽象**：同樣的骨架第三次出現才抽共用；先讓一條主流程端到端跑通，再複製到其他業務線。
9. 用使用者的語言回覆（使用者用中文就用中文）。

---

## 一、整體 Pipeline

```
P0 開場與現況掃描（讀 repo / 文件，不問就能知道的先知道）
 │
P1 現行自動化現況 ──┬─ 沒有 → 走「新建」路線
 │                   └─ 有   → 評分（可維護性 / 穩定性 / 覆蓋 / 報表）→ 決定「增量改造 / 局部重構 / 重寫」
P2 產品與平台（App 類型、平台、多品牌/多租戶、語系、環境）
P3 軟體流程（開發模式、發版節奏、分支策略、CI/CD、測項管理、誰寫測試）
P4 測試範圍與資料（要自動化哪些流程、測試帳號/資料來源、後台依賴、第三方頁、Mock）
P5 基礎設施與限制（裝置、網路、版控/資安規定、預算、人力技能）
P5.5 工具選型（依 App 技術 × 誰寫 × 裝置來源 × 有無 macOS，寫 ADR；不可直接套預設工具）
P6 報表與品質門檻（誰看報表、失敗分類、通知、視覺回歸、flaky 政策）
 │
P7 決策：用 references/decision-matrix.md 把答案映射成「模組清單 + 每個模組的變體」
P8 提案：輸出架構提案（目錄樹、模組、取捨、分階段計畫、風險）→ 使用者確認
P9 落地：依階段建檔（MVP → 擴充），每階段跑驗證清單
P10 交付：知識層（skill / 使用手冊 / release note）+ 交接
```

每一階段的題庫、追問條件、答案對架構的影響：`references/interview-pipeline.md`。
答案 → 模組的對照：`references/decision-matrix.md`。
模組本體（目的、檔案、設計規則、坑）：`references/architecture-modules.md`。

### 對答節奏

- 一輪問 1～4 題。每輪結束後用 2～3 行回報「目前已知 / 推論出的模組影響 / 下一輪要問什麼」，讓使用者知道為什麼要問。
- 使用者回答「不知道」：給預設值並標記為「假設」，寫進提案的「待確認假設」清單，不要卡住。
- 使用者回答跟前面矛盾：立刻指出並請他選一個，不要自行猜。
- 訪談結果寫成 `docs/test-architecture/intake.md`（模板 `templates/intake-summary.md`），提案前給使用者看一次。

---

## 二、P0 開場：先掃描再開口

有 repo 時先做（唯讀）：

| 要找的東西 | 怎麼找 | 對應問題 |
|---|---|---|
| 現有自動化框架 | `find . -name "*.yaml" -path "*flows*"`、`grep -rl "appium\|detox\|XCUITest\|Espresso\|maestro" --include=*.{js,ts,java,kt,py,swift,yaml,json} .` | P1 |
| App 類型 | `build.gradle`、`Podfile`、`package.json`（react-native / expo）、`pubspec.yaml`（Flutter）、WebView 用量、平板版面（`sw600dp`、iPad size class） | P2 |
| 可測性 / 特殊能力 | testID / `Semantics(identifier` / accessibilityIdentifier 數量；feature flag SDK、相機、WebRTC、推播、生物辨識、IAP 套件 | Q-P2-6、Q-P2-7、Q-P4-6 |
| CI | `.github/workflows`、`Jenkinsfile`、`.gitlab-ci.yml`、`bitrise.yml`、`azure-pipelines.yml` | P3 |
| 測項來源 | `*.xlsx`、`*.csv`、TestRail/Xray/Zephyr 匯出檔 | P3/P4 |
| 多品牌/flavor | Android `productFlavors`、iOS schemes/targets、多個 applicationId | P2 |
| 機密處理 | `.env*`、`*.yaml` 內的 password、`.gitignore` 規則 | P5 |

沒有 repo：直接從 P1 開始問。

開場白範本（照實情調整）：
> 我會分 6 個主題問你，大約 5～8 輪，每輪最多 4 題。問完我會給一份架構提案讓你確認，確認後才開始建檔。我先看了 repo，已知：<列事實>。

---

## 三、快速模式（使用者趕時間時）

問 2 輪（共 7 題）：
- 第 1 輪：Q-P1-1（現行自動化）、Q-P2-1 + Q-P2-9（平台/App 類型、是否多支 App 互動）、Q-P3-4（誰維護、會什麼語言 → 決定工具語言）、Q-P5-1 + Q-P5-2（裝置來源、執行機 OS → 決定 runner 模式）。
- 第 2 輪：Q-P4-1（第一條主流程）、Q-P4-4 精簡版（主流程有沒有 App 外步驟：OTP / 後台審核 / 付款 / 另一方角色）；涉及金流、位置、醫療或其他個資時加問 Q-P5-3。
MVP（與 `decision-matrix.md`「預設組合」相同）：M1 + M2 + M3 + M5 + M9（基本判定 + 單檔 HTML）+ M12（安裝 + 抓元素）+ M13（README + 一份設計文件）+ M14（gitignore）。
**主流程卡在 App 外步驟時**：M7 的對應變體（OTP、後台 API、對方角色 bot）進 MVP；做不到就把 MVP 主流程縮到不需外部步驟的那一段，並在提案寫明。
提案中把所有預設值列為「待確認假設」，第一條主流程跑通後再回頭補問。

---

## 四、核心設計原則（每個模組都要遵守）

這些是參考專案付過代價才換來的原則，提案時要逐條對照：

1. **單一執行入口**：所有測試都經過同一支 runner（M1）。它負責載入設定、切換品牌/平台資源、統一輸出目錄、看門狗、產報表、決定 exit code。使用者不用記任何工具原生參數。
2. **三種東西分開放**：「環境/品牌設定（扁平 key-value）」、「測試資料（帳號 → case 清單，可巢狀）」、「定位器（頁面 → 元素）」。flow 只放流程邏輯，不寫死任何 id、文字、帳號。
3. **資料驅動取代複製貼上**：同一條流程跑 N 種變體（付款方式、語系、會員等級）→ 一支 flow + 雙層迴圈（帳號 × case）+ 依 `type` 分派到變體專屬片段。新增 case 只改資料檔。
4. **換品牌/平台不改 flow**：flow 永遠讀固定路徑（例如 `active/`），由 runner 依參數把 `active` 指向正確目錄（symlink 或複製）。
5. **任何等待都有上限，整次執行也有上限**：牆鐘截止時間 + 輪數硬上限 + 整體 watchdog。卡死的測試也要結束並產出報表。
6. **不預知彈窗位置**：把「點擊 → 等下一頁錨點」包成共用 helper；錨點等不到才清彈窗；**確實關掉彈窗才重點**（避免重複送單）。彈窗清單放設定檔，新增彈窗不改 flow。
7. **PASS/FAIL 只看阻斷錯誤**：warning 不算失敗；被中斷、被 watchdog 殺掉、沒產生結果檔的執行要判 FAIL 並寫明「執行未完成」。
8. **報表給人看**：失敗要翻成「哪個流程 / 哪個階段 / 等哪個元素」+ 第幾個 case + 失敗截圖；單檔 HTML、圖片內嵌，可以直接轉寄。
9. **後台動作自動化**：需要後台審核、發 OTP、改狀態才能走完的流程，用 API hook 完成（整輪登入一次、session 共用），不要留人工步驟。
10. **視覺回歸是選配、預設關閉**：關閉時連截圖都不做；「建立基線」與「比對」是兩種模式，結果不混在同一份統計。
11. **知識寫下來**：每個子系統一份設計文件（含已踩過的坑），每次重大異動一份 release note，過時文件封存不刪。這份 skill 就是這個原則的產物。

---

## 五、P7～P10：從答案到落地

### P7 決策
打開 `references/decision-matrix.md`，逐題把答案映射成模組與變體。輸出一張表：

| 模組 | 納入？ | 變體 | 依據（哪一題的哪個答案） |
|---|---|---|---|

### P8 提案（給使用者確認的內容）
1. 一段話總結：要解決的問題、範圍、不做什麼。
2. 目錄樹（只列有納入的模組）。
3. 模組表（上面那張）＋每個模組 1～3 句設計重點。
4. 分階段計畫（參考 `references/rollout-plan.md`）：階段 0 環境 → 階段 1 MVP 一條主流程端到端 → 階段 2 資料驅動 + 韌性 → 階段 3 報表/視覺/CI → 階段 4 擴到其他業務線與品牌。每階段寫「完成定義」。
5. 風險與待確認假設。
6. 需要使用者提供的東西（App 安裝包、測試帳號、後台 API 文件、裝置）。

使用者確認前不建檔。使用者要改 → 回到對應的 P 階段補問，更新 intake 與提案。

### P9 落地
- 依 `references/architecture-modules.md` 每個模組的「最小檔案集」建檔，模板在 `templates/`，參考實作在 `references/reference-implementation.md`。
- 每階段結束跑 `references/rollout-plan.md` 的驗證清單（語法檢查、單條流程實跑、故意製造失敗看報表、換品牌/平台跑一次）。
- 單一 flow 修 2 輪（改一次 + 跑一次 = 一輪）還修不好 → 停下來回報使用者，附上證據（log、截圖、hierarchy）。
- 沒有裝置可實跑時，要明說「未實跑驗證」，不可宣稱完成。

### P10 交付
- `docs/`：給操作者的手冊（不會寫程式的人也看得懂）+ 給維護者的教學。
- `.claude/skills/<子系統>/SKILL.md`：每個子系統的設計與坑（讓下一個 AI 接手）。
- `release-notes/`：這次建了什麼、怎麼驗證、已知限制。
- 把 intake.md 與 ADR 留在 repo。

---

## 六、自我審核（交付前 AI 自己跑一遍）

- [ ] 每個納入的模組都能指出是哪一題的答案導致的；每個排除的模組也有理由。
- [ ] Q-P4-6 勾選的每個特殊能力在提案中都有做法、模組、風險（對照 `capability-catalog.md`）。
- [ ] flow / 測試碼裡沒有寫死的 id、文字、帳號、網址（grep 檢查）。
- [ ] 所有等待都有上限；整次執行有 watchdog；動態 retry 次數有合法整數防呆。
- [ ] 報表能區分：阻斷錯誤 / warning / 執行未完成。
- [ ] 機密沒有進版控（`.gitignore` 與實際 `git status` 都看過）。
- [ ] 換一個品牌 / 環境不用改任何 flow；換平台時：同一份 codebase（跨平台框架）不改 flow，雙原生 App 則共用介面、平台各自實作 Page Object / 定位器。
- [ ] 有合規要求時：報表 grep 不到帳號 / 姓名格式；證據包有 manifest；報表與通知沒有外部資源 / 外部主機。
- [ ] 文件寫明了「已驗證 / 未驗證」的範圍。
- [ ] 所有範例都已去識別化（`references/sanitization-checklist.md`）。

---

## 七、檔案索引

| 檔案 | 內容 |
|---|---|
| `references/interview-pipeline.md` | P0～P6 題庫、追問條件、每題對架構的影響、現行框架評分表 |
| `references/decision-matrix.md` | 答案 → 模組 / 變體 的對照、預設組合、常見情境組合 |
| `references/architecture-modules.md` | M1～M20 模組規格（目的、何時納入、最小檔案集、設計規則、常見坑）＋ 跨工具對照表 |
| `references/reference-implementation.md` | 參考專案（Maestro，多品牌金流 App）去識別化後的實作範例與程式片段 |
| `references/maestro-pitfalls.md` | Maestro 實測行為與陷阱（選 Maestro 時必讀） |
| `references/capability-catalog.md` | 32 種特殊能力（App Clip / Instant App、系統錢包 / 票卡、硬體掃描器 / 周邊 intent、長時間流程 / OTA、語音助理帳號連結、flag、a11y、弱網/離線同步、視訊、相機、magic link、OTP、生物辨識、推播、付款、IAP、遊戲引擎 canvas、影音播放、多 App 互動、企業 SSO、MDM、簽名手勢、平板…）的做法優先序、平台限制、模組（Q-P4-6 用） |
| `references/tool-adaptation.md` | 非 Maestro 工具（Appium/Java 等）的模組落地寫法（選其他工具時必讀） |
| `references/appium-pitfalls.md` | Appium 實務陷阱（XPath、並行埠、WDA 簽章、生物辨識、推播） |
| `references/rollout-plan.md` | 分階段落地計畫、每階段完成定義與驗證清單 |
| `references/sanitization-checklist.md` | 去識別化檢查清單（寫範例、交付前用） |
| `references/audit-history.md` | 這份 skill 的模擬審計紀錄與修正點（改 skill 前先看） |
| `templates/intake-summary.md`、`templates/architecture-decision-record.md` | 訪談摘要、設計決策紀錄模板 |
| `templates/config-examples.md` | 品牌設定、定位器、測試資料、labels、checkpoint settings、`.gitignore` 範本 |
| `templates/run_suite.sh` | M1 單一入口（含 watchdog、active 切換、報表、exit code） |
| `templates/wait_anchor_or_dismiss.yaml`、`wait_anchor_retap.yaml`、`dismiss_blocking_popups.yaml`、`retry_tap_until_visible.yaml` | M6 韌性 helper（Maestro，可直接複製到 `subflows/common/`） |
| `templates/ui_diff_checkpoint.yaml`、`ui_diff_check.py`、`ui_diff_define_ignore.py` | M10 視覺回歸 |
| `templates/failure_rules.py`、`generate_report.py`、`_summarize_results.py`、`run_failed.sh` | M9 判定與報表、M11 重跑名單與 flaky 標記（複製到 `scripts/`；頁面名稱讀 `selector_labels.json` 的 flow keys） |
| `templates/flow_index.py`、`templates/push_testrail.py`、`templates/requirements.txt` | flow 名稱/檔名 → 路徑與 tags 索引（報表與重跑共用）；TestRail 回寫；Python 相依 |
| `templates/trend_report.py` | M20 每週通過率趨勢（讀 `history/runs.jsonl`） |
| `templates/notify_payload.py` | notify.sh 用的 payload 產生器（Slack 類 `{text}` / Teams Adaptive Card） |
| `templates/notify.sh`、`templates/ci-github-actions.yml`、`templates/ci-gitlab.yml`、`templates/Jenkinsfile`、`templates/azure-pipelines.yml`、`templates/bitbucket-pipelines.yml` | 結果通知（webhook + 主機白名單）、CI 管線（GitHub Actions：模擬器 + 雲端農場骨架；Jenkins：內網實機 lab + Vault + 裝置鎖） |
| `templates/device_health_check.sh` | M18 裝置健康檢查（電量、空間、鎖屏、網路；輸出健康裝置清單） |
| `templates/archive_evidence.sh` | M17 證據歸檔（遮罩 → SHA-256 manifest → 打包上傳內網保存區） |

模板適用範圍：`*.yaml` helper 只適用 Maestro；`run_suite.sh` 是 Maestro 本機模式（雲端農場見 M1「雲端模式」）；`failure_rules.py` / `generate_report.py` 讀 Maestro 的 log 格式 —— 換工具不是「改兩段」，而是改成讀該工具的結構化結果（`tool-adaptation.md` §3），HTML 版型、遮罩、i18n、`ui_diff_check.py` 可沿用。Python 腳本需 Python 3.9+。

模板之間的路徑與命名契約（改名要一起改）：
- 定位器一律掛 `output.selector.<page>`，flow 內寫完整路徑 `${output.selector.<page>...<leaf>.text|id|point}`；`<page>` 要列在 `selector_labels.json` 的 `flow`。
- `.last_run_status.json` 的 key 是 `<flow>@<target>`（非 Maestro 的 `*.result.json` 必須帶 target 欄位，見 `tool-adaptation.md` §3.1）；結果資料夾名稱 = flow 的 `name:`，沒有 `name:` 時 = 檔名（`flow_index.py` 兩種都建索引）。
- 迴圈變數固定叫 `output.currentCase = output.currentAccount.cases[output.caseIndex]`、`output.currentType`（報表靠這兩個字串算 case tag）。
- helper 檔名 `wait_anchor_or_dismiss` / `retry_tap_until_visible` 與 env key（`anchor_text`…）被報表反查使用；新增 helper 要加進 `generate_report.py` 的 `_HELPER_FLOW_RE` / `_HELPER_ENV_KEYS`。
- checkpoint 截圖名 `chk_<name>`；基線路徑 `config/ui_baseline/<baseline_key>/<name>/`，`baseline_key` 由 runner 組成 `brand/platform/form_factor[/locale][/flags][/model]`。
