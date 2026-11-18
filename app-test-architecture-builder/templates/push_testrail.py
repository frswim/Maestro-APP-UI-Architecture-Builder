#!/usr/bin/env python3
"""M16：把本次結果回寫 TestRail（選配模板）。

前提：每支 flow 用 tag 標 TestRail case id，例如 `tags: [smoke, C1234]`（一支 flow 可對應多個 case）。
環境變數（放 CI secret）：TESTRAIL_URL、TESTRAIL_USER、TESTRAIL_API_KEY、TESTRAIL_PROJECT_ID、TESTRAIL_SUITE_ID（單 suite 專案可省）
對應：PASS→Passed(1)、flaky→Passed + 註解、FAIL→Failed(5)、BLOCKED→Blocked(2)。
run 名稱帶 target（brand/env/platform/locale/flags/form_factor/device）+ App build（APP_BUILD）。
注意：只回寫遮罩後的文字（failure_rules / report_mask 規則）；截圖上傳前同樣要遮罩；資料駐留有要求時確認 TestRail 實例的區域。
需要：requests、Python 3.9+
"""
import json
import os
import re
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows（cp949/cp950/cp932）主控台與管線不亂碼
except Exception:
    pass
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_index  # noqa: E402

CASE_TAG = re.compile(r"^C(\d+)$")
STATUS = {"passed": 1, "blocked": 2, "failed": 5}


def main():
    url = os.environ["TESTRAIL_URL"].rstrip("/") + "/index.php?/api/v2/"
    auth = (os.environ["TESTRAIL_USER"], os.environ["TESTRAIL_API_KEY"])
    status = json.loads((ROOT / ".last_run_status.json").read_text(encoding="utf-8"))
    idx = flow_index.build_flow_index(ROOT)
    run_dir = os.environ.get("RUN_DIR_ABS")

    results, case_ids = [], set()
    for key, v in status.items():
        if run_dir and v.get("run_dir") and os.path.realpath(v["run_dir"]) != os.path.realpath(run_dir):
            continue
        tags = v.get("tags") or idx.get(v.get("flow", key.split("@")[0]), {}).get("tags", [])
        for t in tags:
            m = CASE_TAG.match(str(t))
            if not m:
                continue
            cid = int(m.group(1)); case_ids.add(cid)
            sid = STATUS["passed"] if v["passed"] else (STATUS["blocked"] if v.get("blocked") else STATUS["failed"])
            comment = f"target: {key.split('@', 1)[-1]}"
            if v.get("flaky"):
                comment += "\nflaky: passed on rerun"
            if v.get("reason"):
                comment += "\n" + v["reason"]
            results.append({"case_id": cid, "status_id": sid, "comment": comment,
                            "version": os.environ.get("APP_BUILD", "")})
    if not results:
        print("沒有帶 C<id> tag 的結果，略過 TestRail 回寫"); return

    target = os.environ.get("TARGET_ID", "")
    body = {"name": f"UI automation {target} {os.environ.get('APP_BUILD', '')}".strip(),
            "include_all": False, "case_ids": sorted(case_ids)}
    if os.environ.get("TESTRAIL_SUITE_ID"):
        body["suite_id"] = int(os.environ["TESTRAIL_SUITE_ID"])
    run = requests.post(url + f"add_run/{os.environ['TESTRAIL_PROJECT_ID']}", json=body, auth=auth, timeout=30)
    run.raise_for_status()
    rid = run.json()["id"]
    r = requests.post(url + f"add_results_for_cases/{rid}", json={"results": results}, auth=auth, timeout=60)
    r.raise_for_status()
    print(f"✅ TestRail run {rid}：{len(results)} 筆結果")


if __name__ == "__main__":
    main()
