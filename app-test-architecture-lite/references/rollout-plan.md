# 分階段落地計畫

原則：每階段都要能「跑得起來、看得到報表」才進下一階段；完成定義（DoD）沒達成不准宣稱完成。沒有裝置可實跑時，DoD 改成「乾跑通過 + 標明未實跑」。

> 這是「新建路線」（Q1=a/b）。已有完整框架的改造路線屬完整版。

## 階段 0：環境與骨架（0.5～2 天）
- 建目錄、`.gitignore`、安裝說明（README，或自行寫 `setup/setup.sh`）、`config/brands/<brand>.yaml.example`、從 `templates/` 複製 runner 與報表腳本。
- 驗證：新人照 README 從零裝好；runner 對錯誤參數給清楚訊息。
- `flows/config.yaml`（模板 `templates/flows-config.yaml`）—— flow 放在子資料夾時必備。
- DoD：`./scripts/run_suite.sh <brand> flows/` 跑得到 `flows/_smoke/launch.yaml`（確認不是 0 支 flow），能冷啟動 App、截一張圖、產出 `report.html`。

## 階段 1：MVP —— 一條主流程端到端（3～10 天）
- 用 `snap.sh` 抓元素 → 寫定位器檔（M3）→ 共用片段（M5：登入/回首頁）→ 第一條主流程（Q7）。
- 基本判定與報表（M9：至少區分阻斷錯誤與 warning、單檔 HTML、失敗截圖）。
- 驗證：連跑 3 次全綠；故意把一個定位器改錯 → 報表指出流程/階段/元素；故意 Ctrl-C → 報表顯示「執行未完成」。
- DoD：主流程穩定通過，失敗時非作者也看得懂報表。

## 階段 2：資料驅動 + 韌性（1～2 週）
- M4：把主流程改成迴圈 + 依 type 分派；新增 case 只改資料檔。
- M6：等錨點 helper、彈窗清單、重試上限；runner watchdog。
- M11：只重跑失敗。
- M7（若需要）：後台 API hook、OTP。
- 驗證：資料檔加/減 case 不改 flow；人工觸發彈窗會被清掉；把 timeout 調很短 → 逾時失敗並寫明等待目標；watchdog 設 1 分鐘 → 強制結束仍出報表。
- DoD：所有變體在單一 flow 跑完；沒有任何等待可以無限卡住。

## 階段 3：報表強化 / CI（約 1 週）
- M9 進階：定位器 → 人類可讀情境、case tag、helper 反查（模板已內建，補齊 `selector_labels.json` 即可）。
- M15：GitHub Actions（或其他 CI 執行同一行 runner 指令）、通知。
- 驗證：歷史 log 回放確認判定正確；CI 上故意讓一條 flow 失敗，看報表與通知。
- DoD：報表可直接轉寄給非 QA 的人看懂；CI（或排程）每日自動跑。

## 階段 4：擴充到其他業務線 / 品牌 / 平台
- 新品牌：只加 `brands/<new>.yaml`、`test_data/<new>/`、`selectors/<platform>/<new>/`，不改 flow。
- 新業務線：複製同一模式（迴圈 + 變體片段 + 資料檔），第三次重複才抽共用骨架。
- 新平台（iOS）：新增 `selectors/ios/<brand>/`，同 key 名。
- 視覺回歸、裝置池、稽核證據、無障礙等進階模組屬完整版。
- DoD：`run_suite.sh <new_brand> <flow>` 不改任何 flow 即可跑。

## 階段 5：知識交接（貫穿每階段，最後收斂）
- 使用者手冊、維護教學、每個子系統的 SKILL.md、release note、ADR、intake 留檔。
- DoD：沒參與開發的人照手冊能獨立跑測試、看懂報表、知道什麼要回報。

## 每階段共用驗證清單
- [ ] 語法檢查全過（工具自帶 lint / check-syntax）；CI 設定檔先用 YAML parser 驗過（`python3 -c "import yaml,sys;list(yaml.safe_load_all(open(sys.argv[1])))" <file>`），並在 CI 平台的 lint（GitLab CI Lint、`actionlint` 等）跑一次
- [ ] 定位器 key 一致性與 labels 完整性檢查
- [ ] grep 無寫死的 id/文字/帳號/網址出現在 flow
- [ ] `git status` 乾淨：無機密、無產出檔
- [ ] 通知實際送出一次（webhook / email 各自設定的那種），確認收得到
- [ ] release note 寫明已驗證 / 未驗證範圍
