# 決策表（Lite）：答案 → 模組

「必」= 一律納入；「條」= 符合條件才納入。模組規格見 `architecture-modules.md`。

| 模組 | 名稱 | 預設 | 納入條件 / 變體 |
|---|---|---|---|
| M1 | 單一執行入口 `run_suite.sh` | 必 | 單一 App → brand 用 `default`；Q4 有多環境 → `TARGET_ENV`；Q10 低階裝置 → `TIMEOUT_SCALE` |
| M2 | 設定分層（設定 / 機密 / 測試資料） | 必 | Q3=b → 品牌設定檔；Q4=b/c → `config/env/`；Q11=a → 實檔不進版控 |
| M3 | 定位器外置 + `active` 切換 | 必 | Q2 雙平台 → `selectors/android/`、`selectors/ios/`；Q3=b → 依品牌分目錄 |
| M4 | 資料驅動迴圈 | 條 | Q7 變體 ≥ 3，或 Q3=c |
| M5 | 共用片段（登入、導航、清理） | 必 | — |
| M6 | 韌性：等錨點 + 清彈窗 helper、重試上限 | 條（多數必） | Q9=a/b，或 Q2=d |
| M7 | 後台 / API hook（基本） | 條 | Q7 有 OTP / 後台審核，或 Q8=b/d |
| M9 | 結果判定 + 人類可讀報表 | 必 | Q12=b → 單檔可轉寄；Q11=b → `REPORT_INLINE_ASSETS=1` |
| M11 | 只重跑失敗 / flaky 標記 | 條 | Q12=a/b 時必 |
| M12 | 抓元素 `snap.sh`、安裝說明 | 必 | — |
| M13 | 知識層（手冊、設計文件、release note） | 必 | Q6 維護者=b → 操作手冊為重點 |
| M14 | 版控規則（`.gitignore`） | 必 | — |
| M15 | CI（GitHub Actions） | 條 | Q5 用 GitHub Actions；Q5=b 或 Q12=a/b 時必（其他 CI 照 runner 一行指令自接） |

**超出 Lite 範圍的答案**（照 `SKILL.md` 第五節處理，列在提案「之後 / 範圍外」）：
- Q1=c 且不是 Maestro、或要評估 / 改造既有框架
- Q2 要用 Appium / XCUITest / Espresso，或 Q10=c 雲端裝置農場
- 要視覺回歸、Mock、測項系統自動回寫、稽核證據 / 遮罩 / 簽章、多裝置並行池、無障礙檢查、趨勢報表、feature flag 組合矩陣

## 預設組合（快速模式 / 答不知道時）
M1 + M2 + M3 + M5 + M6 + M9 + M12 + M13 + M14；第一條主流程跑通後再加 M4、M7、M11、M15。

## 常見情境
| 情境 | 組合 | 重點 |
|---|---|---|
| 新創、單 App、1 位 QA | 預設組合 → M11 | 先求一條主流程每天穩定跑 |
| 渠道 / 方案很多的流程（付款方式、方案等級） | 預設 + M4 + M7 | 新增 case 只改資料檔 |
| 彈窗很多的電商 / 內容 App | 預設 + M6 強化 + 測試版開關 | 先請開發關彈窗，清單當保險 |
| 已有幾支零散 Maestro flow | 預設 + 收編盤點表 | 舊 flow 跑通前保留 |
