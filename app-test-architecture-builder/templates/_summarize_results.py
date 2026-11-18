#!/usr/bin/env python3
"""M11：解析最近一次（或指定）run 目錄，產生 .last_run_status.json 供 run_failed.sh 使用。

用法：
    python3 scripts/_summarize_results.py                 # 自動挑 test-results/ 最新的 run
    python3 scripts/_summarize_results.py <run_dir>       # 指定（例如 ui_compare/<brand>/<ts>/_raw）

- 用 rglob 找所有 logs/maestro.log（Maestro 會在輸出目錄內再加一層時間戳，深度不固定）
- 判定規則與報表共用 failure_rules.judge()
- key = <flow>@<target>，target = brand/env/platform/locale/flags/form_factor/device（環境變數 TARGET_ID，由 run_suite.sh 組）
  → 同一台裝置輪流跑不同語系 / flag 組合不會互相覆蓋；entry 記錄 target 各欄位，run_failed.sh 依此還原
- 找不到 flow 檔路徑的失敗會印警告並 exit 2（避免重跑時被濾掉造成假綠）
- 與前一次狀態檔「合併」：這次沒跑到的 flow 保留原紀錄（重跑失敗的那幾支不會把整輪結果洗掉）
- RERUN=1（run_failed.sh）且前一次失敗、這次通過 → flaky=true（重跑才通過，不是乾淨的 PASS）；BLOCKED 另記 blocked=true
需要 Python 3.9+。
"""
import json
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows（cp949/cp950/cp932）主控台與管線不亂碼
except Exception:
    pass
from pathlib import Path

import failure_rules  # 同目錄

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".last_run_status.json"


def latest_run() -> Path:
    d = ROOT / "test-results"
    dirs = [p for p in d.iterdir() if p.is_dir()] if d.exists() else []
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


def flow_index() -> dict:
    import flow_index as fi  # 同目錄
    return fi.build_flow_index(ROOT)


def _hist_key(v: dict, cur: list) -> str:
    """歷史紀錄的 flow key：同一個 run 有多個 target 跑同名 flow 時，加上 @platform/locale/device 區分。"""
    name = v.get("flow", "")
    if len(cur) == len({c.get("flow") for c in cur}):
        return name
    t = v.get("target") or {}
    suffix = "/".join(x for x in (t.get("PLATFORM", ""), t.get("LOCALE", ""), t.get("DEVICE", "")) if x)
    return f"{name}@{suffix}" if suffix else name


def _hist_status(v: dict) -> str:
    if v.get("flaky"):
        return "flaky"
    if v["passed"]:
        return "pass"
    return "blocked" if v.get("blocked") else "fail"


def main():
    run_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else latest_run()
    if run_dir is None or not run_dir.exists():
        sys.exit(0)
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    flows = flow_index()
    device = os.environ.get("DEVICE", "")
    target = os.environ.get("TARGET_ID", device)
    target_fields = {k: os.environ.get(k, "") for k in ("BRAND", "TARGET_ENV", "PLATFORM", "LOCALE", "FLAGS", "FORM_FACTOR", "DEVICE", "DEVICE_MODEL", "TIMEOUT_SCALE")}
    missing_path = []
    status = dict(previous)
    # 非 Maestro：讀 *.result.json（tool-adaptation.md §3.1）
    for jp in sorted(run_dir.rglob("*.result.json")):
        try:
            r = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        st = str(r.get("status", "failed")).lower()
        # target 以 JSON 內的欄位優先（一個 run 開多組 capabilities：多平台 / 多語系 / 多裝置時，env 只有一份）
        jt = dict(target_fields)
        for k_env, k_json in (("BRAND", "brand"), ("TARGET_ENV", "env"), ("PLATFORM", "platform"), ("LOCALE", "locale"),
                              ("FLAGS", "flags"), ("FORM_FACTOR", "form_factor"), ("DEVICE", "device"), ("DEVICE_MODEL", "device_model")):
            if r.get(k_json):
                jt[k_env] = str(r[k_json])
        jtarget = r.get("target") or "/".join(jt.get(k, "") for k in ("BRAND", "TARGET_ENV", "PLATFORM", "LOCALE", "FLAGS", "FORM_FACTOR", "DEVICE"))
        key = f"{r.get('name', jp.stem)}@{jtarget}"
        status[key] = {"flow": r.get("name", jp.stem), "path": r.get("path", ""), "device": jt.get("DEVICE", device),
                       "target": jt, "passed": st in ("passed", "flaky_pass"),
                       "blocked": st == "blocked", "flaky": st == "flaky_pass", "run_dir": str(run_dir),
                       "tags": r.get("tags", []),
                       **({"reason": r["reason"]} if r.get("reason") else {})}
    for log in sorted(run_dir.rglob("maestro.log")):
        if log.parent.name != "logs":
            continue
        flow_dir = log.parent.parent
        key = f"{flow_dir.name}@{target}" if target else flow_dir.name
        text = log.read_text(encoding="utf-8", errors="ignore")
        failed, reason = failure_rules.judge(text, flow_dir)
        path = flows.get(flow_dir.name, {}).get("path", "")
        entry = {"flow": flow_dir.name, "path": path, "device": device, "target": target_fields,
                 "passed": not failed, "run_dir": str(run_dir)}
        if failed and not path:
            missing_path.append(flow_dir.name)
        if reason:
            entry["reason"] = reason
        if failed and failure_rules.is_blocked(text):
            entry["blocked"] = True
        # 只有「重跑」（run_failed.sh 設 RERUN=1）才判 flaky；隔天新 build 修好的不是 flaky
        if not failed and os.environ.get("RERUN") == "1" and previous.get(key, {}).get("passed") is False:
            entry["flaky"] = True
        status[key] = entry
    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    cur = [v for v in status.values() if v.get("run_dir") == str(run_dir)]
    n_fail = sum(1 for v in cur if not v["passed"])
    n_flaky = sum(1 for v in cur if v.get("flaky"))
    # M20 結果歷史：每次 run 追加一行（趨勢報表用）；history/ 要放持久位置（進版控、雲端儲存或 CI cache）
    hist = ROOT / "history" / "runs.jsonl"
    hist.parent.mkdir(exist_ok=True)
    import time
    with hist.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_dir": str(run_dir), "target": target,
                             "app_build": os.environ.get("APP_BUILD", ""), "total": len(cur),
                             "failed": sum(1 for v in cur if not v["passed"] and not v.get("blocked")),
                             "blocked": sum(1 for v in cur if v.get("blocked")),
                             "flaky": sum(1 for v in cur if v.get("flaky")),
                             "flows": {_hist_key(v, cur): _hist_status(v) for v in cur}},
                            ensure_ascii=False) + "\n")
    if missing_path:
        print(f"⚠️ 這些失敗的 flow 找不到對應 yaml（重跑會漏掉）：{missing_path}")
    print(f"wrote {OUT} (this run: {len(cur)} flows, {n_fail} failed, {n_flaky} flaky)")
    if missing_path:
        sys.exit(2)


if __name__ == "__main__":
    main()
