# 常見 App 外步驟 / 系統能力（Lite：8 種）

Q7 勾到的每一項，提案都要寫出「做法 + 模組 + 風險」。不在表上的能力（例如企業 SSO、藍牙 IoT、內購、遊戲畫面、硬體掃描器、視訊、feature flag 矩陣等）：照鐵則 2 先 spike 並寫 ADR，或列為完整版範圍。

| # | 能力 | 做法優先序 | 限制 / 注意 | 模組 |
|---|---|---|---|---|
| 1 | **OTP（簡訊 / Email 驗證碼）** | ①測試環境白名單門號 / 信箱 + 固定 OTP ②後台或測試 API 查碼（送出後輪詢，有次數與逾時上限）③測試版 bypass 開關 ④測試信箱服務 API | 正式環境不自動化 OTP 登入；不得用個人手機門號 | M7 |
| 2 | **Email 驗證連結 / magic link** | 測試信箱 API 取信 → 解析連結 → Maestro `openLink`（或 `adb shell am start -d <url>`、`xcrun simctl openurl`） | 連結多半一次性，重試要重新寄；寄信有延遲，輪詢設上限 | M7 |
| 3 | **後台審核 / 改狀態** | 後台 API hook：整輪登入一次 → 用單號查 → 審批；取不到單號才用帳號查最新一筆 | 失敗一定 throw；session 過期給明確訊息與更新步驟 | M7 |
| 4 | **付款 / 第三方頁** | 交易終點要驗：測試環境用金流 sandbox（測試卡、3DS 測試）走到完成頁 + API 查訂單狀態；只是外連：驗「已跳轉」（`gone_text` 原頁按鈕消失）與返回後狀態 | 第三方頁文字常抓不到；正式環境不跑 | M6、M7 |
| 5 | **檔案上傳（相簿 / 檔案選擇器）** | 預先推送測試檔到裝置並授權（`adb push` 到 Pictures / Download、`adb install -g`）；選檔步驟多重備援，記錄裝置型號 | 系統選檔 UI 依 OS 版本不同 | M12、M5 |
| 6 | **權限對話框** | 安裝時授權（`adb install -g`、iOS 模擬器 `xcrun simctl privacy grant`）；要測對話框本身才走 UI | iPhone 實機的權限對話框只能走 UI；系統 UI 不在 App hierarchy | M12 |
| 7 | **推播通知** | ①後端 API 驗「已送出 / 已確認」狀態（最穩）②deep link 模擬點擊通知 ③實機開通知欄點擊（需 spike） | 需推播 sandbox 設定正確；設逾時上限 | M7 |
| 8 | **定位 / 背景與恢復** | 定位：Maestro `setLocation` / `adb emu geo fix` / `xcrun simctl location set`；背景與被殺恢復：`stopApp` → `launchApp`、Home 鍵背景化後回來，資料一致性用 API 驗 | 雲端農場與實機的模擬定位限制多，先 spike | M5、M7 |
