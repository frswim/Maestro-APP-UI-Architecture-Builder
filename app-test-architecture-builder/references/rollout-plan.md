# 分階段落地計畫

原則：每階段都要能「跑得起來、看得到報表」才進下一階段；完成定義（DoD）沒達成不准宣稱完成。沒有裝置可實跑時，DoD 改成「乾跑通過 + 標明未實跑」。

> 這是「新建路線」。已有框架走下方「改造路線」。非 Maestro 工具時，各階段 DoD 裡的 `run_suite.sh` 換成該工具的入口（`tool-adaptation.md`）。

## 階段 0：環境與骨架（0.5～2 天）
- 建目錄、`.gitignore`、`setup/setup.sh`、`config/brands/<brand>.yaml.example`、runner 骨架。
- 驗證：新人照 README 從零裝好；`setup.sh` 重跑會略過已裝項目；runner 對錯誤參數給清楚訊息。
- DoD：`./scripts/run_suite.sh <brand> flows/_smoke/launch.yaml` 能冷啟動 App、截一張圖、產出 `report.html`。

## 階段 1：MVP —— 一條主流程端到端（3～10 天）
- 用 `snap.sh` 抓元素 → 寫定位器檔（M3）→ 共用片段（M5：登入/回首頁）→ 第一條主流程（Q-P4-1）。
- 基本判定與報表（M9：至少區分阻斷錯誤與 warning、單檔 HTML、失敗截圖）。
- 驗證：連跑 3 次全綠；故意把一個定位器改錯 → 報表指出流程/階段/元素；故意 Ctrl-C → 報表顯示「執行未完成」。
- DoD：主流程穩定通過，失敗時非作者也看得懂報表。

## 階段 2：資料驅動 + 韌性（1～2 週）
- M4：把主流程改成迴圈 + 依 type 分派；新增 case 只改資料檔。
- M6：等錨點 helper、彈窗清單、重試上限；runner watchdog。
- M11：只重跑失敗。
- M7（若需要）：後台 API hook。
- 驗證：資料檔加/減 case 不改 flow；人工觸發彈窗會被清掉；把 timeout 調很短 → 逾時失敗並寫明等待目標；watchdog 設 1 分鐘 → 強制結束仍出報表。
- DoD：所有變體在單一 flow 跑完；沒有任何等待可以無限卡住。

## 階段 3：報表強化 / 視覺回歸 / CI（1～2 週，依需求）
- M9 進階：定位器 → 人類可讀情境、case tag、helper 反查。
- M10：checkpoint、基線建立、忽略區塊、檢查模式。
- M15：CI 管線、artifact、通知。
- 驗證：歷史 log 回放做新舊判定差異表；視覺回歸先建基線 → 再跑檢查 → 故意改一個文案看 FAIL 與差異框。
- DoD：報表可直接轉寄給非 QA 的人看懂；CI（或排程）每日自動跑。

## 階段 4：擴充到其他業務線 / 品牌 / 平台
- 新品牌：只加 `brands/<new>.yaml`、`test_data/<new>/`、`selectors/<platform>/<new>/`，不改 flow。
- 新業務線：複製同一模式（迴圈 + 變體片段 + 資料檔），第三次重複才抽共用骨架。
- 新平台（iOS）：新增 `selectors/ios/<brand>/`，同 key 名。
- DoD：`run_suite.sh <new_brand> <flow>` 不改任何 flow 即可跑。

## 階段 5：知識交接（貫穿每階段，最後收斂）
- 使用者手冊、維護教學、每個子系統的 SKILL.md、release note、ADR、intake 留檔。
- DoD：沒參與開發的人照手冊能獨立跑測試、看懂報表、知道什麼要回報。

## 改造路線（已有框架：增量 / 局部重構 / 新舊並行）

| 階段 | 內容 | DoD |
|---|---|---|
| R0 量測 | 依 `interview-pipeline.md` 的「現行框架量測」算基準：測試數、寫死定位器數、sleep 數、flaky 率、執行時間；找出最常失敗的前 10 個頁面 / 測試 | 基準數字寫進 intake 與 release note |
| R1 隔離 | flaky 測試加 `quarantine` tag，不擋版但每天跑、記錄；修好才移出 | gate 只由穩定測試組成 |
| R2 結果與報表 | 先加結構化結果（Listener JSON / failure_rules）+ 新報表，新舊報表並行 | 失敗都能看到流程/階段/目標 + 截圖；判定差異表已核對 |
| R3 逐批替換 | 每批 1～3 個頁面：定位器外置、`sleep` → 等待 helper、彈窗處理；每批完連跑 N 次 | 該批 flaky 率 < 5%、sleep 數下降；批次紀錄在 release note |
| R4 入口與 CI | 單一入口、watchdog、裝置池、通知 | 一行指令 / 一個 job 跑完並出報表 |
| R5 擴充 | 資料驅動、視覺回歸、追溯 / 證據 | 依需求模組的 DoD |
| R6 汰除 | 舊寫法全部換完後刪除舊 helper 與舊報表 | grep 舊寫法 = 0 |

整體目標用數字定：例如 flaky 率 25% → < 5%、`sleep` 900 → 0、失敗平均排查時間下降。

## 每階段共用驗證清單
- [ ] 語法檢查全過（工具自帶 lint / check-syntax）；CI 設定檔先用 YAML parser 驗過（`python3 -c "import yaml,sys;list(yaml.safe_load_all(open(sys.argv[1])))" <file>`），並在 CI 平台的 lint（GitLab CI Lint、`actionlint` 等）跑一次
- [ ] 定位器 key 一致性與 labels 完整性檢查
- [ ] grep 無寫死的 id/文字/帳號/網址出現在 flow
- [ ] `git status` 乾淨：無機密、無產出檔
- [ ] 通知實際送出一次（webhook / email 各自設定的那種），確認收得到
- [ ] release note 寫明已驗證 / 未驗證範圍
