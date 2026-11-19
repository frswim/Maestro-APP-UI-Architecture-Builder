# 訪談題庫（Lite：12 題）

★ = 必答。每輪最多 4 題、選項化、永遠允許「其他」。能從 repo 推出的跳過。
典型分 4～6 輪：P1+P2 → P2+P3 → P4 → P5+P6。

---

## P1 現況

### ★ Q1｜目前有沒有在跑的 App UI 自動化？
- a. 完全沒有
- b. 有零星腳本（例如幾支 Maestro flow，本機手動跑），沒有固定架構
- c. 有完整框架、固定在跑
- d. 曾經有，已停用（原因？）

註：開發在 App repo 的單元 / 元件測試不算 b（記錄成可測性資產：testID 等）；但 XCUITest / Espresso 寫的端到端 UI 流程算 b 或 c。

影響：
- a → 新建路線（`rollout-plan.md`）。
- b → 新建路線 + **收編**：做「腳本盤點表」（每支 → 對應主流程 / 可抽共用的步驟 / 寫死的 id 文字帳號 / 處置：收編、重寫、刪除），舊腳本在新結構跑通前保留可執行。
- c → 已有框架的評分、改造路線屬完整版；Lite 只能在「現行工具是 Maestro」時，把本架構的核心模組逐步套上去，並在提案寫明「改造路線未涵蓋」。
- d → 停用原因就是第一優先要解的問題（常見：不穩 → M6；沒人看報表 → M9；維護太累 → M2/M3/M4）。

---

## P2 產品與平台

### ★ Q2｜App 類型與平台？（可複選）
- a. Android 原生　b. iOS 原生　c. React Native / Flutter　d. Hybrid（大量 WebView）

影響：
- b → 需要 macOS 執行機與 iOS 模擬器（實機另需簽章，先 spike）。
- c → 確認開發是否已埋 testID：React Native `testID`；**Flutter 要用 `Semantics(identifier: ...)`（Widget `Key` 外部工具看不到）**；沒有就跟開發約定命名規則。Kotlin Multiplatform（UI 各自用 Compose / SwiftUI）算 a + b；Jetpack Compose 要開 `testTagsAsResourceId = true` 才看得到 `testTag`。
- d → M6 必納入；**HTML 的 `data-testid` 不會出現在 Maestro 看得到的 accessibility tree**，要請開發用 `id` / `aria-label`；WebView 占比很高（例如 Ionic / Capacitor）時，Maestro 可能不是最佳工具，列為待 spike 並註明完整版有 Appium webview 做法。

### Q3｜同一條流程要跑在哪些「變體」上？
- a. 只有一個 App、一種使用者
- b. 多個品牌 / 白牌 App（不同 applicationId）
- c. 多種帳號類型 / 地區（同 App）
- d. 多語系

影響：a → brand 參數用 `default`，仍保留 `active/` 結構；b → 品牌設定檔 + 定位器依品牌分目錄（Lite 提供基本做法，品牌很多時的 `_base` + 差異、矩陣抽樣屬完整版）；c → 差異放測試資料（帳號 → case）；d → 優先用 id 定位，文字定位依語系分值（進階 locale 維度屬完整版）。

### Q4｜有哪些環境？
- a. 只有正式　b. 測試 + 正式　c. 只有測試環境

影響：b/c → `config/env/<env>.yaml` 疊加（runner `TARGET_ENV=`）；a/b → **正式環境只跑唯讀冒煙**（不下單、不付款、不寄信），用 `prod-safe` tag 區分。

---

## P3 軟體流程

### ★ Q5｜發版節奏與 CI？
- 節奏：a. 固定 sprint　b. 持續交付　c. 月 / 季大版　d. 不固定
- CI：GitHub Actions / 其他 CI / 沒有 CI

影響：a → sprint 末跑完整回歸、每天跑冒煙；b → 冒煙（< 15 分鐘）當 merge gate；c → 發版前大回歸 + hotfix 套件；GitHub Actions → `templates/ci-github-actions.yml`；其他 CI → 照 runner 一行指令自行接（其他 CI 模板屬完整版）；沒有 CI → 本機排程（cron / launchd）+ 通知。

### Q6｜測項在哪裡？誰維護自動化？
- 測項：a. Excel / Sheet　b. 測項管理系統　c. Jira AC　d. 沒有
- 維護：a. QA 自動化工程師　b. 手測 QA 為主　c. 開發

影響：a/b/c → flow 加測項 id tag（例如 `C123`、`req:PROJ-1`）方便追溯（自動回寫測項系統屬完整版）；d → 先跟使用者列出主流程清單；維護者 b → 強調「改資料檔不碰 flow」與操作手冊（M13）。

---

## P4 範圍與資料

### ★ Q7｜第一條要自動化的主流程？（從打開 App 到結束）主流程裡有沒有 App 外的步驟？
App 外步驟選項：OTP / 驗證信、後台審核、付款 / 第三方頁、檔案上傳、推播、權限對話框、定位、其他。

追問：這條流程有幾種變體？每種變體的 UI 步驟一樣嗎？
影響：
- 變體 ≥ 3 且步驟不同 → M4 資料驅動 + 依 type 分派；步驟相同只差參數 → 單純參數化。
- 每個 App 外步驟 → 查 `capability-catalog.md` 對應列，寫進提案（做法 / 模組 / 風險）。表上沒有的 → 鐵則 2 spike。
- 這條流程就是 MVP 的驗收標的。

### ★ Q8｜測試帳號與資料怎麼來？
- a. 固定幾組帳號，人工準備
- b. 可用 API / 後台建立
- c. 每次測試會消耗資料（餘額、庫存）
- d. 環境會定期重置

影響：資料檔結構「帳號 → case」；b → M7 準備資料；c → 流程要有補資料 / 清理步驟並寫明相依；d → 開跑前帳號健康檢查，失敗時訊息以 `[BLOCKED]` 開頭（報表顯示 BLOCKED，不算 App 缺陷）。

### Q9｜App 會不會不定時跳出彈窗？（活動、評分、引導、更新、權限）
- a. 很多　b. 偶爾　c. 幾乎沒有

影響：a/b → M6 必納入；優先序：①請開發提供測試版開關關掉 ②測試帳號設定成不會觸發 ③M6 彈窗清單自動關。系統層 UI（評分對話框、權限）不一定能被清單關掉。建議跟前端約定所有阻擋型彈窗的關閉鈕統一一個 id。

---

## P5 裝置與限制

### ★ Q10｜在什麼裝置上跑？執行機是什麼 OS？
- 裝置：a. 本機模擬器　b. 實體裝置（USB）　c. 雲端裝置農場
- 執行機：macOS / Linux / Windows

影響：
- a/b → Lite 的 runner 直接可用；多台實機要並行時，每台各跑一個 runner（runner 有裝置鎖），進階裝置池屬完整版。
- c → **雲端農場屬完整版**；Lite 先在本機 / 實機跑通，提案列「雲端化」為之後項目。
- Windows → bash 腳本建議在 WSL2 執行（Git Bash 沒有 `pkill`，watchdog 會失效）；iOS 需要 macOS。
- 低階裝置 / 慢網路 → `TIMEOUT_SCALE=1.5～2` 放大等待上限。

### ★ Q11｜機密與網路規定？
- a. 機密不得進版控　b. 不得連外 / 只能內網　c. 只能用合成測試資料　d. 無特殊要求

影響：a → 品牌設定實檔不進版控，只放 `.yaml.example`，CI 用 secret 產生；b → 報表設 `REPORT_INLINE_ASSETS=1`（bootstrap 放 `config/vendor/`，否則不連外的陽春版）、通知走內網（`NOTIFY_ALLOWED_HOSTS` 或 `NOTIFY_FORMAT=email`）、不用 Maestro AI 指令（會送截圖到雲端）、設 `MAESTRO_CLI_NO_ANALYTICS=1`、CLI 離線安裝；c → 測試資料全用假資料。受監管產業（金融、醫療）的遮罩、證據保存、簽章屬完整版，提案要明確列出。

---

## P6 報表

### ★ Q12｜誰看結果？怎麼通知？什麼算失敗？
- 讀者：a. QA 自己　b. 轉寄給 PM / 開發（單檔 HTML）
- 通知：Slack 類 / Teams / LINE / email / 不需要
- 擋版：a. 主流程失敗就擋　b. 只有冒煙擋　c. 只報告

影響：M9 一律做；`REPORT_LANG`（zh-Hant / ja / en / ko）= 讀者語言；通知 → `templates/notify.sh`（`NOTIFY_FORMAT`）；a/b → exit code 當 gate，搭配 M11 重跑（重跑才通過標 flaky，不當乾淨 PASS）。

---

## 收尾
整理成 `templates/intake-summary.md` 格式給使用者確認 → 列待確認假設 → 進 P7（`decision-matrix.md`）。
