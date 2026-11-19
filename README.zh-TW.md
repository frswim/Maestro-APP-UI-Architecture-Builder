# app-test-architecture-builder

[English](README.md) | 繁體中文

一份 Claude Code skill：讓 AI 以**訪談 → 決策 → 提案 → 分階段落地 → 驗證**的流程，替任何產業的公司建立或改造 App（Android / iOS / 跨平台 / Hybrid）UI 自動化測試架構。

架構是模組化的：AI 先跟你對答，了解你們的現況、軟體流程、平台、測試範圍、基礎設施與報表需求，再決定要加哪些模組、拿掉哪些模組，不會把同一套架構硬套到每家公司。

內容來自一套實際上線、跨多品牌、每天跑回歸的 Maestro 專案（已去識別化），並經過 10 輪不同產業樣本的模擬審計修正。

---

## 適用情境

- 「幫我們公司建 App 自動化測試架構」
- 「我們已經有自動化（Maestro / Appium / XCUITest…），但很不穩，請評估並改善」
- 「把這套測試架構移植到新產品 / 新專案」
- 「我們要導入 UI 自動化，從哪裡開始？」

**不適用**：在既有、已定案的專案裡只修單一 flow 或單一定位器。那種情況用該專案自己的 skill。

---

## 安裝

skill 是一個資料夾，**整個資料夾都要複製**（`SKILL.md` 會引用 `references/` 與 `templates/`）。

| 用途 | 放置位置 |
|---|---|
| 只在某個 repo 使用（可 commit 給團隊共用） | `<repo>/.claude/skills/app-test-architecture-builder/` |
| 所有專案都能使用（個人） | `~/.claude/skills/app-test-architecture-builder/` |

```bash
cp -R <來源>/app-test-architecture-builder ~/.claude/skills/
```

複製後開一個新的 Claude Code session 即可使用。

---

## 使用方式

### 1. 斜線指令（最確定）

```
/app-test-architecture-builder 我們公司要導入 App 自動化，請幫我規劃
```

### 2. 直接描述需求

說「幫公司建 App 自動化測試架構」、「評估我們現有的自動化框架」之類的話，AI 會依 skill 的描述自動載入。這是 AI 自行判斷的，想確保載入就用斜線指令。

### 3. 快速模式

趕時間時直接說「先給我最小可跑的骨架」。AI 只問 2 輪、共 7 題（現行自動化、平台、是否多 App 互動、誰維護、裝置來源、執行機 OS、第一條主流程與 App 外步驟），其餘用預設值產出 MVP，並把預設值列為「待確認假設」，之後再回頭補問。

### 建議先準備

- repo 路徑（有的話，AI 會先掃描，能推得出來的就不問）
- 測項規格檔（Excel / TestRail / Jira 等）
- 第一條想自動化的主流程（從打開 App 到結束的步驟）
- 測試帳號、裝置、CI 的基本資訊

---

## 流程（Pipeline）

```
P0  開場與現況掃描（讀 repo，不問就能知道的先知道）
P1  現行自動化現況 → 新建 / 增量改造 / 新舊並行
P2  產品與平台（App 類型、多品牌/多租戶、多 App 互動、語系、環境、feature flag）
P3  軟體流程（開發節奏、CI/CD、測項管理、誰維護、版控規定）
P4  測試範圍與資料（主流程、測試資料、App 外步驟、特殊能力清單）
P5  基礎設施與限制（裝置、執行機、合規、時程人力）
P5.5 工具選型（App 技術 × 誰寫 × 裝置來源 × 有無 macOS；寫 ADR）
P6  報表與品質門檻（讀者、擋版規則、視覺回歸、趨勢、正式證據文件）
P7  決策（答案 → 模組清單）
P8  提案 → 你確認後才建檔
P9  分階段落地（MVP → 擴充），每階段跑驗證清單
P10 交付（使用手冊、維護教學、設計文件、release note）
```

每輪最多問 4 題、選項化；每輪結束會回報「已知事實 / 推論出的模組影響 / 下一輪要問什麼」。訪談結果整理成 `docs/test-architecture/intake.md`，提案前給你確認。

---

## 架構模組（M1～M20）

| 模組 | 內容 | 預設 |
|---|---|---|
| M1 | 單一執行入口（設定載入、資源切換、輸出目錄、watchdog、報表、exit code；含雲端農場模式） | 必 |
| M2 | 設定分層（品牌 / 環境 / 機密 / 測試資料分開；Vault、多租戶、語系） | 必 |
| M3 | 定位器外置（依平台 / 品牌分檔、`active` 切換、`_base` + 品牌差異） | 必 |
| M4 | 資料驅動迴圈（帳號 × case，依 type 分派變體片段） | 條件 |
| M5 | 共用片段（登入、導航、清理） | 必 |
| M6 | 韌性層（等錨點 + 清彈窗 helper、重試上限、`TIMEOUT_SCALE`） | 多數必 |
| M7 | 後台 / API hook（審批、OTP、資料準備、對方角色 bot） | 條件 |
| M8 | Mock（代理攔截改回應、弱網） | 條件 |
| M9 | 結果判定 + 人類可讀報表（PASS / FAIL / BLOCKED / flaky、遮罩、多語系、單檔 HTML） | 必 |
| M10 | 視覺回歸 UI Diff（建立基線 / 檢查兩種模式、忽略區塊） | 條件 |
| M11 | 只重跑失敗、flaky 標記 | 建議 |
| M12 | 開發與環境工具（安裝腳本、抓元素、測試檔推送） | 必 |
| M13 | 知識層（使用手冊、維護教學、子系統設計文件、release notes） | 必 |
| M14 | 協作與版控（`.gitignore`、離線 bundle 交換） | 必 |
| M15 | CI 整合（GitHub Actions / GitLab / Jenkins / Azure / Bitbucket） | 條件 |
| M16 | 規格匯入與追溯（Excel / TestRail / Xray / Zephyr / Azure Test Plans） | 條件 |
| M17 | 稽核證據（遮罩、SHA-256 manifest、保存、簽署 PDF 證據報告） | 條件 |
| M18 | 裝置池與並行（裝置鎖、健康檢查、受測硬體池、品牌矩陣抽樣） | 條件 |
| M19 | 無障礙自動檢查（WCAG） | 條件 |
| M20 | 結果歷史與趨勢（每週通過率、最常失敗 / flaky） | 條件 |

哪個答案會導致納入哪個模組，見 [references/decision-matrix.md](references/decision-matrix.md)。

---

## 支援的工具與環境

- **測試工具**：Maestro（模板最完整）、Appium（Java / Python / TypeScript 寫法）、原生 XCUITest + Espresso / Compose UI test、Detox、Playwright（Hybrid 的 Web 層）。非 Maestro 的落地寫法見 [references/tool-adaptation.md](references/tool-adaptation.md)。
- **App 技術**：Android / iOS 原生、React Native、Flutter、Kotlin Multiplatform、Ionic / Capacitor 等 Hybrid、內嵌 Unity 等 canvas UI。
- **裝置來源**：本機模擬器、自有實機 lab、BrowserStack / Sauce Labs / AWS Device Farm / Firebase Test Lab / Maestro Cloud（附「農場 × 工具相容表」）。
- **特殊能力**：32 種，包括 OTP、TOTP、企業 SSO、生物辨識、推播、付款 sandbox、IAP、相機 / 掃碼、硬體掃描器、藍牙 / IoT、弱網 / 離線同步、視訊、多 App 互動、feature flag、平板、MDM、App Clip 等，各有做法優先序與平台限制。見 [references/capability-catalog.md](references/capability-catalog.md)。

表上沒有、或標示「需查證」的組合，AI 會先列為「待 spike」，用一條 hello-world 測試在實際環境驗證後才寫進提案。

---

## 檔案結構

```
app-test-architecture-builder/
├── SKILL.md                     # 入口：鐵則、pipeline、自我審核、檔案索引
├── references/
│   ├── interview-pipeline.md    # P0～P6 題庫、追問、對架構的影響、P5.5 工具選型
│   ├── decision-matrix.md       # 答案 → 模組、預設組合、衝突處理
│   ├── architecture-modules.md  # M1～M20 規格與跨工具對照
│   ├── capability-catalog.md    # 32 種特殊能力的做法
│   ├── tool-adaptation.md       # Appium / pytest / WDIO / 原生框架的落地寫法、結果 JSON schema
│   ├── maestro-pitfalls.md      # Maestro 實測行為與陷阱
│   ├── appium-pitfalls.md       # Appium 實務陷阱
│   ├── rollout-plan.md          # 新建路線與改造路線的分階段計畫、完成定義
│   ├── reference-implementation.md  # 原始案例（已去識別化）
│   ├── sanitization-checklist.md    # 去識別化檢查清單
│   └── audit-history.md         # 10 輪模擬審計的誤差與修正紀錄
└── templates/                   # 可直接複製的模板
    ├── run_suite.sh / run_failed.sh               # M1 入口、M11 重跑
    ├── wait_anchor_or_dismiss.yaml 等 4 支          # M6 Maestro 韌性 helper
    ├── failure_rules.py / generate_report.py / _summarize_results.py / flow_index.py   # M9 判定與報表
    ├── ui_diff_check.py / ui_diff_define_ignore.py / ui_diff_checkpoint.yaml           # M10 視覺回歸
    ├── trend_report.py                            # M20 趨勢
    ├── archive_evidence.sh / device_health_check.sh   # M17 證據、M18 裝置健康檢查
    ├── notify.sh / notify_payload.py              # 通知（Slack 類 / Teams / LINE / email）
    ├── push_testrail.py                           # TestRail 回寫
    ├── ci-github-actions.yml / ci-gitlab.yml / Jenkinsfile / azure-pipelines.yml / bitbucket-pipelines.yml
    ├── config-examples.md                         # 品牌設定、定位器、測試資料、遮罩、.gitignore 範本
    ├── intake-summary.md / architecture-decision-record.md
    └── requirements.txt
```

---

## 模板使用須知

- `*.yaml` helper 只適用 Maestro；`run_suite.sh` 是 Maestro 本機模式。換工具時，入口、等待 helper、結果格式都要換成該工具的寫法，但報表版型、遮罩、多語系、視覺比對、通知、趨勢可以沿用：讓測試輸出 `*.result.json`（schema 見 `tool-adaptation.md` §3.1）即可。
- Python 腳本需要 Python 3.9+，相依見 `templates/requirements.txt`。
- `run_suite.sh` 用環境變數切換目標維度，主要有 `TARGET_ENV`、`PLATFORM`、`LOCALE`、`FLAGS`、`FORM_FACTOR`、`DEVICE`、`DEVICE_MODEL`、`TIMEOUT_SCALE`；完整清單見腳本檔頭。
- Windows 執行機建議用 WSL2（Git Bash 沒有 `pkill`，watchdog 會失效）。
- 模板之間有命名契約（定位器路徑、迴圈變數名、helper 檔名、狀態檔 key），改名要一起改，詳見 `SKILL.md` 第七節。

---

## 限制

- 模板經語法檢查，並用模擬的 Maestro 輸出與合成資料實測過；**尚未在真實裝置上整套跑過**。第一次導入時，AI 會在階段 0 用 hello-world 測試驗證。
- 對照表（農場支援、工具指令、平台限制）會隨工具版本過時，以實測為準。
- 硬體本身（韌體、電氣）、語音指令、穿戴裝置等延伸介面不在本架構範圍，會在提案中明確列為排除或人工項。

---

## 維護

- 修改前先讀 [references/audit-history.md](references/audit-history.md)，避免把已修正的問題改回去。
- 新增範例或模板前，照 [references/sanitization-checklist.md](references/sanitization-checklist.md) 去識別化；專案特有的敏感關鍵字清單不要寫進 skill。
- 修改後建議用一個新的虛構公司樣本跑一次模擬審計（照 `audit-history.md` 的格式記錄）。
