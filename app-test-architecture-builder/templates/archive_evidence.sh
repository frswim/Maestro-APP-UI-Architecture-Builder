#!/usr/bin/env bash
# M17 稽核證據歸檔 —— 模板
# 用法：scripts/archive_evidence.sh [<run_dir>]   （預設 test-results/ 最新一個）
# 1. 複製 run 目錄到暫存 → 2. 用 config/report_mask.json 的 text 規則遮罩 log/json/xml
# 3. 寫 manifest.json（每個檔案 SHA-256 + build 版本 + 裝置 + 時間）→ 4. 打包 → 5. 上傳內網保存區（WORM/保存年限由保存區設定）
# 截圖遮罩：報表嵌入時已處理；原始截圖若含個資，歸檔前用同一份 screenshot_rects 處理（generate_report.py 的 _embed_png_data_uri 可抽出重用）
set -euo pipefail
cd "$(dirname "$0")/.."
RUN="${1:-$(ls -td test-results/*/ | head -1)}"; RUN="${RUN%/}"
NAME="evidence_$(basename "$RUN")"; TMP=".evidence_tmp/$NAME"
rm -rf "$TMP"; mkdir -p "$TMP"; cp -R "$RUN"/. "$TMP"/
python3 - "$TMP" <<'PY'
import hashlib, json, os, re, sys, time
from pathlib import Path
root = Path(sys.argv[1])
rules = json.loads(Path("config/report_mask.json").read_text()).get("text", []) if Path("config/report_mask.json").exists() else []
for f in root.rglob("*"):
    if f.is_file() and f.suffix in (".log", ".json", ".xml", ".txt", ".html"):
        s = f.read_text(encoding="utf-8", errors="ignore")
        for r in rules:
            s = re.sub(r["pattern"], r.get("replace", "****"), s)
        f.write_text(s, encoding="utf-8")
manifest = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "app_build": os.environ.get("APP_BUILD", ""),
            "device": os.environ.get("DEVICE", ""), "files": {}}
for f in sorted(root.rglob("*")):
    if f.is_file():
        manifest["files"][str(f.relative_to(root))] = hashlib.sha256(f.read_bytes()).hexdigest()
(root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
PY
tar -czf ".evidence_tmp/${NAME}.tar.gz" -C .evidence_tmp "$NAME"
sha256sum ".evidence_tmp/${NAME}.tar.gz" 2>/dev/null || shasum -a 256 ".evidence_tmp/${NAME}.tar.gz"
# 上傳到內網保存區（依公司規定替換）：例如 curl -T ... https://evidence.intranet.example.com/ 或 rsync 到 NAS
echo "✅ 證據包：.evidence_tmp/${NAME}.tar.gz（請上傳保存區後刪除本機暫存）"
