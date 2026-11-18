# 去識別化檢查清單

寫範例、模板、skill、交付文件前必做。目標：任何人拿到這些檔案都無法得知原公司、產品、客戶、人員或取得任何存取權。

## 一定要替換的東西

| 類型 | 例子 | 替換成 |
|---|---|---|
| 帳號密碼 / token / cookie 值 | 真實密碼、session id | `<pw>`、`<token>`、`<session>` |
| 內部網址 / 網域 / IP | 後台、API gateway | `https://admin.example.com/` |
| API 路徑 | 公司特有的 endpoint 名稱 | `<query_endpoint>` 或通用名 |
| App 套件名 / bundle id | 真實 applicationId | `com.example.brand_a` |
| 品牌 / 產品 / 客戶名稱 | 品牌縮寫、產品代號 | `brand_a`、`brand_b` |
| 測試帳號 email、交易帳號 id、卡號、錢包地址 | | `qa+brand_a@example.com`、`10000001`、`<wallet_address>` |
| 人名 / 帳號名 / 本機路徑 | 同事姓名、`/Users/<name>/` | 角色名（「QA A」）、`~/project` |
| 內部文件連結 | 公司 wiki / 雲端文件 URL | 刪除或寫「需求文件（內部）」 |
| 截圖 | 含真實資料的畫面 | 不放進 skill；需要就用示意描述 |
| 真實元素 id / 畫面文字 / 業務組合 | 獨特的 resource-id、首頁文案、獨特的業務線組合 | `<close_btn_id>`、泛化描述（「多品牌交易類 App」） |
| 帶日期與「某人決定」的歷史註解 | 模板程式碼裡的決策日期、誰確認 | 只留原因，不留日期與人 |

## 可以保留的東西
- 通用產業術語（入金/出金、渠道類型、KYC）、通用 UI 文字（Continue、Submit、Notice）。
- 工具行為、設計決策、踩坑紀錄、數據型結論（例如「46 份 log 中 7 份漏判」）。

## 交付前自動檢查

```bash
# 在 skill / 交付目錄執行，所有命中都要人工確認
grep -rnEi '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' . | grep -v example.com
grep -rnEi 'https?://' . | grep -vE 'example\.com|get\.maestro\.mobile\.dev|cdn\.jsdelivr|localhost'
grep -rnEi 'password|passwd|secret|token|jsid|cookie' .
grep -rnE '/Users/[a-z]' .
grep -rnE '\b[0-9]{7,}\b' .        # 疑似真實帳號 id / 卡號
# 再加上專案特有的關鍵字清單（品牌縮寫、套件名前綴、內部網域、人名、真實元素 id / 畫面文字）
# ⚠️ 這份關鍵字清單本身就是敏感資訊：只放在本機或私有 repo，不要寫進要分享的 skill
grep -rnEi '<brand1>|<brand2>|<internal-domain>|<person>' .
```
