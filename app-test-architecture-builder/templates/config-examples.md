# 設定檔範本（M2 / M3 / M4 / M9 / M14）

## config/brands/brand_a.yaml.example
```yaml
# 扁平 key: value；runner 轉成 -e KEY=VALUE；flow 內 ${key}
# 清單 / 物件不要放這裡 → 放 config/test_data/<brand>/*.js
device_type: "android"          # 必填：android / ios
app_id: "com.example.brand_a"
device: "emulator-5554"
apiBaseUrl: "https://admin.example.com/"
admin_user: "<admin_user>"      # 機密：實檔不進版控，或由 CI secret 產生
admin_pw: "<admin_pw>"
amount: "50"
```

## config/selectors/android/brand_a/common_page.js
```javascript
if (!output.selector) { output.selector = {}; }
output.selector.common_page = {
  navigation: { home_anchor: { text: "<首頁錨點文字>" }, tab_home: { id: "<tab_id>", index: 0 } },
  popup: {
    blocking_dismiss_ids: ["<close_btn_id>", "blocking_popup_dismiss"],   // 後者：與前端約定的通用關閉鈕
    blocking_dismiss_by_title: [
      { title: "<彈窗標題>", button: "<關閉按鈕文字>" },   // regex 全字比對，符號要跳脫
      { title: ".*(isn't responding|沒有回應).*", button: "Wait|等待" }  // 系統 ANR（各語系文字都列）
    ]
  },
  result_page: { back_button: { text: ".*Back.*" } }
};
```

## config/test_data/brand_a/<flow>.js
```javascript
output.<flow>Accounts = [
  {
    user_email: "qa+brand_a@example.com", user_pw: "<pw>",
    cases: [
      { type: "<variant_type>", variant: "<畫面上的名稱，一字不差>", account_id: "<id>" },
      // { type: "...", ... },   // 暫停：行首加 //
    ]
  }
];
```

## config/selector_labels.json
```json
{
  "flow":   { "<page>": "<流程中文名>" },
  "phase":  { "<section>": "<階段中文名>" },
  "action": { "<leaf_key>": "<元素中文名>" },
  "channel_type_labels": { "<variant_type>": "<顯示名>" }
}
```

## config/ui_baseline/<baseline_key>/<checkpoint>/settings.yaml
（`baseline_key` = `<brand>/<platform>/<form_factor>[/<locale>][/<flags>][/<device_model>]`，由 runner 自動組）
```yaml
threshold: 0          # 差異比例上限
failOnDiff: true      # 是否影響最終結果
color_tolerance: 0    # 單像素色差容忍（0~441）
ignore:               # 百分比矩形，用框選工具產生
- {x: 75.8%, y: 91.4%, w: 23.8%, h: 3.7%}
```

## config/report_mask.json（合規遮罩，選配）
```json
{
  "text": [
    {"pattern": "\\b\\d{7,16}\\b", "replace": "****"},
    {"pattern": "(?i)(password|pin|otp)=\\S+", "replace": "\\1=****"}
  ],
  "screenshot_rects": [{"x": "0%", "y": "12%", "w": "100%", "h": "10%"}]
}
```
`text` 套用在報表所有字串與歸檔 log；`screenshot_rects` 在截圖嵌入報表 / 歸檔前塗黑（依畫面位置設定，不同頁面位置不同時只遮共同區塊，或在 flow 中避免截到）。

## .gitignore
```gitignore
# 機密與本機設定
config/brands/*.yaml
!config/brands/*.yaml.example
config/test_data/*/
.env*
# runner 每次切換的 symlink（不進版控）
config/selectors/active
config/test_data/active
# 產出
test-results/
ui_compare/
report*.html
.locks/
.evidence_tmp/
.last_run_status.json
snapshots/
debug_snapshots/
*.log
*.png
*.jpg
*.mp4
# 視覺基線是持久資產 → 從 *.png 救回
!config/ui_baseline/**/*.png
config/ui_baseline/**/history/
# 測試資料用的上傳圖（若要共享）
!config/test_data/receipt.png
# 雜項
__pycache__/
*.pyc
node_modules/
.DS_Store
.idea/
.vscode/
*.bundle
```
注意：`config/test_data/*/` 若要進版控（不含真帳密時），拿掉這行並把帳密移到品牌設定。
