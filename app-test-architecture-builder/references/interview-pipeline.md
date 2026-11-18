# 訪談 Pipeline 題庫

每題格式：**ID｜問題**、選項（第一個為一般建議）、追問條件、對架構的影響（→ 模組代號見 `architecture-modules.md`）。
標 ★ 的是必答題；其餘題目在「能從 repo 推得出來」或「前面答案已排除」時跳過。

問法規則：
- 一輪最多 4 題；優先同一主題，題數不足 4 題時可以併入下一個主題的題目（典型 5～8 輪）。
- 選項要具體到使用者能直接選；永遠允許「其他（自由填寫）」。
- 每輪結束回報：已知事實 / 推論出的模組影響 / 下一輪主題。

---

## P1 現行自動化現況

### ★ Q-P1-1｜目前有沒有在跑的 App UI 自動化？
- a. 完全沒有，從零開始
- b. 有，但只有零星腳本、沒有固定架構
- c. 有完整框架，在 CI 或每日固定跑
- d. 曾經有，已停用（說明停用原因）

註：開發在 App repo 內的**單元 / 元件層**測試（JUnit、widget test、只測單一畫面不走流程的 instrumentation）不算 b，記錄成可測性資產（testID、IdlingResource、測試 flag）。但 **XCUITest / Espresso / Compose UI test 寫的端到端 UI 流程算 b 或 c**（看是否穩定、是否進 CI），要盤點與評分 —— 它們很可能是沿用的基礎（P5.5「原生雙框架」）。

影響：a → 新建路線；b → **新建路線 + 收編**：也要問 Q-P1-3 與做「現行框架量測」，並產出「腳本盤點表」（每支腳本 → 對應主流程 / 可抽成共用片段的步驟 / 寫死值清單（id、文字、帳號）/ 處置：收編、重寫、刪除）；舊腳本在新結構跑通前保持可執行，於新建路線階段 1～2 逐支收編，收編完才刪；c → 走「現行框架評分」決定增量改造；d → 停用原因就是新架構第一優先要解的問題（常見：太不穩、維護成本太高、沒人看報表）。

### Q-P1-2（b/c/d 才問）｜現行使用的工具與語言？
- Maestro（YAML）/ Appium（Java/Python/JS）/ Detox / Espresso+XCUITest / Playwright 或 Cypress（Web/Hybrid）/ 其他

追問：版本、在哪台機器跑、誰在維護。
影響：沿用工具時，後續模組用該工具的對應寫法（`architecture-modules.md` 末尾對照表）；要換工具時，提案要列遷移成本與「新舊並行期」。

### Q-P1-3（b/c/d 才問）｜現行架構最痛的 3 件事？（可複選）
- a. 不穩定 / flaky（彈窗、載入慢、時序問題）
- b. 改一個畫面要改很多地方（定位器散落、複製貼上）
- c. 新增測項很慢（每個 case 都要寫新腳本）
- d. 報表看不懂 / 沒人看 / 誤判
- e. 執行太久或會卡死
- f. 換品牌 / 換平台要整份複製
- g. 環境難建、新人上手難

影響（直接決定改造優先序）：a → M6；b → M3+M5；c → M4（+M16）；d → M9；e → M1 watchdog + M6 上限；f → M2+M3 的 active 切換；g → M12 安裝腳本 + M13 手冊。

### 現行框架量測（b/c/d 才做；P0 掃描時先算）
- 規模：測試數、Page Object / flow 數、執行時間。
- 寫死定位器：`grep -rc 'By.xpath\|xpath:' src/`、Maestro 的 `id: "` / `text: "` 直接出現在 flow 的次數。
- 固定等待：`grep -rc 'Thread.sleep\|time.sleep\|waitForAnimationToEnd' .`
- flaky 率：近 30 次執行結果（TestNG/JUnit XML 歷史、CI 紀錄）中「同一測試有過也有不過」的比例；沒有歷史就先連跑 5 次量。
- 這些數字是改造路線的基準線，寫進 intake。

### 現行框架評分表（c 才做；AI 讀 repo 後自評，再請使用者確認）

| 面向 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 定位器管理 | 寫死在每支測試 | 部分集中 | 全部外置、依平台/品牌分檔 |
| 重用性 | 大量複製貼上 | 有共用函式但不一致 | 導航/登入/清理全是共用片段 |
| 資料驅動 | 每個 case 一支腳本 | 部分參數化 | 資料檔驅動迴圈 |
| 等待與韌性 | 固定 sleep | 有顯式等待但無上限 | 有上限 + 彈窗處理 + watchdog |
| 結果判定 | 只看工具原生結果 | 有自訂但會誤判 | 區分阻斷錯誤/warning/未完成 |
| 報表 | 無或原生 | 有但難讀 | 人類可讀情境 + 截圖 + 可轉寄 |
| 執行入口 | 各自下指令 | 有腳本但參數多 | 單一入口、一行指令 |
| 文件 | 無 | 有但過時 | 有設計文件與異動紀錄 |

判分補充（避免各說各話）：
- 定位器：Page Object 有集中但值寫死在類別裡（例如 XPath 常數）= 1；有外部定位器檔或統一 Locator 介面 = 2；散在測試方法裡 = 0。
- 等待：有顯式等待但仍有大量 `sleep`（> 測試數的一半）= 0。
- 報表：只有工具原生 XML、沒人看 = 0。

另外三個**資產面向**不加總、但決定路線：
| 面向 | 低 | 高 |
|---|---|---|
| 既有測試資產（數量 × 仍有價值的比例） | < 50 支或多數已失效 | ≥ 100 支且多數仍對應現行功能 |
| flaky 率 | < 10% | > 20% |
| 團隊對現行工具的熟練度 | 沒人熟 | 有人熟 |

路線判定：
- 總分 ≥ 10 → 增量改造（只補缺的模組）。
- 5～9 → 局部重構（保留工具與可用片段，重做結構）。
- ≤ 4 → **預設「新舊並行、逐步替換」**：保留現行工具與測試資產，新結構（定位器外置、等待 helper、結果 JSON、報表）先套在最常壞的頁面，依 `rollout-plan.md` 改造路線逐批替換；只有在「資產低 且 沒人熟現行工具」時才提重寫，並列出重寫成本讓使用者決定。不得因分數低就直接建議重寫。

---

## P2 產品與平台

### ★ Q-P2-1｜要測的 App 是什麼類型、哪些平台？（可複選）
- a. Android 原生
- b. iOS 原生
- c. 跨平台 UI（React Native / Flutter / Compose Multiplatform）——**Kotlin Multiplatform 只共用邏輯、UI 用 Compose + SwiftUI 各寫的，算 a + b（雙原生）**
- d. Hybrid：原生殼 + 大量 WebView（收銀台、活動頁、表單）
- e. 也要測對應的 Web 版

影響：b → 需要 macOS 執行機、iOS 模擬器或實機，定位器多一個平台目錄；c → 先確認 testID / accessibilityLabel 是否已埋（決定定位器穩定度，沒有就要跟開發約定）；d → M6 必納入（WebView 載入慢、loading mask 吃點擊、元素無 id），定位器允許「座標」作為最後手段並要註明原因；e → 工具選型要能涵蓋 Web（或 Web 另用 Playwright，共用資料與報表層）。

### ★ Q-P2-2｜同一套流程要跑在幾個「變體」上？
- a. 只有一個 App
- b. 多品牌 / 白牌（同一套程式，不同 applicationId、文案、主題）
- c. 多租戶 / 多地區（同 App，不同帳號決定功能）
- d. 以上皆有
- e. 同一產品的不同版本 App（例如個人版 / 企業版），兩個 bundle id、功能部分不同

影響：e → 同時用品牌目錄（id、文案差異）+ 測試資料的功能旗標（`features: ["approval"]`，flow 依旗標跳過不存在的功能）；b/d → M2 品牌設定檔 + M3 定位器依品牌分目錄 + runner 的 active 切換；c → 多租戶：runner 的 brand 參數當 tenant 用（`config/brands/<tenant>.yaml` 放租戶設定與可預期值：價格表、啟用服務；`test_data/<tenant>/` 放帳號與 case），定位器通常不分目錄；租戶若由 GPS 位置 / 帳號地區決定，mock location 要跟 tenant 連動（`capability-catalog.md` #13）；a → 仍建議保留 `active/` 結構（成本低，未來擴充不用重構）。

### Q-P2-3｜App 語系與 UI 文案會變嗎？
- a. 單一語系、文案穩定
- b. 多語系，需要每個語系都測
- c. 文案常改（A/B test、營運活動）

影響：b → locale 變體：runner `LOCALE=<x>` 傳給 flow，App 語系用 launch argument / 裝置語系 / 雲端 capability 切換（先確認 App 支援哪一種）；文字定位改用 id/testID，做不到就定位器依語系分值；非拉丁文字（天城文、泰文、CJK…）：文字斷言前先做 Unicode 正規化（NFC），輸入非 ASCII 時確認工具支援（Maestro `inputText` 對非 ASCII 支援有限 → WebView 內用 Appium sendKeys、或裝 ADB Keyboard 類輸入法）；彈窗「標題 + 按鈕」清單要涵蓋每個語系的文字；測試資料可放 `test_data/<brand>/<locale>/`；報表 case tag 與通知帶 locale；視覺基線依語系分；c → 定位器優先 id/testID，文字定位只當 fallback，彈窗清單機制（M6）必要。

### Q-P2-4｜有哪些測試環境？
- a. 只有正式環境（限唯讀或小額）
- b. UAT / Staging 各一套
- c. 多套環境（dev/sit/uat/stg），常切換
- d. 測試環境 + 正式環境都要跑

影響：b/c/d → 加環境層 `config/env/<env>.yaml`（runner 的 `TARGET_ENV` 疊加覆寫）；a/d → **正式環境只跑唯讀冒煙**（登入、瀏覽、搜尋、到結帳前一頁），會產生真實訂單 / 扣款 / 寄信的步驟一律只在測試環境跑；正式環境的 flow 用 `prod-safe` tag 標示，runner 在 `TARGET_ENV=prod` 時只允許這個 tag，並寫清理策略。

### ★ Q-P2-5｜測試用的 App 包由誰、在哪裡建出來？
- a. App 的 CI 每次產出測試用 build（debug / qa flavor），自動化直接下載
- b. QA 手動拿安裝包（APK / IPA）安裝
- c. 只有商店版 / release 版

追問：有 App 內購買嗎？（有 → 需要經商店測試軌道安裝、簽章與上架版一致的包，見 `capability-catalog.md` #17）testID / accessibility 是否在 release 被移除？iOS 實機要簽章的 .ipa（Ad Hoc / Enterprise / 開發者帳號）誰提供？模擬器用 .app（simulator build）誰出？
影響：a → CI 管線串「App build artifact → 測試 job」，報表記錄受測 build 版本；b → runner 開頭印出並記錄已安裝 App 版本（`adb shell dumpsys package <id> | grep versionName` / `xcrun simctl appinfo`）；c → 無法埋測試 flag、可能沒有 testID，定位器穩定度下降，提案列為高風險並建議爭取 qa build。iOS 需要「建置機（macOS）」與「執行機（模擬器需 macOS；實機可在雲端）」分開考慮。

### ★ Q-P2-9｜一條主流程是否跨多支 App / 多個角色？
- a. 否，單一 App 單一使用者
- b. 是，多支 App 互動（例如顧客端 + 服務提供端、買家 + 賣家、病患 + 醫師）
- c. 是，同一 App 多角色（例如申請人 + 審核人）

影響：b/c → `capability-catalog.md` #22：①對方角色用後端測試 API 當 bot（最穩，單裝置即可）②兩台裝置各跑一支 App 的 flow，用後端狀態同步（同步點都要逾時上限，M18）③同一台裝置裝兩支 App 輪流切換（只適合非即時互動）；設定要分 `customer_app_id` / `provider_app_id`；狀態檔與報表要帶 role。

### Q-P2-7｜有沒有 feature flag / 遠端設定會改變 UI？
- a. 有（請說明系統、怎麼覆寫、目前有哪些上線中的組合）
- b. 沒有

影響：a → 見 `capability-catalog.md` #1：`config/flags/<profile>.json` + runner `FLAGS=`；決定要跑的組合（上線中 + 即將上線）；flow 依 flag 用 tag 篩選；狀態檔、報表、基線帶 profile。

### Q-P2-8｜裝置型態與顯示設定？（可複選）
- a. 只有手機直式
- b. 也支援平板（不同版面 / 分割畫面）
- c. 橫豎屏、摺疊機
- d. 深色模式 / 字型縮放要驗

影響：b/c → runner `FORM_FACTOR=`、定位器 override 層、flow 分支（`capability-catalog.md` #18）；d → 基線 key 加主題、字型縮放矩陣（#19、M10、M19）。

### Q-P2-6｜開發能提供哪些「可測性鉤子」？（可複選）
- a. testID / accessibilityIdentifier（resource-id）
- b. 測試版 flag：關掉促銷彈窗、評分窗、新手引導、動畫
- c. deep link 直達指定頁面 / 狀態
- d. 測試用 API：建立帳號、設定狀態、查 OTP
- e. 都不行，只能黑箱

影響：a → 定位器以 id 為主；b → **彈窗處理優先序：測試 flag 關閉 > M6 彈窗清單**（系統層 UI 例如 iOS 的評分對話框、Android In-App Review 不在 App hierarchy 裡、M6 清單不一定關得掉，一定要用 flag 或測試帳號避開）；c → 前置導航用 deep link 縮短流程、降低 flaky（主流程至少保留一條完整走 UI 的路徑）；d → M7；e → M6 權重最高、座標定位比例會上升，提案標風險。

---

## P3 軟體流程

### ★ Q-P3-1｜開發與發版節奏？
- a. Scrum，固定週期（例如兩週）發版
- b. Kanban / 持續交付，隨時發版
- c. Waterfall / 季度大版（常伴隨月度 hotfix）
- d. 不固定

影響：a → 自動化節奏綁 sprint：每個 sprint 末跑完整回歸，日常跑冒煙；b → 必須接 CI（M15），冒煙套件要短（< 15 分鐘）並當 merge gate；c → 重點是發版前的大回歸 + 視覺回歸（M10）；有 hotfix → 另建 `hotfix` 套件：smoke + 受影響功能的 tag（flow 依功能區塊加 tag，例如 `area:transfer`），hotfix 只跑這些；d → 先做夜間排程 + 手動觸發。

### Q-P3-2｜CI/CD 用什麼？自動化要接進去嗎？
- GitHub Actions / GitLab CI / Jenkins / Bitbucket Pipelines / Bitrise / Azure DevOps / 沒有 CI / 不能接（資安限制）

追問：CI 機器能不能跑模擬器（需要硬體加速 / macOS runner；Bitbucket Cloud、多數 SaaS runner 沒有 KVM → 要 self-hosted runner）？要不要用雲端裝置農場？artifact 保留多久（趨勢需要另存，M20）？
影響：要接 → M15（headless、artifact 上傳、exit code 當 gate、報表連結通知）；不能接 → runner 本機排程（cron / launchd）+ 報表轉寄。

### Q-P3-3｜測項（test case）在哪裡管理？
- a. Excel / Google Sheet
- b. TestRail / Xray / Zephyr 等測項管理系統
- c. Jira ticket 的 AC
- d. 沒有書面測項

影響：a/b → M16 規格匯入（過濾規則、合併儲存格、追溯 id、batch 驗收）；b → 報表要回寫結果或至少帶 case id；c → M16 輕量版：每支 flow 加需求 ticket tag（`req:PROJ-123`；tag 前綴約定：TestRail `C123`、Azure Test Plans `TC123`、Xray test `xray:PROJ-456`、Zephyr Scale `zephyr:PROJ-T123`、需求 `req:PROJ-123`，避免撞名），報表顯示 key 並可連回 ticket；AC 清單逐條對應到 flow 中的斷言；之後若導入 Xray / Zephyr 再升級成 b；d → 先跟使用者共同列出「主流程清單」當第一批範圍。

### Q-P3-4｜誰寫與維護自動化？技能程度？
- a. 專職 QA 自動化工程師（會寫程式）
- b. 手測 QA 為主，程式能力有限
- c. 開發自己寫
- d. 外包 / 輪值

影響：b → 工具偏向宣告式（YAML 類），強調資料檔驅動（改 case 不碰程式）、操作手冊（M13 的使用者手冊）、報表中文情境；c → 可以跟 App 同 repo、用同語言，定位器改由開發埋 testID；d → 文件與知識層（M13）權重最高。

### Q-P3-5｜版控規定？
- a. 一般 Git 遠端（GitHub/GitLab/Bitbucket）
- b. 只能放公司內部 Git
- c. 不能放任何線上服務（只能離線交換）

影響：c → M14 離線協作（git bundle 增量交換、同步基準 tag、分支規則）；所有情況都要 `.gitignore` 排除機密、測試產出、本機設定，並保留需要進版控的二進位資產（例如視覺基線）的例外規則。

---

## P4 測試範圍與資料

### ★ Q-P4-1｜第一批要自動化的主流程是哪一條？（請描述從打開 App 到結束的步驟）
例：登入 → 搜尋商品 → 加入購物車 → 結帳 → 看到訂單完成頁。

追問：這條流程有幾種「變體」？（付款方式、配送方式、會員等級、國家）每種變體的 UI 步驟一樣嗎？
影響：變體多且步驟不同 → M4 資料驅動 + 依 `type` 分派片段；變體步驟相同 → 單純參數化；第一條流程就是 MVP 的驗收標的。

### Q-P4-2｜測試範圍分層？（可複選）
- a. 冒煙（每天 / 每次 merge，最短時間驗主流程活著）
- b. 回歸（發版前，涵蓋主要變體）
- c. 規格逐條驗收（對著測項表一條條做）
- d. 視覺回歸（畫面跑版、文案錯）

影響：用 tag 分層（runner 支援 include-tags）；c → M16；d → M10。

### ★ Q-P4-3｜測試帳號與資料怎麼來？
- a. 固定幾組測試帳號，人工準備
- b. 可以用 API / 後台批次建立
- c. 需要特定狀態的帳號（KYC 等級、會員等級、餘額）很難準備
- d. 每次測試會消耗資料（餘額、庫存、優惠券）
- e. 環境會定期刷新 / 重置（帳號、資料會失效）

影響：資料檔結構用「帳號 → case 清單」；c → 考慮 M8 Mock（攔截 API 改回應）或後台 API 設定狀態（M7）；d → 測試要有補資料/清理步驟（例如先跑入金補餘額再跑出金），流程間的資料相依要寫進資料檔註解與手冊；e → **資料重建 job**（用 API / 腳本產生合成測試帳號與資料，刷新後自動跑）+ **開跑前帳號健康檢查**（登入、餘額、狀態），檢查失敗時以 `[BLOCKED]` 訊息結束（報表顯示 BLOCKED，不算 App 缺陷、不算 flaky）；合規要求合成資料時，資料產生器本身也要進版控。

### Q-P4-4｜流程中有沒有「App 外」的步驟？（可複選）
- a. 需要後台人工審核 / 改狀態才能繼續
- b. OTP / Email / SMS 驗證碼
- c. 第三方頁（支付、WebView 外連）
- c2. 企業 SSO / OAuth 登入（Okta、Azure AD、SAML；系統瀏覽器 ASWebAuthenticationSession / Chrome Custom Tabs）
- d. 系統相簿 / 檔案上傳 / 相機
- d2. 硬體掃描器 / 周邊裝置送 intent（專用手持機、掃描槍、刷卡機）→ `capability-catalog.md` #30，會影響 P5.5 工具選型
- e. 推播通知
- f. 生物辨識登入 / 授權（Face ID、指紋）
- g. 硬體 token / TOTP 動態密碼
- h. 都沒有

影響：a → M7 後台 API hook（整輪登入一次共用 session、查單號→審批、失敗要 throw 讓報表判 FAIL）；b → **OTP 依序選**：①測試環境白名單門號/信箱 + 固定 OTP（最穩）②後台或測試 API 查碼（M7 的 OTP 變體，帶重試與逾時）③測試版 bypass flag ④測試信箱服務 API；正式環境不自動化 OTP 登入（或用專用帳號 + 長效 session）；不得用個人手機門號；c2 → 見 `capability-catalog.md` #25（測試 IdP、bypass token、只保留 1～2 條真實 SSO）；c → 分兩類：(1) **交易終點必須驗**的（電商結帳、付款）：測試環境用金流 sandbox（測試卡、3DS 測試 challenge、錢包 sandbox）走到「付款完成 / 訂單完成頁」並驗訂單狀態（UI 或 API）；跳到外部 App 的錢包（裝置上未必安裝）改用 sandbox web 流程或 mock 閘道 + deep link 回 App；(2) 只是外連的：只驗證「已跳轉」與「返回後狀態」，用「原頁面錨點消失」判斷跳轉成功；d → 預先推送測試檔與授權（M12 的 setup 腳本），選檔步驟用多重備援並記錄裝置型號；e → 推播若是流程**必要步驟**：①後端 API 確認「已送出 / 已確認」狀態（最穩）②實機開通知欄點擊（Android 開通知欄、iOS 切 springboard，見 `appium-pitfalls.md` #12），需 FCM/APNs sandbox 正確設定，設逾時上限 ③deep link 模擬點擊通知；只是附帶通知則只驗後端狀態；f → 實機無法自動化生物辨識：實機走 PIN / 密碼 fallback 或測試版 flag；生物辨識本身只在模擬器驗證（工具的 biometric 指令）或列人工項，提案寫明；g → TOTP：seed 放機密庫（Vault / CI secret），測試內以標準演算法計算或呼叫 token 模擬 API；處理時鐘偏移（取碼前檢查剩餘秒數，不足就等下一個週期）、一碼只用一次，重試要取新碼。

### ★ Q-P4-6｜主流程會用到以下哪些「特殊能力」？（可複選；完整清單與做法見 `capability-catalog.md`）
- feature flag、a11y 自動檢查、弱網/離線（含離線同步衝突）、即時視訊、相機/證件/掃碼、Email magic link、OTP、TOTP、生物辨識、推播、付款/第三方頁、檔案上傳下載/PDF、定位地圖、藍牙/NFC/IoT、背景/被殺恢復、權限對話框、App 內購買、平板/摺疊、深色模式/字型、時間相關、穿戴/Widget、多 App/多角色、遊戲引擎/canvas、影音播放、企業 SSO、MDM 受管設定、手寫簽名/手勢、長時間流程（OTA）、語音助理帳號連結、硬體掃描器 / 周邊 intent、加入系統錢包 / 票卡、App Clip / Instant App

問法：列成多選（分 2～3 輪問，每輪 ≤ 4 個選項群組），或請使用者看清單回覆編號。
影響：**每個勾選項都要在 intake 與提案中寫出「做法優先序 + 模組 + 風險」**（照 `capability-catalog.md` 那一列）；沒勾的不做。不在清單內的能力，照同格式補一條並寫 ADR。

### Q-P4-5｜App 有沒有不定時出現的彈窗？
- a. 有很多（活動、廣告、評分、引導、版本更新、權限）
- b. 偶爾
- c. 幾乎沒有

影響：a/b → M6 必納入；並建議跟前端約定「所有阻擋型彈窗的關閉鈕統一一個 id」，之後新彈窗零維護。

---

## P5 基礎設施與限制
（P5 結束後立刻做 P5.5 工具選型）

### ★ Q-P5-1｜在什麼裝置上跑？
- a. 本機模擬器（Android Emulator / iOS Simulator）
- b. 實體裝置（USB 連線）
- c. 雲端裝置農場（BrowserStack / Sauce Labs / AWS Device Farm / Firebase Test Lab / Maestro Cloud…；**先查 P5.5 的「農場 × 工具相容表」**）
- d. 自有裝置 lab（多台實機接在內網機器上，例如 Mac mini）
- e. 混合

追問：同時要跑幾台？解析度是否固定？（影響座標定位與視覺基線）使用者主力裝置的效能等級（低階機 → `TIMEOUT_SCALE`、冷啟動 / WebView 首載先量基準、ANR 對話框列入彈窗清單、App 切到背景（例如購買畫面）可能被系統殺掉）要不要每次都跑全部裝置，還是 smoke 跑 1 台、回歸分散到全部？
影響：c → runner 用「雲端模式」（M1）：打包上傳 → 輪詢 → 下載結果 → 同一套報表；工具要先實測能在該農場跑（P5.5）；並行數與費用寫進提案；視覺基線要依「裝置型號 + 解析度」分；b/d 且 ≥ 2 台 → M18 裝置池（鎖裝置、每台獨立輸出、結果合併、健康檢查）；平行執行時 runner 的 device 參數與 watchdog 比對要用 device id；解析度不固定 → 禁用像素座標，只用百分比座標且列為最後手段。

### ★ Q-P5-2｜執行機作業系統與網路限制？
- macOS / Windows / Linux；公司網路是否擋 pip/npm/brew、是否需要 proxy

影響：Windows → bash 模板（`run_suite.sh`、`run_failed.sh`、`notify.sh`）在 Git Bash 下 watchdog 失效、symlink 變複製 → 建議 WSL2，或把 runner 改寫成 Python（跨平台）；Python 腳本已統一 UTF-8 I/O，仍建議設 `PYTHONIOENCODING=utf-8`；iOS 需要 macOS（建置 / 模擬器）。安裝腳本（M12）要能在受限網路下逐項失敗不中斷、記錄原因；擋套件下載 → 依賴越少越好（報表用標準庫 + 少量套件），列出離線安裝方式。

### ★ Q-P5-3｜資安與合規要求？（可複選；金融、醫療、政府等受監管產業快速模式也必問）
- a. 機密不得進版控
- b. 程式碼 / 報表 / 截圖不得出公司內網（不能用雲端服務、外部 CDN、外部 IM）
- c. 只能用合成測試資料
- d. 報表 / log / 截圖要遮罩個資（帳號、姓名、證號）
- e. 法規要求執行證據與追溯，保存 N 年
- f. 機密集中在密碼庫（Vault / Secrets Manager）
- g. 資料限定地區（例如只能在 EU 處理 / 儲存）
- h. 無特殊要求

影響：a → M2 機密分層（`*.example` 進版控）；b → 報表資源全部內嵌（`REPORT_INLINE_ASSETS=1` + `config/vendor/`）、通知只走內網 IM（`NOTIFY_ALLOWED_HOSTS`）或內網 SMTP relay（`NOTIFY_FORMAT=email`）、CI 用自架；工具本身的連外也要關：Maestro 不用 `extractTextWithAI` / `assertWithAI`（會把截圖送雲端）、設 `MAESTRO_CLI_NO_ANALYTICS=1`、CLI 與依賴改離線安裝（內部鏡像 / 預先打包），Appium driver 也預先下載；c → 資料產生器（Q-P4-3 e）；使用者含未成年人 / 病患等，一律用合成帳號與假姓名（regex 遮罩遮不住姓名）；雲端農場預設錄影與截圖存放在平台上，也在遮罩範圍外，要確認保存與存取權限；d → M9 遮罩規則 `config/report_mask.json`（文字 regex + 截圖遮罩矩形），log 歸檔前同樣遮罩，自我審核要 grep 報表確認無帳號格式；e → M17 稽核證據；f → M2 Vault 變體（執行時注入，設定檔只放 secret path）；g → 每個外部服務逐項確認區域並寫進 ADR：裝置農場 / Maestro Cloud、CI runner 與 artifact 儲存、測項管理系統、IM / 通知、測試信箱、CDN（報表資源一律內嵌，不從外部 CDN 載入）、錯誤追蹤服務；不確定的服務先不用。視覺基線截圖可能含個資 → 基線用合成帳號、或忽略 / 遮罩區塊。

### Q-P5-4｜時程與人力？
- 期望多久看到第一條流程跑通？之後誰接手？

影響：決定分階段計畫的切法；人力少 → 先做 MVP + 報表，韌性與視覺回歸延後。

---

## P5.5 工具選型（★ 必做，不可直接套預設）

不要預設 Maestro。依下表給出 1 個建議 + 1 個備選，寫成 ADR（`templates/architecture-decision-record.md`），並跟使用者確認。

| 維度 | 傾向 Maestro | 傾向 Appium（WebdriverIO / Java / Python） | 傾向 Detox | 傾向原生 Espresso / XCUITest | 傾向 Playwright |
|---|---|---|---|---|---|
| 誰寫（Q-P3-4） | 手測 QA、低程式能力 | QA 自動化工程師 | RN 開發 | 原生 App 開發 | Web 開發 |
| App 技術（Q-P2-1） | 原生 / RN / Flutter / Hybrid 皆可 | 皆可，WebView context 切換最完整 | 只限 RN | 單平台原生 | Web / Hybrid 的 Web 部分 |
| 裝置來源（Q-P5-1） | 本機模擬器、Maestro Cloud（其他農場要查下表） | 多數雲端農場（例外見下表）；自有實機 lab 並行最成熟 | 本機 / 自架為主 | Firebase Test Lab、多數農場 | 瀏覽器雲 |
| Flutter App（Q-P2-1=c，Flutter） | 可（需 `Semantics(identifier:)`） | Appium Flutter driver / 一般 Appium（同樣需 Semantics identifier） | 不適用 | Flutter `integration_test`；**Patrol**（Dart，可處理原生權限、通知、系統 UI） | Flutter Web 才適用 |
| 自有實機 lab 多台並行（Q-P5-1=d） | 可（多個 runner + 裝置鎖），iOS 實機支援要先驗證 | 最成熟（每台獨立 session 與埠） | iOS 實機支援有限 | 可 | — |
| 有無 macOS（iOS 需要） | iOS 模擬器需 macOS | 實機可全雲端 | iOS 需 macOS | 需 macOS | 不需要 |
| 與 App 同 repo / 同語言 | 否（YAML） | 可 | 是 | 是 | 可 |

**農場 × 工具相容表（相容性否決優先於語言偏好；資料以撰寫時為準，選用前一定用 hello-world 實測並寫進 ADR）**

| 農場 | 執行方式 | Appium | Maestro | Espresso / XCUITest | 其他 |
|---|---|---|---|---|---|
| BrowserStack / Sauce Labs | **依工具而定**：Appium = 客戶端驅動（遠端 WebDriver）；Espresso / XCUITest / Maestro = 伺服器端執行（上傳 App + test runner，saucectl / App Automate API） | ✔ | 部分支援，需查版本與指令限制 | ✔（iOS 實機要已簽章的 test runner `.ipa`） | — |
| AWS Device Farm | 伺服器端執行（上傳測試包 + test spec） | ✔（Python / Java / Node 打包） | 需自訂環境 test spec，未原生支援 | ✔ | — |
| **Firebase Test Lab** | 伺服器端執行 | **✘** | **✘** | ✔（instrumentation；WebView 用 Espresso-Web） | Robo（無腳本相容性抽測）、Game Loop（遊戲） |
| Maestro Cloud | 伺服器端執行 | ✘ | ✔ | ✘ | — |
| 自有實機 / 本機模擬器 | 本機 | ✔ | ✔ | ✔ | — |

→ 例：使用者已有 FTL 預算、團隊寫 TS → UI E2E 用 Appium（WebdriverIO）跑在辦公室實機 / 本機模擬器（或改 BrowserStack / Device Farm）；FTL 留給 Robo 相容性抽測或開發的 Espresso 測試。

**Hybrid（Q-P2-1=d）依 WebView 占比分流**：
- WebView 占比高（≥ 約 70%，例如 Ionic / Capacitor / Cordova）→ **Appium + WEBVIEW context + CSS 定位**（開發加 `data-testid`）；**`data-testid` 不會進 Android / iOS accessibility tree**，Maestro 與原生 UiAutomator / XCUITest 看不到它 —— 選 Maestro 就要請開發改用會映射到 a11y 的屬性（`id`、`aria-label`），並確認抓元素工具真的看得到。
- Native / WebView 切換點（影片播放器、商店購買、遊戲引擎、系統對話框、權限都在 NATIVE_APP）寫成 helper（`switch_to_webview()` / `switch_to_native()`）。
- QA build 要開 WebView debugging（Capacitor `webContentsDebuggingEnabled`、Android `WebView.setWebContentsDebuggingEnabled(true)`）；chromedriver 要對應裝置 WebView 版本（低階舊機版本差異大，用 Appium `chromedriverAutodownload` 或 chromedriver 對照表）。
- **兩層策略**：Web 層頁面（表單、測驗）用 Playwright + 行動裝置模擬在瀏覽器測（快、穩、可進 CI）；實機 E2E 只留串起 native / web 的主流程。

判定規則：
- **雙原生框架 vs Appium 單一 codebase**（雙原生 App、團隊會 Kotlin + Swift、已有 XCUITest / Espresso 資產時必須比較）：原生框架穩定、快、跟 App 同 repo，但兩套測試碼；Appium 一套碼，但較慢、多一層。選雙原生時，**共用的是測試規格、資料檔、locator key 命名、結果 JSON（`tool-adaptation.md` §3.1）與報表**，不共用測試碼。寫 ADR。
- **語言 = 實際維護者最熟的語言**（Python 團隊 → Appium Python + pytest；Java → Appium Java；TS → WebdriverIO）。
- 「雲端裝置農場 + 跨平台 + 程式能力足夠」→ 預設 Appium（語言依上條）；Maestro 為備選（需先驗證農場支援，例如 AWS Device Farm 沒有原生 Maestro 類型，要用自訂環境 test spec）。
- 「手測 QA 為主、本機或 Maestro Cloud」→ 預設 Maestro。
- 「RN 且開發主導、本機/自架」→ Detox；混合團隊（開發 + 手測 QA）→ 開發維護片段與定位器、QA 只改資料檔，工具選開發熟的那個，但資料檔格式要讓 QA 看得懂。
- 主流程需要在測試中送 adb 指令 / broadcast intent（硬體掃描器、周邊，catalog #30）時：Appium 可直接做；選 Maestro 必須先確認 App 有測試注入入口或主機端 bridge，寫 ADR。
- Flutter 且開發會寫 Dart、要碰原生系統 UI（權限、通知）→ 評估 Patrol；QA 主導、YAML 好上手 → Maestro（要求開發用 `Semantics(identifier:)`）。a11y 稽核（M19）不論選哪個，都在 App repo 用 Flutter widget test 的 `meetsGuideline` 做。
- 現行框架評分 ≥ 10，或「新舊並行」路線 → 沿用現行工具與語言（例如團隊是 Java → Appium Java client，不是改 WebdriverIO）。
- 任何選擇都要列：學習成本、與裝置來源的相容性（需實測一條 hello-world flow 才算確認）、授權費用。

選定後，後續模組照 `architecture-modules.md` 的原則實作，語法換成該工具（文末對照表）；本 skill 的 `templates/*.yaml`、`run_suite.sh` 執行段、log 解析只適用 Maestro。**非 Maestro 必讀 `tool-adaptation.md`**（Appium/Java 的入口、watchdog、等待 helper、Listener JSON 寫法）與對應的 pitfalls 檔（`appium-pitfalls.md`）。

---

## P6 報表與品質門檻

### ★ Q-P6-1｜誰看測試結果？怎麼看？
- a. QA 自己看 HTML 報表
- b. 要轉寄給 PM / 開發 / 主管（單檔可攜）
- c. 要進聊天群組通知（Slack / Teams / 其他企業 IM）
- d. 要進儀表板 / 測項管理系統
- e. 要看趨勢（每週通過率、最常失敗 / flaky 的 flow）
- f. 要交正式證據文件（PDF、需簽署 / 驗收機關要求的格式）

影響：所有情況都做 M9（人類可讀失敗情境 + 截圖）；報表語言 = 讀者語言（`REPORT_LANG`，labels 也要用該語言）；b → 單檔 HTML、圖片 base64 內嵌（代價是檔案大，要寫明）；Q-P5-3=b 時不得轉寄到內網以外；c → runner 結尾送摘要 + 報表位置；d → 產出 JUnit XML / JSON；e → M20 結果歷史（`history/runs.jsonl` + `templates/trend_report.py`，history 要放持久位置）；f → M17「證據報告」變體（列印版面、PASS 步驟截圖、PDF/A + 字型內嵌、數位簽章），先跟驗收方確認格式與簽章要求並寫 ADR。報表語言跟讀者一致。

### Q-P6-2｜什麼情況算「失敗」？什麼要擋版？
- a. 任何主流程失敗都擋版
- b. 只有冒煙失敗擋版，回歸失敗開單追蹤
- c. 只報告不擋版

影響：決定 exit code 規則、視覺回歸的 failOnDiff 預設值、flaky 是否自動重跑（M11：只重跑失敗的、重跑通過要標記為 flaky 而不是當成 PASS 隱藏）。

### Q-P6-3｜要不要做視覺回歸（截圖比對）？
- a. 要，關鍵頁面都要
- b. 先不要，之後再說
- c. 要，但只想抓大跑版，不在意小像素差

影響：a/c → M10；c → threshold 與 color_tolerance 放寬、只比對固定區域；a → 預設 0 容忍 + 忽略動態區塊。基線依「品牌 × 平台 × 解析度」分。

---

## 訪談收尾

1. 把所有答案整理成 `templates/intake-summary.md` 的格式，給使用者確認。
2. 列出「待確認假設」（使用者答不知道、或你推論的）。
3. 進入 P7（`decision-matrix.md`）。
