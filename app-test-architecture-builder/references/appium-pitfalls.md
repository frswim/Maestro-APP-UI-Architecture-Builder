# Appium 實務陷阱（選 Appium 時必讀）

> 版本差異大，動工前用一條 hello-world 測試在實際裝置來源上驗證。

## 定位
1. **iOS 上 XPath 非常慢**（要序列化整棵 accessibility tree），大量 XPath 是 flaky 與超時的主因。優先 accessibility id → `-ios class chain` → `-ios predicate string`；Android 優先 resource-id → UiAutomator selector。
2. 開發沒埋 id 時，跟開發約定命名規則（`screen_element_action`），列入可測性鉤子（Q-P2-6）。
3. WebView：`driver.getContextHandles()` 切 `WEBVIEW_*` context 才能用 CSS；Android 需要 App 開啟 WebView debugging，chromedriver 版本要對應裝置 WebView 版本。

## 等待
4. `implicitlyWait` 與顯式等待混用會讓等待時間相乘；建議 implicit = 0，全部用顯式等待 / helper。
5. `Thread.sleep` 全面禁止（例外要寫註解與原因）；用 grep 計數當改造指標。

## 實機與並行
6. iOS 實機需要 WebDriverAgent 簽章（開發者 Team ID、provisioning profile）；WDA 首次建置慢，CI 上預先建好並快取。
7. 並行時每個 session 要不同埠：Android `systemPort`、`chromedriverPort`、`mjpegServerPort`；iOS `wdaLocalPort`、`mjpegServerPort`，並指定 `udid`。
8. 一台 Mac 同時驅動的 iOS 實機數有限（依硬體，通常 2～4 台），超過就加 Mac。
9. 裝置健康檢查：開跑前確認電量、螢幕解鎖、網路、可用空間、系統彈窗（更新提示）；不健康就跳過該裝置並在報表標示。
10. Appium 2 的 driver / plugin 要鎖版本（`appium driver install uiautomator2@x.y.z`），寫進 setup 腳本，避免 CI 自動升級。

## 系統層 UI
11. **生物辨識**：模擬器可用 `mobile: enrollBiometric` / `mobile: sendBiometricMatch`（iOS Simulator）、`adb -e emu finger touch <id>`（Android Emulator）；**實機無法自動化** → 實機走 PIN fallback 或測試版 flag，生物辨識本身只在模擬器驗證或列為人工項。
12. **推播通知**：Android `driver.openNotifications()` 後找通知文字點擊；iOS 要切到 springboard（`com.apple.springboard`）找通知。都需要測試環境的 FCM / APNs sandbox 設定正確，且要有逾時上限；更穩的替代是用後端 API 確認「已送出 / 已確認」狀態。
13. 系統權限對話框：Android `autoGrantPermissions`、iOS `autoAcceptAlerts`（注意它也會吃掉 App 自己的 alert）。

## 結果
14. TestNG XML 只有 pass/fail，沒有失敗情境 → 用 Listener 輸出結構化 JSON（`tool-adaptation.md` §3）。
15. `IRetryAnalyzer` 重跑通過要記錄成 flaky，不要讓它變成乾淨的 PASS。
