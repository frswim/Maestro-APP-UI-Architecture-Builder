# 參考實作：多品牌金流 App 的 Maestro 自動化（去識別化）

> 這是本 skill 的原始案例。品牌、套件名、網址、帳號、API 路徑、人名都已替換成假值。
> 用途：讓後續 AI 看懂「我們實際怎麼做、為什麼這樣做」。套到新公司時，**照原則改寫，不要照抄值**。

## 0. 案例背景

| 項目 | 內容 |
|---|---|
| App | 多品牌交易類 App，Android（Maestro 2.8），原生殼 + 收銀台 / 表單大量 WebView |
| 品牌 | 數個白牌（`brand_a`、`brand_b`…），同一套流程、不同 applicationId 與文案 |
| 業務流程 | 交易流程 A（payin）、交易流程 B（payout）、次要角色的流程 B；每個流程有 5 種付款方式類型（以下用 `type_a`～`type_e` 代稱，例如卡片、錢包、轉帳類），各類型 UI 步驟不同 |
| 外部步驟 | 送單後要在後台審批；部分渠道跳第三方支付頁；部分要上傳收據圖片 |
| 痛點演進 | ① 5 支複製貼上的獨立 flow → 改資料驅動迴圈；② 定位器寫死 → 外置並依品牌切換；③ 前端不定時加彈窗 → 等錨點 helper；④ 報表誤判 warning、卡死不出報表 → 判定規則 + watchdog；⑤ 畫面跑版沒人發現 → UI Diff（視覺回歸，屬完整版） |
| 團隊 | 小型 QA 團隊，版控受限（不能用線上 remote）→ git bundle 交換 |

訪談對應：從零有幾支零散腳本、Android 原生 + 大量 WebView、多品牌、彈窗很多、後台審核、第三方頁、上傳收據、本機模擬器、報表要可轉寄。→ 核心模組全上（M1～M7、M9、M11～M14），另加完整版的視覺回歸。

## 1. 目錄（實際形狀）

```
config/
  brands/brand_a.yaml                # 扁平設定（不進版控）
  test_data/active -> brand_a        # runner 切換
  test_data/brand_a/{payin.js,payout.js,secondary_role_payout.js}
  test_data/receipt.png              # 上傳用測試圖
  selectors/active -> android/brand_a
  selectors/android/brand_a/{common_page.js,payin_page.js,payout_page.js,secondary_role_page.js}
  selector_labels.json
flows/
  full_cycle/full_cycle.yaml         # 流程 A → 流程 B（runFlow 串接，A 產生的資料供 B 使用）
  payin/payin_channels_loop.yaml
  payout/payout_channels_loop.yaml
subflows/
  common/{wait_anchor_or_dismiss,wait_anchor_retap,dismiss_blocking_popups,
          retry_tap_until_visible,dismiss_launch_popup,login,logout,back_to_home}.yaml
  payin/{go_to_payin,select_account,variant_body_type_a,variant_body_type_b,...}.yaml
  payout/{go_to_payout,select_account,variant_body_*,submit_and_back}.yaml
api/scripts/{admin_login.js,approve_payin.js}
scripts/{run_suite.sh,failure_rules.py,generate_report.py,_summarize_results.py,
         snap.sh,debug_flow.sh,setup_test_files.sh}
setup/setup.sh
docs/{使用者操作手冊.md,使用教學.md}
.claude/skills/<每個子系統一份>/   # 資料驅動迴圈、彈窗防護、報表、定位器、視覺回歸、release notes、封存
```

## 2. 品牌設定（扁平 key-value）

```yaml
# config/brands/brand_a.yaml —— runner 逐行轉成 maestro -e KEY=VALUE；flow 內用 ${key}
# 只能扁平 key: value；清單/物件放 test_data
device_type: "android"            # 必填，決定 selectors/<device_type>/<brand>
app_id: "com.example.brand_a"
device: "emulator-5554"
apiBaseUrl: "https://admin.example.com/"
admin_user: "<admin_user>"
admin_pw: "<admin_pw>"            # 腳本內轉雜湊後送出
user_pw: "<pw_prefix>"            # 密碼含 !! 時拆兩段，避免被 shell / 工具吃掉
user_pw_suffix: "!!"
amount: "50"                      # 預設金額
alt_currency_amount: "10"                  # 依幣別覆寫
form_holder_name: "Test User"     # 表單假資料
```

## 3. 定位器（含彈窗清單）

```javascript
// config/selectors/android/brand_a/common_page.js
if (!output.selector) { output.selector = {}; }
output.selector.common_page = {
  navigation: {
    tab_home:  { id: "<bottom_tab_id>", index: 0 },
    tab_funds: { id: "<bottom_tab_id>", index: 4 },     // 底部 tab 共用 id，用 index 區分（比文字快）
    home_anchor: { text: "<首頁錨點A>|<首頁錨點B>" } // regex：不同品牌首頁錨點不同
  },
  popup: {
    // 阻擋型彈窗：有關閉鈕 id 就放這裡（一次 regex 判斷全部）
    blocking_dismiss_ids: ["<promo_close_id>", "<guide_skip_id>", "blocking_popup_dismiss"],
    // 沒 id 的 WebView 彈窗：「標題 + 按鈕」配對，按鈕在標題下方才點
    blocking_dismiss_by_title: [
      { title: "Notice", button: "Close" },
      { title: "<驗證提示標題>", button: "<稍後按鈕>" }
    ]
  },
  login: {
    // Spannable 文字只有右半邊可點 → 只能座標，註明原因
    login_link_point: { point: "70%,93%" }
  },
  result_page: { back_button: { text: ".*Back.*" } }
};
```

定位器 key 一致性 / labels 缺漏檢查（Node 一行流，CI 也能跑）：

```bash
node -e "
const fs=require('fs');const L=JSON.parse(fs.readFileSync('config/selector_labels.json','utf8'));const miss=new Set();
for(const b of fs.readdirSync('config/selectors/android'))for(const f of fs.readdirSync('config/selectors/android/'+b)){
 global.output={};eval(fs.readFileSync('config/selectors/android/'+b+'/'+f,'utf8'));
 for(const o of Object.values(output.selector))(function w(o){for(const[k,v]of Object.entries(o)){
  const leaf=v===null||typeof v!=='object'||Array.isArray(v)||'text'in v||'id'in v||'point'in v;
  if(leaf){if(!(k in L.action))miss.add('action:'+k)}else{if(!(k in L.phase))miss.add('phase:'+k);w(v)}}})(o)}
console.log([...miss].join('\n')||'none')"
```

## 4. 測試資料（帳號 → case）

```javascript
// config/test_data/brand_a/payin.js
output.payinAccounts = [
  {
    user_email: "qa+brand_a@example.com",
    user_pw: "<pw_prefix>", user_pw_suffix: "!!",
    cases: [
      { type: "type_a",       variant: "<Variant A1>",            account_id: "10000001", currency: "USD" },
      { type: "type_b",     variant: "<Variant B1>",            account_id: "10000001", currency: "USD" },
      // { type: "type_c", variant: "<Variant C1>",              account_id: "10000001", currency: "USD" },  // 暫停：行首 //
      { type: "type_d", variant: "<Variant D1>", bank: "Bank A", account_id: "10000002", currency: "USD" },
      { type: "type_e",       variant: "<Variant E1>",    account_id: "10000001", currency: "USD" }
    ]
  }
];
```

## 5. 迴圈主 flow（骨架）

```yaml
appId: ${app_id}
name: payin_all_channels_loop
tags: [smoke, payin]
---
- launchApp: { stopApp: true }                       # 冷啟動一次，session 保留
- runFlow: ../../subflows/common/dismiss_launch_popup.yaml
- runScript: ../../config/selectors/active/common_page.js   # 只在主 flow 載入
- runScript: ../../config/selectors/active/payin_page.js
- runFlow:                                            # 被彈窗擋住會自動清
    file: ../../subflows/common/wait_anchor_or_dismiss.yaml
    env:
      anchor_text: ${output.selector.common_page.navigation.home_anchor.text}
      timeout_ms: "25000"
- runScript: ../../config/test_data/active/payin.js
- evalScript: ${output.apiBaseUrl = apiBaseUrl}
- runScript: ../../api/scripts/admin_login.js         # 整輪登入後台一次
- evalScript: ${output.accountIndex = 0}
- repeat:
    while: { true: "${output.accountIndex < output.payinAccounts.length}" }
    commands:
      - evalScript: ${output.currentAccount = output.payinAccounts[output.accountIndex]}
      # - runFlow: { file: ../../subflows/common/login.yaml, env: { user_email: ${output.currentAccount.user_email} } }
      - evalScript: ${output.caseIndex = 0}
      - repeat:
          while: { true: "${output.caseIndex < output.currentAccount.cases.length}" }
          commands:
            - evalScript: ${output.currentCase = output.currentAccount.cases[output.caseIndex]}
            - evalScript: ${output.currentType = output.currentCase.type}
            - evalScript: ${output.currentVariant = output.currentCase.variant}
            - evalScript: ${output.currentAccountId = output.currentCase.account_id}
            # 含「冒號+空白」的 JS（三元、物件）整段要加雙引號，否則 YAML 解析失敗
            - evalScript: "${output.currentAmount = (output.currentCase.currency == '<ALT>') ? alt_currency_amount : amount}"
            - runFlow: ../../subflows/payin/go_to_payin.yaml
            - runFlow: ../../subflows/payin/select_account.yaml
            - tapOn: { id: "v-.*-input" }               # 框架動態 id → regex
            - inputText: ${output.currentAmount}
            - runFlow:
                file: ../../subflows/common/wait_anchor_or_dismiss.yaml
                env: { tap_text: "Continue", anchor_id: "<webview_container_id>", timeout_ms: "10000" }
            # 依 type 分派（工具不支援動態檔名 → 每個 type 一個 when 分支）
            - runFlow: { when: { true: '${output.currentType == "type_a"}' },   file: ../../subflows/payin/variant_body_type_a.yaml }
            - runFlow: { when: { true: '${output.currentType == "type_b"}' }, file: ../../subflows/payin/variant_body_type_b.yaml }
            # ...其餘 type
            - runFlow:
                file: ../../subflows/common/wait_anchor_or_dismiss.yaml
                env: { anchor_text: "<結果頁單號標籤>", timeout_ms: "30000", settle_ms: "1000" }
            - extractTextWithAI:                          # 單號沒有可讀元素時才用 AI 擷取（會把截圖送雲端；不得連外的環境不可用）
                query: "Extract the full reference number next to the '<結果頁單號標籤>' label"
                outputVariable: "aiOrderNumber"
            - evalScript: ${output.orderNumber = aiOrderNumber}
            - runScript: ../../api/scripts/approve_payin.js
            - runFlow: ../../subflows/result_back.yaml
            - evalScript: ${output.caseIndex = output.caseIndex + 1}
      - evalScript: ${output.accountIndex = output.accountIndex + 1}
```

變體片段（type_a）重點：等渠道列表錨點（settle 1000）→ 切分類 tab（看不到就橫滑）→ `scrollUntilVisible` 渠道名 → helper：點渠道等確認頁（settle 2000）→ 勾條款 → helper：點送出鈕、`gone_text: <送出鈕文字>`（第三方頁文字常抓不到，用「原頁按鈕消失」判斷跳轉）→ 關第三方頁 → 確認離開。

## 6. 等錨點 helper 呼叫範例

```yaml
# 點渠道 → 等確認頁；被彈窗吃掉 → 清彈窗 → 確實關掉才重點；出現後 2 秒再掃一次
- runFlow:
    file: ../common/wait_anchor_or_dismiss.yaml
    env:
      tap_text: ${output.currentVariant}
      anchor_text: ${output.selector.payin_page.confirmation.payment_amount.text}
      timeout_ms: "30000"
      settle_ms: "2000"

# 流程 B 送出：流程本來就要點的確認鈕用 confirm_text，slice 縮短讓它早點被發現
- runFlow:
    file: ../common/wait_anchor_or_dismiss.yaml
    env:
      tap_text: ${output.selector.payout_page.confirmation.submit_button.text}
      confirm_text: ${output.selector.payout_page.confirmation.okay_button.text}
      anchor_text: ${output.selector.payout_page.confirmation.processing.text}
      timeout_ms: "120000"
      slice_ms: "3000"
```

完整 helper 寫法見 `../templates/wait_anchor_or_dismiss.yaml`（含參數正規化、牆鐘截止、輪數封頂、三種模式、結尾掃描）。

## 7. 後台 API hook（骨架）

```javascript
// api/scripts/approve_payin.js —— Maestro runScript：可用 http.post、output、console.log；不能 require
const baseUrl = output.apiBaseUrl;
const session = output.apiSession;                  // admin_login.js 存的
if (!session) throw new Error('缺少後台 session，請先執行 admin_login.js');

function query(searchType, value) {
  const res = http.post(baseUrl + '<query_endpoint>', {
    headers: { 'Content-Type': 'application/json', 'Cookie': 'session=' + session },
    body: JSON.stringify({ searchType: searchType, query: value, page: 1, limit: 10 })
  });
  const data = JSON.parse(res.body || '{}');
  return (data.rows && data.rows[0]) || null;
}

const hasOrder = !!(output.orderNumber && String(output.orderNumber).trim());
const row = hasOrder ? query('by_order', output.orderNumber)
                     : query('by_account', output.currentAccountId);   // 第三方頁沒單號 → fallback
if (!row) throw new Error('查無符合的待審核訂單');                     // throw → 報表判 FAIL
// ...改狀態 → 審批；回應不是成功就 throw，並在訊息寫明哪一步
```

session 過期的人工更新方式要寫進 `api/HOW_TO_UPDATE_SESSION.md`（從瀏覽器 DevTools → Cookies 複製）。

## 8. 報表判定與情境反查

判定規則與反查邏輯已實作在 `templates/failure_rules.py`、`templates/generate_report.py`：只看阻斷錯誤、偵測執行未完成、從 log 的定位器路徑翻成「流程 / 階段 / 目標」、helper 內失敗從呼叫端 env 反查、case tag 與失敗截圖。導入時只要補齊 `config/selector_labels.json`：
```json
{ "flow":   { "payin_page": "流程A", "common_page": "通用" },
  "phase":  { "channel_selection": "渠道選擇", "confirmation": "確認頁" },
  "action": { "payment_amount": "付款金額", "submit_button": "送出按鈕" },
  "channel_type_labels": { "type_a": "類型A", "type_b": "類型B" } }
```

## 9. 這個案例刻意「沒做」或延後的事（避免後續 AI 誤以為已完成）

- 多帳號切換：登出片段是佔位，資料檔目前只能放 1 組帳號；開跑前需手動登入。
- 強制更新彈窗：自動關閉暫停中。
- Mock：題庫與模板已備，未落地。
- CI：公司規定不能接，改本機執行 + 轉寄單檔報表。
