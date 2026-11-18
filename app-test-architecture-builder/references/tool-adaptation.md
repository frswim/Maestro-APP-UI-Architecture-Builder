# 非 Maestro 工具的落地對應（以 Appium + Java / TestNG 為例）

`templates/` 的 YAML helper、`run_suite.sh` 的執行段、`failure_rules.py` / `generate_report.py` 的 log 解析都是 **Maestro 專用**。
選了其他工具時，**保留設計原則、重寫實作**。本檔給 Appium + Java + TestNG + Maven 的對應寫法；WebdriverIO / Python 的寫法結構相同。

## 1. 模組對應總表

| 模組 | Maestro 版（templates） | Appium + Java 版 |
|---|---|---|
| M1 入口 | `run_suite.sh` | `scripts/run_suite.sh` 薄殼 → `./mvnw test -P<target> -Dbrand=… -Denv=… -Dplatform=… -Dlocale=… -Dgroups=smoke`；Maven profile 對應 target |
| M1 watchdog | 背景 subshell + pkill | TestNG `@Test(timeOut=…)` / suite `time-out` + surefire `forkedProcessTimeoutInSeconds` + CI 層 timeout（Jenkins `timeout(time: 60, unit: 'MINUTES')`） |
| M2 設定 | 扁平 yaml → `-e` | `config/brands/<brand>.yaml` + `config/env/<env>.yaml` 由 `ConfigLoader` 疊加；機密由 Vault / CI 注入成環境變數，設定檔只放 key 名或 secret path |
| M3 定位器 | `selectors/<platform>/<brand>/*.js` | `selectors/<platform>/<brand>/<page>.yaml|json` → `Locators.get("payin_page.confirmation.submit")` 回傳 `By`；Page Object 只用 key，不寫 XPath。key 路徑寫進例外訊息（報表反查用） |
| M4 資料驅動 | `repeat` + `output` | TestNG `@DataProvider` 讀 `test_data/<brand>/<flow>.json`；每個 case 一個 test invocation（天然 case tag） |
| M5 共用片段 | `runFlow` | Page Object + Flow/Step 類別（`LoginSteps.loginWithPin()`） |
| M6 等錨點 | `wait_anchor_or_dismiss.yaml` | `WaitHelper.waitAnchorOrDismiss(...)`（見 §2），**全面取代 `Thread.sleep`** |
| M7 API hook | `runScript` + `http.post` | 同語言 HTTP client（OkHttp / RestAssured），session 用 suite 級 `@BeforeSuite` 建立 |
| M9 判定 | `failure_rules.py` 讀 maestro.log | TestNG `ITestListener` 輸出 `results/<run>/<case>.json`（status、reason、locator_key、case tag、截圖路徑、裝置、build）→ 報表腳本讀 JSON（不用解析 log）；BLOCKED 用自訂例外 `EnvironmentBlockedException` |
| M9 報表 | `generate_report.py` | 沿用 HTML 版型，但輸入改成上面的 JSON；或用 Allure + 自訂 categories（阻斷 / BLOCKED / flaky） |
| M10 視覺 | `ui_diff_check.py` | 可直接沿用（它只吃 `chk_*.png` 檔案）：Listener 在 checkpoint 存 `chk_<name>.png` 到 `_raw/` 即可 |
| M11 重跑 | `run_failed.sh` | TestNG `testng-failed.xml` 或 `IRetryAnalyzer`（重跑通過標 flaky、寫進 JSON） |
| M18 裝置池 | 多個 runner + 裝置鎖 | TestNG `parallel="tests"`，每個 `<test>` 一台裝置的 capabilities；Appium 每台不同 `systemPort` / `wdaLocalPort` / `mjpegServerPort`；Jenkins Lockable Resources 鎖裝置 |

## 2. 等錨點 + 清彈窗（Java 範例）

```java
public final class WaitHelper {
    private final AppiumDriver driver;
    private final PopupRegistry popups;   // 讀 selectors/<platform>/<brand>/common_page 的 blocking_dismiss_ids / by_title

    /** 先點（可選）→ 分段等錨點 → 等不到就清彈窗 → 確實關掉才重點 → 牆鐘截止後丟出帶 locator key 的例外 */
    public void waitAnchorOrDismiss(String tapKey, String anchorKey, Duration timeout, Duration slice, String confirmKey) {
        if (tapKey != null) driver.findElement(Locators.get(tapKey)).click();
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            Duration left = Duration.ofNanos(Math.max(500_000_000L, Math.min(slice.toNanos(), deadline - System.nanoTime())));
            try {
                new WebDriverWait(driver, left).until(ExpectedConditions.visibilityOfElementLocated(Locators.get(anchorKey)));
                return;
            } catch (TimeoutException ignored) { /* 分段等待逾時 = warning，不是失敗 */ }
            if (confirmKey != null && Locators.isVisible(driver, confirmKey)) { driver.findElement(Locators.get(confirmKey)).click(); continue; }
            if (popups.dismissAny(driver) && tapKey != null) driver.findElement(Locators.get(tapKey)).click();  // 只有確實關掉彈窗才重點
        }
        throw new AnchorTimeoutException(anchorKey, timeout);   // 訊息含 locator key → 報表翻成流程/階段/目標
    }
}
```
規則同 M6：只用在階段切換點；`implicitlyWait` 設 0（否則每次判斷都白等）；所有 retry 有上限。

## 3. Listener 輸出（報表輸入）

```java
public class ResultJsonListener implements ITestListener {
    @Override public void onTestFailure(ITestResult r) { write(r, isBlocked(r) ? "BLOCKED" : "FAILED"); }
    @Override public void onTestSuccess(ITestResult r) { write(r, r.getMethod().getCurrentInvocationCount() > 1 ? "FLAKY_PASS" : "PASSED"); }
    // write(): case id（Excel 列 / 需求 id）、data provider 參數（遮罩後）、locator_key、例外訊息（遮罩後）、
    //          截圖（每步 + 失敗）、裝置 udid / 型號 / OS、App build 版本、開始結束時間 → results/<run>/<case>.json
}
```
`failure_rules` 在 Java 版的對應：只有未處理的例外 / 斷言失敗 = FAILED；分段等待逾時不算；suite 被 timeout / 中斷 → Listener 沒寫出 JSON 的 case 判「執行未完成」。

### 3.1 結果 JSON schema（任何工具通用，`generate_report.py` 會自動讀）

每個 case 一個 `<run_dir>/**/<case>.result.json`；有這種檔案時報表不解析 maestro.log：
```json
{
  "name": "checkout_flow[type_a-0]", "path": "tests/test_checkout.py::test_checkout", "tags": ["smoke", "C1234"],
  "status": "passed | failed | blocked | flaky_pass",
  "reason": "AnchorTimeout: checkout_page.summary.total (30000ms)",
  "locator_key": "output.selector.checkout_page.summary.total",
  "locator_value": "Total", "case_index": 0, "variant_type": "type_a",
  "screenshots": ["shots/c1_fail.png"], "duration_s": 42.1,
  "device": "<udid>", "device_model": "<model>", "platform": "android", "locale": "pt-BR", "flags": "<profile>",
  "brand": "default", "env": "staging", "role": "customer", "app_build": "<build>"
}
```
- **一個 run 開多組 capabilities（多平台 / 語系 / 裝置）時，`platform`、`locale`、`device` 等 target 欄位必填** —— `_summarize_results.py` 用它們組 key（`<name>@<target>`），沒填就只能用環境變數的那一份，同名 case 會互相覆蓋 → 假綠。只跑單一 target 時可改由 runner export `BRAND` / `TARGET_ENV` / `PLATFORM` / `LOCALE` / `FLAGS` / `FORM_FACTOR` / `DEVICE` / `TARGET_ID`。
- `reason` 寫入前先遮罩；`locator_key` 用 `output.selector.<page>.<...>` 形式（即使不是 Maestro）才能沿用 `selector_labels.json` 反查。
- `_summarize_results.py` 也會讀 `*.result.json`（→ `.last_run_status.json`、歷史、通知、TestRail 回寫都能用）；`run_failed.sh` 是 Maestro 版，非 Maestro 時用測試框架自己的重跑（pytest `--lf` / `pytest-rerunfailures`、TestNG `testng-failed.xml`）。

## 4. 改造既有 Page Object 的順序（增量）

1. 加 `Locators` + 定位器檔，**先搬最常壞的 10 個頁面**；XPath → accessibility id / resource-id（iOS 優先 accessibility id、`-ios class chain`、`-ios predicate string`）。
2. 加 `WaitHelper`，逐頁把 `Thread.sleep` 換掉（用 grep 計數追蹤剩餘數量）。
3. 加 Listener JSON + 新報表；**新舊報表並行一段時間**，比對判定差異。
4. 每改完一批，跑同一組測試 N 次量 flaky 率（見 `rollout-plan.md` 改造路線）。

## 4.5 Appium + Python / pytest 對應

| 模組 | 寫法 |
|---|---|
| M1 入口 | `scripts/run_suite.py`（Python，跨平台，Windows 也能跑）：讀 `config/brands/<b>.yaml` + `config/env/<e>.yaml` → 環境變數 → `pytest -m <tag>`；watchdog 用 `subprocess.run(timeout=...)` |
| M2/M3 | `conftest.py` fixture 載入設定與 `selectors/<platform>/<brand>/*.yaml`，`Locators.get("page.section.key")` 回傳 `(AppiumBy.ID, "...")` |
| M4 | `@pytest.mark.parametrize` 讀 `test_data/<brand>/<flow>.json`，`ids=` 用 `type-index`（報表 case tag） |
| M6 | `helpers/wait.py`：`wait_anchor_or_dismiss(driver, anchor_key, tap_key=None, timeout=30, slice=5, confirm_key=None)`，邏輯同 §2 Java 版 |
| M9 | `conftest.py` 的 `pytest_runtest_makereport` hook：失敗截圖 + 寫 §3.1 的 `*.result.json`；BLOCKED 用自訂例外 `EnvironmentBlocked` |
| M11 | `pytest-rerunfailures`（`--reruns 1`），hook 裡把「重跑才通過」寫成 `flaky_pass` |
| M18 | `pytest-xdist` + 每個 worker 一台裝置，每台不同 `systemPort` |
| 多角色（#22） | 對方角色 bot 寫成 fixture（`provider_bot.accept(order_id)`、`provider_bot.move_along(route)`） |

## 4.6 Appium + WebdriverIO（TypeScript）對應

| 模組 | 寫法 |
|---|---|
| M1 入口 | `scripts/run_suite.ts`（或 npm script）讀設定 → 選 `wdio.<target>.conf.ts`；watchdog = Mocha `timeout` + WDIO `connectionRetryTimeout` + CI step 上限 |
| M3 | `selectors/<platform>/<brand>/*.json` → `loc('page.section.key')` 回傳 `~accessibilityId` / `id=` / CSS（WebView） |
| M4 | `test_data/*.json` + `describe` / `it` 迴圈產生 case，標題帶 `type-index` |
| M6 | custom command `browser.waitAnchorOrDismiss(anchorKey, { tapKey, timeoutMs, sliceMs, confirmKey })`，邏輯同 §2 |
| Hybrid | `await driver.switchContext('WEBVIEW_<pkg>')` / `'NATIVE_APP'` 包成 helper；`getContexts()` 等待 webview 出現要有上限 |
| M9 | custom reporter（`@wdio/reporter`）在 `onTestEnd` 寫 §3.1 的 `*.result.json`；`afterTest` hook 失敗截圖 |
| M11 | `specFileRetries` / `mochaOpts.retries`，重跑通過寫成 `flaky_pass` |
| M18 | 多個 capabilities（每台裝置一組，不同 `appium:systemPort`），`maxInstances` 控制並行 |

## 4.7 原生雙框架（XCUITest + Espresso / Compose UI test）對應

| 模組 | iOS（XCUITest） | Android（Espresso / Compose test / UiAutomator） |
|---|---|---|
| M1 入口 | 薄殼 `scripts/run_suite.sh` → `xcodebuild test-without-building -xctestrun ... -destination ...`（先 `build-for-testing` 一次） | `./gradlew :app:connected<Flavor>AndroidTest` 或 `adb shell am instrument`；雲端 `saucectl run` |
| 白牌切換 | 一個 UI test target，`XCUIApplication(bundleIdentifier:)` 依品牌設定啟動對應 App；或每 scheme 一個 test plan | `targetPackage` 綁單一 flavor → 每個 flavor 一個 test APK（`<flavor>AndroidTest`）；或改用 UiAutomator（跨 App、可依 package 啟動） |
| M3 定位器 | `accessibilityIdentifier` 常數放共用 Swift 檔；key 命名與 Android 一致 | `testTag` / resource-id 常數；Compose 根節點開 `testTagsAsResourceId` |
| M4 資料驅動 | 讀 `test_data/<brand>/*.json`（加進 test bundle 資源），迴圈或 XCTest 動態 case | `@RunWith(Parameterized::class)` / JUnit5 `@ParameterizedTest` 讀同一份 JSON |
| M6 等待 | `waitForExistence(timeout:)` + 自寫 `waitAnchorOrDismiss`；系統對話框 `addUIInterruptionMonitor` / springboard | Espresso IdlingResource（同步 App 內非同步）、Compose `waitUntil`；系統對話框用 UiAutomator |
| M9 結果 | `xcresulttool` 匯出 → 轉 §3.1 JSON（含失敗截圖附件） | JUnit XML（`build/outputs/androidTest-results`）+ 截圖 → 轉 §3.1 JSON |
| M11 | `-retry-tests-on-failure -test-iterations 2`（Xcode 13+），重跑通過標 flaky | Gradle `testOptions` / Android Test Orchestrator + 自寫 retry rule，標 flaky |
| 共用層 | **測試規格、資料檔、locator key 命名、§3.1 JSON、報表、通知、TCM 回寫** 兩平台共用；測試碼不共用 |

## 5. 其他工具速記
- **Detox**：`detox test -c <config>`；等待用 `waitFor(element).toBeVisible().withTimeout()`；彈窗用 launchArgs 測試 flag 關閉優先。
- **Espresso / XCUITest**：IdlingResource / `waitForExistence(timeout:)`；定位器常數放共用 module；結果從 JUnit XML / xcresult 轉 JSON。
