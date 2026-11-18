# 決策矩陣：答案 → 模組 / 變體

模組代號定義在 `architecture-modules.md`。
「必」= 一律納入；「建」= 建議納入，使用者拒絕才拿掉；「條」= 符合條件才納入。

## 一、模組總表

| 模組 | 名稱 | 預設 | 納入條件（題號 → 答案） |
|---|---|---|---|
| — | 工具選型 | 必 | 依 `interview-pipeline.md` P5.5 矩陣決定，寫 ADR；不可直接套預設 |
| M1 | 單一執行入口 runner（含 watchdog、輸出目錄、exit code） | 必 | 變體：Q-P5-1=c → 雲端模式；單一 App → brand 參數用 `default` |
| M2 | 設定分層（環境/品牌、機密、測試資料分開） | 必 | 變體：Q-P2-2=b/d → 品牌檔；Q-P2-4=b/c/d → 加環境層；Q-P2-3=b → locale 維度；Q-P5-3 有要求 → 機密走本機檔/CI secret |
| M3 | 定位器外置（依平台/品牌分檔 + active 切換） | 必 | 變體：Q-P2-1 多平台 → `<platform>/` 層；跨平台框架（RN/Flutter）且 testID 共用 → `shared/` + 平台 override；Q-P2-2=b/d → `<brand>/` 層；單一 App 單平台 → 仍保留 `active/` 但只有一個目錄 |
| M4 | 資料驅動迴圈（帳號 × case，依 type 分派） | 條 | Q-P4-1 變體 ≥ 3 或 Q-P2-2=c/d；Q-P1-3 含 c |
| M5 | 共用片段（導航、登入、清理、回首頁） | 必 | — |
| M6 | 韌性層（等錨點 helper、彈窗清單、重試上限） | 條→多數必 | Q-P4-5=a/b，或 Q-P2-1 含 d，或 Q-P1-3 含 a/e |
| — | 多 App / 多角色互動 | 條 | Q-P2-9=b/c → `capability-catalog.md` #22（對方角色優先用 API bot） |
| M7 | 後台 / API hook（審批、狀態設定、資料準備、OTP） | 條 | Q-P4-4 含 a/b，或 Q-P4-3=b/c，或 Q-P2-6 含 d；變體：OTP、金流 sandbox 訂單驗證 |
| M8 | Mock（攔截 API 改回應） | 條 | Q-P4-3=c 且後台無法設定狀態；或要測錯誤情境（逾時、5xx） |
| M9 | 結果判定 + 人類可讀報表 | 必 | 變體：Q-P6-1=b → 單檔內嵌；c → 通知；d → JUnit/JSON |
| M10 | 視覺回歸 UI Diff | 條 | Q-P4-2 含 d，或 Q-P6-3=a/c |
| M11 | 只重跑失敗 / flaky 標記 | 建 | Q-P6-2=a/b 時必 |
| M12 | 開發與環境工具（安裝腳本、抓元素、除錯 runner、測試檔推送） | 必（安裝 + 抓元素）| Q-P4-4 含 d → 加測試檔推送；Q-P5-2 受限網路 → 安裝腳本要逐項容錯 |
| M13 | 知識層（使用手冊、維護教學、子系統設計文件、release notes、封存） | 必 | 變體：Q-P3-4=b → 使用者手冊為重點 |
| M14 | 協作與版控規則（gitignore、離線 bundle 交換、基線擁有者） | 必（gitignore）| Q-P3-5=c → 離線 bundle 流程 |
| M15 | CI 整合 | 條 | Q-P3-2 有 CI 且可接；Q-P3-1=b，或 Q-P6-2=a/b（要擋版 / 擋 merge）時必；模板 `templates/ci-github-actions.yml`、`ci-gitlab.yml`、`Jenkinsfile`、`azure-pipelines.yml`、`bitbucket-pipelines.yml` |
| M17 | 稽核證據與追溯 | 條 | Q-P5-3=e |
| M18 | 裝置池與並行 | 條 | Q-P5-1=b/d/e 且 ≥ 2 台，或執行時間超出預算 |
| M19 | 無障礙自動檢查 | 條 | Q-P4-6 勾 a11y，或法規 / 合約要求 |
| M20 | 結果歷史與趨勢 | 條 | Q-P6-1=e，或 artifact 保留期短 |
| — | 特殊能力（flag、弱網、視訊、相機、magic link、平板…） | 條 | Q-P4-6 每個勾選項 → `capability-catalog.md` 對應列的模組與做法 |
| M16 | 規格匯入與追溯（Excel/TCM → batch flow，TCM 回寫） | 條 | Q-P3-3=a/b，或 Q-P4-2 含 c；b → `templates/push_testrail.py`；Q-P3-3=c（Jira AC）→ 輕量版：ticket key tag + 報表連結 |

## 二、預設組合（快速模式 / 使用者答不知道時）

- 工具：快速模式也要先問 Q-P3-4、Q-P5-1、Q-P5-2 再套 P5.5 判定規則；本機模擬器 + 手測 QA → Maestro；雲端農場 → Appium（語言 = 維護者最熟的語言）。
- 模組：M1 + M2 + M3 + M5 + M9（基本判定 + 單檔 HTML）+ M12（安裝 + 抓元素）+ M13（README + 一份設計文件）+ M14（gitignore）。
- 階段 2 再加：M4、M6、M11。
- 其餘等使用者提出需求。

## 三、衝突與優先序

| 情況 | 處理 |
|---|---|
| 使用者要「全部都要」但人力只有 1 人、時程短 | 依 `rollout-plan.md` 階段切，先 MVP；把延後的模組列在提案「之後」區塊 |
| 現行框架評分 ≥ 10 但使用者想重寫 | 先列出重寫的成本與風險（並行期、遺失已穩定的 case），讓使用者確認 |
| 要求 CI gate 但只有實機 | 實機接在可當 CI agent 的機器（例如 Mac mini 當 Jenkins agent）→ 可以接 CI（模板 `templates/Jenkinsfile`）；真的不能接時才改「夜間本機排程 + 結果通知」，CI 只跑靜態檢查 |
| 不得出內網 | 自架 CI、報表資源內嵌、通知走內網、不用雲端農場；`notify.sh` 設主機白名單 |
| 資料限定地區（Q-P5-3=g） | 雲端服務可用但逐項確認區域（農場、CI、TCM、IM、信箱、CDN），寫 ADR；報表資源內嵌 |
| 已有零散腳本（Q-P1-1=b） | 新建路線 + 腳本盤點表收編；舊腳本在新結構跑通前保留 |
| 現行框架分數低但資產多 | 走「新舊並行、逐步替換」，不重寫（`interview-pipeline.md` 路線判定） |
| CI gate + 雲端裝置農場 | PR：App build → 上傳 → 只跑 smoke（時間預算 < 15 分鐘、並行 2～4 台）；夜間跑回歸；重跑後才通過的 case 在 gate 上算 PASS 但標 flaky 並通知，連續 flaky 開單；列出農場並行數與月費 |
| 正式環境也要跑 | 只跑 `prod-safe` tag 的唯讀冒煙，runner 擋其他 tag |
| 開發可以加測試 flag | 彈窗 / 評分窗 / 引導 / 動畫用 flag 關掉優先，M6 清單只當保險 |
| 要視覺回歸但裝置解析度不固定 | 基線依裝置型號分；或只做元素存在性斷言，不做像素比對 |
| 機密不得落地，但工具要讀設定 | 執行時從 CI secret / 系統 keychain 注入環境變數，設定檔只放 key 名稱 |
| 多語系 + 文字定位 | 優先改用 id/testID；做不到就語系對照表，報表標明語系 |

## 四、常見情境組合（給 P8 提案參考）

| 情境 | 典型模組組合 | 重點 |
|---|---|---|
| 新創、單 App、無自動化、1 位 QA | M1 M2 M3 M5 M9 M12 M13 M14 → 再 M6 M11 | 先求一條主流程每天穩定跑 |
| 多品牌白牌 App、渠道多（金流、電商） | 全部核心 + M4 M6 M7 M10 | active 切換、資料驅動、彈窗清單、後台 API |
| 大企業、已有 Appium 舊框架、強合規 | 評分後增量：M3 M6 M9 M11 + M15，M2 機密改 secret | 不重寫，先補報表與穩定性 |
| 開發主導、跨平台 RN/Flutter、持續交付 | M1 M2 M3（testID）M5 M9 M11 M15 | 冒煙 < 15 分鐘當 merge gate |
| 測項在 Excel、要逐條驗收 | 核心 + M16 + M11 | 過濾規則、追溯 id、每 batch 驗收 |
| Hybrid App、大量 WebView 收銀台/表單 | 核心 + M6 必；WebView 占比高 → Appium webview context + `data-testid`，Web 層另用 Playwright；座標只當最後手段 | 用「錨點出現/消失」判斷換頁；native / webview 切換寫成 helper |
