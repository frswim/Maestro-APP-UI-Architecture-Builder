# Maestro 實測行為與陷阱（選 Maestro 時必讀）

> 依據：Maestro 2.8.x 實跑 log 與反組譯 orchestra jar。版本不同時，第 1～4 點要重新確認（`maestro --version`；必要時 `javap -c -p` 看 `evaluateCondition` / `repeatCommand`）。

## A. 條件判斷與等待

1. **`when: visible` / `notVisible` / `repeat.while` 會等待**：內部 lookup timeout 約 7 秒，且扣掉距上次互動經過的時間（`adjustedToLatestInteraction`）。
   - `visible`：元素在 → 立即 true；不在 → 等到上限才 false。
   - `notVisible`：元素不在 → 立即 true；**元素在 → 一直等它消失**，到上限才 false。
   - 推論：正常路徑不要用 `while: notVisible <錨點>`（錨點已出現時白等）；改成正向 `visible` 判斷設 flag。
   - 推論：每多一個「先檢查有沒有彈窗」的 `when visible`，沒彈窗時最多白等 7 秒；同一段時間內多個檢查共用預算。
2. **`tapOn ... optional: true` 元素不存在時會等滿 timeout**（10～30 秒），不是快速跳過。
3. **`retryTapIfNoChange` 預設 true**：點完 UI 沒變會等再重試。切 tab 這類動作加 `retryTapIfNoChange: false`；需要立刻進下一步的再加 `waitToSettleTimeoutMs: 0`。
4. **`launchApp` 一定會等 App 可互動**（2～25 秒），無法再壓縮。
5. **`extendedWaitUntil` / `waitForAnimationToEnd` 的 `timeout` 是字串欄位**，可以 `${...}` 動態給；JS 數字可能變 `"5000.0"`，一律 `String(Math.floor(x))`。

## B. 迴圈與變數

6. **`repeat.times` 非法值 = 無上限**：經 JS 求值後 `toDoubleOrNull()`，NaN / undefined 會**靜默變成 Int.MAX_VALUE**。動態 times 一律先算成合法整數字串並封頂。
7. **`output` 是全域**：`runFlow` / `runScript` 呼叫的子檔都能直接讀寫 `output.*`，不用 env 傳遞。
8. **一般 env 變數（`${user_email}`）是唯讀頂層綁定**：要覆寫子流程讀的 env，用 `runFlow: { file, env: {...} }`；env 有 scope，不會洩漏到下一次呼叫。
9. **env 沒給的變數直接引用 → ReferenceError**：helper 參數一律 `typeof x !== 'undefined' && x ? x : 預設` 正規化成 `output.*`。
10. **`runFlow` / `runScript` 的檔案路徑不支援變數**：「依品牌換檔」只能在外層 runner 先切 symlink / 複製成固定名稱。
11. **路徑相對於目前檔案**：`flows/a/b/x.yaml` 用 `../../../subflows/...`、`subflows/a/x.yaml` 用 `../common/...`、`subflows/x.yaml` 用 `common/...`。搬檔要一起改。

## C. YAML 與 JS 語法

12. **`${...}` 內含「冒號 + 空白」（三元運算子、物件字面量）要把整個值用雙引號包住**，否則 YAML 解析失敗（Parsing Failed）。純比較（`==`、`<`、`&&`）不用。
13. `evalScript` 裡的 `console.log` 不一定寫進 log；要核對中間值用 `assertTrue` 帶 `label`，結果直接反映在報告。
14. `runScript` 的 JS 環境不能 `require`；有 `http.get/post`、`json()`、`output`。雜湊等演算法要內嵌實作。
15. 每改一個 yaml 跑 `maestro check-syntax <file>`；批次：`for f in $(git ls-files 'flows/*.yaml' 'subflows/*.yaml'); do maestro check-syntax "$f"; done`。

## D. 結果與輸出

16. **`optional: true` 失敗只是 warning**：log 記 `CommandWarned`、狀態 `WARNED`，訊息還會包進上層 runFlow 的 metadata（`insight=... level=WARNING`）。**不能再用「log 有 Assertion is false」判失敗**。
17. **`commands.json` 只在 flow 正常結束（PASS 或 FAIL）時寫出**；被 Ctrl-C 或強制結束就沒有 → 可用來偵測「執行未完成」。
18. 沒指定 `--test-output-dir` 時輸出寫到 `~/.maestro/tests/`；指定時 Maestro 還會在裡面自己加一層時間戳資料夾 → 解析結果一律 `rglob`，不假設深度。
19. 同一輪同名 `takeScreenshot` 會覆蓋（不加編號）。
20. failed 步驟的 log 會印出完整的 `${output.selector....}` 原始寫法，下一行 metadata 有展開值（`textRegex=` / `idRegex=` / `RelativePoint(...)`）→ 報表反查依據。

21b. **`maestro test <資料夾>` 預設只跑該層的 yaml**：flow 放在子資料夾（`flows/<domain>/x.yaml`）時，要在 `flows/config.yaml` 寫 `flows: ["**"]`（模板 `templates/flows-config.yaml`），否則回報「Top-level directories do not contain any Flows」、0 支 flow。subflow 放在 `flows/` 以外（例如 `subflows/`）才不會被當成測試跑。

## E. 裝置與環境

21. Maestro Studio 與 CLI 互斥（都會佔用裝置 driver）→ `DeviceServerDiedException`。跑 CLI 前關 Studio。
22. 首次在裝置上執行要裝 driver APK（約 30 秒）。
23. 多台裝置同時連線 → `adb: more than one device`，用 `--device <id>`。
24. WebView 內元素：HTML 的 `data-testid` **不會**出現在 Maestro 看得到的 accessibility tree（要用 `id` / `aria-label` 等會映射的屬性，或改用 Appium webview context）；常無 id、Spannable 文字 clickable=false、第三方頁文字 `important-for-accessibility=false` 抓不到 → 座標或「原頁元素消失」判斷。
25. WebView 下拉（例如虛擬渲染的 select）只有選中項進 accessibility tree → 只能依「順序 × 等高」算座標點選，佈局常數寫在片段註解。
26. 橫滑 WebView tab bar 可能無效 → 改切到「全部」分類用垂直捲動找。
27. Hierarchy 抓元素：`maestro --device <id> hierarchy --compact`。
28. `inputText` 對非 ASCII（天城文、CJK 等）支援有限：先實測；不行就用 ADB Keyboard 類輸入法，或測試資料改用 ASCII 欄位。
