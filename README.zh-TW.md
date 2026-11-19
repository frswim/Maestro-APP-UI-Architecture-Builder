# app-test-architecture-lite

[English](README.md) | 繁體中文

一份免費的 Claude Code skill：讓 AI 用 **Maestro**，以「訪談 → 決策 → 提案 → 分階段落地 → 驗證」的流程，替你的公司從零搭出 App UI 自動化測試架構。

AI 會先問你 12 題（現況、平台、軟體流程、主流程、測試資料、裝置、機密規定、報表），再依決策表挑選核心模組、給你一份提案確認，確認後才開始建檔。成果是一套能每天穩定跑、失敗時報表看得懂的架構。

內容來自一套實際上線、每天跑回歸的 Maestro 專案（已去識別化）。

---

## 包含什麼

- **流程與規則**：訪談 pipeline、決策表、快速模式、交付前自我審核
- **核心模組**：
  - M1 單一執行入口（watchdog、裝置鎖、報表、exit code）
  - M2 設定分層
  - M3 定位器外置
  - M4 資料驅動迴圈
  - M5 共用片段
  - M6 彈窗與等待韌性
  - M7 後台 API hook（基本）
  - M9 結果判定與單檔 HTML 報表
  - M11 只重跑失敗 / flaky 標記
  - M12 抓元素工具
  - M13 知識層
  - M14 版控規則
  - M15 GitHub Actions
- **可直接用的模板**：`run_suite.sh`、彈窗 helper、報表與判定腳本、`snap.sh`、通知（Slack 類 / Teams / LINE / email）、GitHub Actions、設定檔範本
- **Maestro 實測陷阱清單**與一份去識別化的實作範例

## 安裝

整個資料夾複製過去（`SKILL.md` 會引用 `references/` 與 `templates/`）：

```bash
# 所有專案都能用
cp -R app-test-architecture-lite ~/.claude/skills/
# 或只給某個 repo
cp -R app-test-architecture-lite <repo>/.claude/skills/
```

複製後開新的 Claude Code session。

## 使用

```
/app-test-architecture-lite 我們要用 Maestro 導入 App 自動化，請幫我規劃
```

也可以直接描述需求（「幫公司建 App 自動化測試」），AI 會依描述自動載入。
趕時間就說「先給我最小可跑的骨架」，AI 只問 4 題就產出 MVP。

## 需要的環境

- Maestro CLI、JDK、Android SDK（iOS 需要 macOS + Xcode）
- Python 3.9+（`pip install -r templates/requirements.txt`）
- macOS / Linux 執行機；Windows 請用 WSL2

## Lite 與完整版

<!-- 發布前把下面這行的 <FULL_VERSION_URL> 換成完整版（Agensi）的連結 -->
**完整版**(Coming Soon)：[app-test-architecture-builder](<FULL_VERSION_URL>)

| 面向 | Lite（免費） | 完整版 |
|---|---|---|
| 測試工具 | 只有 Maestro | Maestro、Appium（Java / Python / TypeScript）、XCUITest + Espresso / Compose test、Detox、Playwright，附各工具的落地寫法 |
| 工具選型 | 固定 Maestro | 依 App 技術、誰維護、裝置來源、有無 macOS 選工具，附「裝置農場 × 工具」相容表 |
| 裝置來源 | 本機模擬器、USB 實機 | 另含雲端裝置農場（BrowserStack、Sauce、AWS Device Farm、Firebase Test Lab、Maestro Cloud） |
| 訪談題庫 | 12 題 | 約 30 題，含追問與分流 |
| 快速模式 | 1 輪 4 題 | 2 輪 7 題 |
| 已有框架 | 零散腳本收編 | 框架評分、新舊並行改造路線（量化完成定義） |
| 模組 | 13 個核心模組 | 20 個：另含 Mock、視覺回歸、測項系統回寫、稽核證據、裝置池、無障礙、趨勢報表 |
| 能力目錄 | 8 種常見 App 外步驟（OTP、驗證信、後台審核、付款、上傳、權限、推播、定位） | 32 種：另含企業 SSO、TOTP、生物辨識、IoT / 藍牙、內購、遊戲畫面、影音、視訊、多 App 互動、feature flag、平板、MDM / kiosk、硬體掃描器、App Clip、系統錢包、OTA 等 |
| 多維度 | 品牌、環境的基本做法 | 再加多租戶、多語系、feature flag 組合、平板、白牌共用定位器與品牌矩陣抽樣 |
| 合規 | 機密不進版控、不連外的基本設定 | 報表與 log 遮罩、證據保存（SHA-256 manifest）、簽章 PDF 證據報告、資料駐留、Vault |
| CI 模板 | GitHub Actions | GitHub Actions、GitLab、Jenkins、Azure Pipelines、Bitbucket |
| 其他模板 | runner、重跑、彈窗 helper、判定與報表、`snap.sh`、通知、設定範本 | 另含視覺回歸、趨勢報表、TestRail 回寫、證據歸檔、裝置健康檢查 |
| 陷阱清單 | Maestro | Maestro + Appium |
| 範例 | 案例前段（目錄、設定、定位器、迴圈、helper、API hook） | 完整案例，含報表反查與視覺回歸 |
| 驗證 | 獨立審計（新樣本）確認可單獨運作 | 經 10 輪不同產業的模擬審計 |

兩版相同的部分：訪談 → 決策 → 提案 → 分階段落地 → 驗證的流程與鐵則、核心模組的設計原則，以及核心模板（runner、判定、報表、重跑、彈窗 helper）的程式碼。

Lite 遇到範圍外的需求時會照實說明，並列在提案的「之後 / 範圍外」區塊，不會硬用 Lite 模板假裝做得到。

## 限制

- 模板經語法檢查與模擬資料實測，**尚未在真實裝置上整套跑過**；第一次導入時，AI 會在階段 0 用 hello-world flow 驗證。
- Maestro 的行為依版本可能不同，以實測為準（見 `references/maestro-pitfalls.md`）。

