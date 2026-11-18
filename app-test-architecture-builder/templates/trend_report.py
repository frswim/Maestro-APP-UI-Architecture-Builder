#!/usr/bin/env python3
"""M20：讀 history/runs.jsonl，輸出每週通過率趨勢（history/trend.csv + history/trend.html）。

用法：python3 scripts/trend_report.py [--target <prefix>] [--weeks 12]
通過率 = (total - failed - blocked) / (total - blocked)；flaky 另列（不算進通過率的分母扣除）。
另列「最常失敗 / 最常 flaky 的 flow」前 10 名，給排優先序用。
需要 Python 3.9+；無第三方套件；HTML 不用外部資源（可在內網 / 資料駐留限制下使用）。
"""
import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "history" / "runs.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="", help="只看 target 以此開頭的紀錄（例如 default/staging/android）")
    ap.add_argument("--weeks", type=int, default=12)
    a = ap.parse_args()
    if not HIST.exists():
        sys.exit("沒有 history/runs.jsonl（先跑過 run_suite.sh）")
    weeks = collections.OrderedDict()
    fails, flakies = collections.Counter(), collections.Counter()
    for line in HIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if a.target and not r.get("target", "").startswith(a.target):
            continue
        d = dt.datetime.fromisoformat(r["time"])
        wk = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        w = weeks.setdefault(wk, {"runs": 0, "total": 0, "failed": 0, "blocked": 0, "flaky": 0})
        w["runs"] += 1
        for k in ("total", "failed", "blocked", "flaky"):
            w[k] += r.get(k, 0)
        for f, st in (r.get("flows") or {}).items():
            if st == "fail":
                fails[f] += 1
            elif st == "flaky":
                flakies[f] += 1
    rows = list(weeks.items())[-a.weeks:]
    out_csv = ["week,runs,total,failed,blocked,flaky,pass_rate"]
    html_rows = []
    for wk, w in rows:
        denom = w["total"] - w["blocked"]
        rate = (denom - w["failed"]) / denom if denom else 0
        out_csv.append(f"{wk},{w['runs']},{w['total']},{w['failed']},{w['blocked']},{w['flaky']},{rate:.3f}")
        html_rows.append(f"<tr><td>{wk}</td><td>{w['runs']}</td><td>{w['total']}</td><td>{w['failed']}</td>"
                         f"<td>{w['blocked']}</td><td>{w['flaky']}</td><td><div style='background:#2e7d32;height:12px;"
                         f"width:{rate * 200:.0f}px;display:inline-block'></div> {rate:.1%}</td></tr>")
    (ROOT / "history" / "trend.csv").write_text("\n".join(out_csv) + "\n", encoding="utf-8")
    top = lambda c: "".join(f"<li>{k} — {v}</li>" for k, v in c.most_common(10)) or "<li>-</li>"
    (ROOT / "history" / "trend.html").write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Trend</title>
<style>body{{font-family:sans-serif;padding:20px}}td,th{{padding:4px 10px;border-bottom:1px solid #ddd}}</style></head><body>
<h2>Weekly pass rate {a.target}</h2><table><tr><th>week</th><th>runs</th><th>total</th><th>failed</th><th>blocked</th><th>flaky</th><th>pass rate</th></tr>
{''.join(html_rows)}</table><h3>Most failed</h3><ol>{top(fails)}</ol><h3>Most flaky</h3><ol>{top(flakies)}</ol></body></html>""", encoding="utf-8")
    print("\n".join(out_csv))


if __name__ == "__main__":
    main()
