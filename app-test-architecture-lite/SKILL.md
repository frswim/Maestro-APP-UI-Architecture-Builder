---
name: app-test-architecture-lite
description: （免費精簡版）用 Maestro 為公司「從零建立」App（Android / iOS / React Native / Flutter / Hybrid）UI 自動化測試架構的引導式方法：先跟使用者對答（現況、平台、軟體流程、測試範圍、裝置、報表），再依決策表挑選核心模組、產出提案並分階段落地。當使用者說「幫公司建 App 自動化測試」、「用 Maestro 導入 UI 自動化」、「規劃 App 自動化從哪開始」時啟動。不適用於只修既有專案的單一 flow。
---

# App 自動化測試架構建構法（Lite 免費版）

這份 skill 讓 AI 依「訪談 → 決策 → 提案 → 分階段落地 → 驗證」的流程，用 **Maestro** 替一家公司搭出可以每天穩定跑、失敗看得懂的 App UI 自動化架構。

Lite 涵蓋**核心模組**：單一執行入口、設定分層、定位器外置、資料驅動迴圈、共用片段、彈窗與等待韌性、後台 API hook（基本）、結果判定與報表、只重跑失敗、抓元素工具、知識層、版控規則、GitHub Actions。

**Lite 不包含**（屬完整版，遇到時照第五節處理）：Maestro 以外的工具（Appium / XCUITest / Espresso / Detox）、雲端裝置農場、改造既有框架的評分與路線、視覺回歸 UI Diff、Mock、測項管理回寫、稽核證據、裝置池並行、無障礙檢查、趨勢報表、多品牌 / 多語系 / feature flag 的進階做法、32 種特殊能力完整目錄、其他 CI 模板。

內容來源：一套實際上線、每天跑回歸的 Maestro 專案（已去識別化，見 `references/reference-implementation.md`）。

---

## 零、鐵則

1. **先問，再設計，最後才寫檔**。★ 必答題沒問完不准產生架構檔案（快速模式見第三節）。
2. **沒把握的組合先 spike**：遇到本 skill 沒寫到、或標示需查證的情況（某裝置、某系統對話框、某 App 技術的定位方式），提案列為「待 spike」，階段 0 用一條 hello-world flow 在實際裝置上驗證，結果寫 ADR；不得在未驗證下宣稱可行。
3. **能從 repo 推得出來的不問**；問題附上你看到的事實。
4. **每輪最多 4 題、選項化**（用 AskUserQuestion，沒有就用編號清單），建議選項放第一個並標「（建議）」。
5. **範例與產出不得含真實機密**：帳密、token、內部網址、真實帳號、人名一律用 `<placeholder>` / `example.com`；機密放不進版控的本機設定或 CI secret。
6. **每個設計決定寫下「為什麼」**（`templates/architecture-decision-record.md`）。
7. **先讓一條主流程端到端跑通**，再擴充；同樣的骨架第三次出現才抽共用。
8. 用使用者的語言回覆。

---

## 一、Pipeline

```
P0 開場與掃描（有 repo 先讀）
P1 現況：有沒有自動化
P2 產品與平台
P3 軟體流程（節奏、CI、測項來源、誰維護）
P4 範圍與資料（第一條主流程、測試資料、App 外步驟、彈窗）
P5 裝置與限制（裝置、執行機、機密規定）
P6 報表（誰看、怎麼通知、什麼算失敗）
P7 決策：references/decision-matrix.md 答案 → 模組
P8 提案 → 使用者確認後才建檔
P9 分階段落地：references/rollout-plan.md
P10 交付：使用手冊、維護說明、設計文件
```

題庫：`references/interview-pipeline.md`。模組規格：`references/architecture-modules.md`。
訪談結果寫成 `docs/test-architecture/intake.md`（`templates/intake-summary.md`），提案前給使用者確認。每輪結束回報「已知 / 推論出的模組 / 下一輪要問什麼」；使用者答「不知道」就給預設值並列為「待確認假設」。

---

## 二、P0 開場

有 repo 時先唯讀掃描：現有 Maestro / 其他測試（`*.yaml` flows、`appium`、`XCUITest`、`Espresso` 字樣）、App 類型（`build.gradle`、`Podfile`、`package.json`、`pubspec.yaml`）、CI 設定、測項檔（`*.xlsx` / `*.csv`）、`testID` / `accessibilityIdentifier` 用量。

開場白：「我會分 6 個主題問你，大約 4～6 輪，每輪最多 4 題。問完給你一份架構提案確認，確認後才開始建檔。」

---

## 三、快速模式

使用者說「先給我最小可跑的骨架」時，只問 1 輪 4 題：Q1（現況）、Q2（平台與 App 類型）、Q10（裝置與執行機 OS）、Q7（第一條主流程與 App 外步驟）；涉及金流、醫療或其他個資時，第 2 輪補問 Q11。
MVP = M1 + M2 + M3 + M5 + M6 + M9 + M12 + M13 + M14。主流程卡在 App 外步驟（OTP、後台審核）時，M7 對應做法進 MVP，做不到就把 MVP 縮到不需外部步驟的那一段。所有預設值列為「待確認假設」。

---

## 四、核心設計原則

1. **單一執行入口**：所有測試經過 `scripts/run_suite.sh`，負責載入設定、切換 `active`、統一輸出目錄、watchdog、產報表、決定 exit code。
2. **三種東西分開放**：設定（扁平 key-value）、測試資料（帳號 → case）、定位器（頁面 → 元素）。flow 不寫死 id、文字、帳號。
3. **資料驅動取代複製貼上**：同一流程多種變體 → 一支 flow + 迴圈 + 依 `type` 分派變體片段。
4. **任何等待都有上限，整次執行也有上限**。
5. **不預知彈窗位置**：「點擊 → 等下一頁錨點」包成 helper，等不到才清彈窗，確實關掉才重點。
6. **PASS / FAIL 只看阻斷錯誤**；warning 不算失敗；被中斷的執行判「執行未完成」。
7. **報表給人看**：失敗翻成「流程 / 階段 / 目標」+ case + 截圖，單檔 HTML 可轉寄。
8. **知識寫下來**：子系統設計文件、release note、ADR。

---

## 五、遇到 Lite 範圍外的需求

照實告訴使用者「這部分 Lite 沒有現成做法」，並：
- 能用核心模組 + spike 解決的（例如某個特殊系統對話框）→ 照鐵則 2 處理，寫 ADR。
- 需要完整版模組的（Appium / 原生框架、雲端農場、已有框架改造、視覺回歸、稽核證據、裝置池、無障礙、多品牌多語系等）→ 在提案的「之後 / 範圍外」區塊列出，說明完整版（app-test-architecture-builder）有對應做法；**不要硬用 Lite 模板假裝能做到**。

---

## 六、交付前自我審核

- [ ] 每個納入的模組都能指出是哪一題的答案導致的。
- [ ] flow 裡沒有寫死的 id、文字、帳號、網址。
- [ ] 所有等待有上限；runner 有 watchdog。
- [ ] 報表能區分阻斷錯誤 / warning / 執行未完成。
- [ ] 機密沒進版控（`.gitignore` 與 `git status` 都看過）。
- [ ] 文件寫明已驗證 / 未驗證範圍；沒裝置實跑時明說「未實跑」。

---

## 七、檔案索引

| 檔案 | 內容 |
|---|---|
| `references/interview-pipeline.md` | 12 題核心題庫與對架構的影響 |
| `references/decision-matrix.md` | 答案 → 模組、預設組合 |
| `references/architecture-modules.md` | 核心模組規格（M1～M7、M9、M11～M15） |
| `references/capability-catalog.md` | 8 種常見「App 外步驟 / 系統能力」的做法 |
| `references/maestro-pitfalls.md` | Maestro 實測行為與陷阱（必讀） |
| `references/rollout-plan.md` | 分階段落地計畫與完成定義 |
| `references/reference-implementation.md` | 原始案例的去識別化範例 |
| `templates/flows-config.yaml` | Maestro workspace 設定（`flows/config.yaml`，讓子資料夾的 flow 被執行） |
| `templates/run_suite.sh`、`run_failed.sh` | M1 單一入口、M11 只重跑失敗 |
| `templates/wait_anchor_or_dismiss.yaml`、`wait_anchor_retap.yaml`、`dismiss_blocking_popups.yaml`、`retry_tap_until_visible.yaml` | M6 韌性 helper（複製到 `subflows/common/`） |
| `templates/failure_rules.py`、`generate_report.py`、`_summarize_results.py`、`flow_index.py` | M9 判定與報表、M11 重跑名單（複製到 `scripts/`） |
| `templates/snap.sh` | M12 抓元素（截圖 + 元素表） |
| `templates/notify.sh`、`notify_payload.py` | 通知（Slack 類 / Teams / LINE / email） |
| `templates/ci-github-actions.yml` | M15 GitHub Actions（Android 模擬器 + iOS 模擬器） |
| `templates/config-examples.md` | 品牌設定、定位器、測試資料、labels、`.gitignore` 範本 |
| `templates/intake-summary.md`、`architecture-decision-record.md`、`requirements.txt` | 訪談摘要（Q1～Q12）、ADR、Python 相依（放 `scripts/`） |

模板契約（改名要一起改）：
- `flows/config.yaml` 必須有 `flows: ["**"]`（`templates/flows-config.yaml`），否則子資料夾的 flow 不會被執行。
- `dismiss_blocking_popups.yaml` 固定讀 `output.selector.common_page.popup.blocking_dismiss_ids` / `blocking_dismiss_by_title` → 通用頁一定叫 `common_page`、彈窗清單放在 `popup` 底下。
- 定位器掛 `output.selector.<page>`，flow 內寫完整路徑 `${output.selector.<page>...<leaf>.text|id|point}`；`<page>` 要列在 `config/selector_labels.json` 的 `flow`。
- 迴圈變數固定叫 `output.currentCase = output.currentAccount.cases[output.caseIndex]`、`output.currentType`（報表靠這兩個算 case tag）。
- helper 檔名與 env key（`anchor_text`…）被報表反查使用。
- `.last_run_status.json` 的 key 是 `<flow>@<target>`；結果資料夾名稱 = flow 的 `name:`，沒有時 = 檔名。
- Python 腳本需 Python 3.9+。
