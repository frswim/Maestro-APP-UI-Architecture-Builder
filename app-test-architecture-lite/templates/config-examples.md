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
注意：`config/test_data/*/` 若要進版控（不含真帳密時），拿掉這行並把帳密移到品牌設定；保持忽略的話，CI 要從 secret 產生測試資料（見 `ci-github-actions.yml`）。
`requirements.txt` 跟腳本一起放在 `scripts/`（CI 模板用 `pip install -r scripts/requirements.txt`）。
