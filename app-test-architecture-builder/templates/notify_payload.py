#!/usr/bin/env python3
"""notify.sh 用：把文字轉成 IM webhook 的 JSON payload（slack|teams|line），或直接寄信（email）。
用法：notify_payload.py <text> <slack|teams|line>
      notify_payload.py "" email <final_exit> <target> <report>   # 讀 .last_run_status.json 組摘要後經 SMTP relay 寄出
email 環境變數：SMTP_HOST、SMTP_PORT（預設 25）、MAIL_FROM、MAIL_TO（逗號分隔）、
               MAIL_ALLOWED_DOMAINS（選填，收件者網域白名單，例如 hospital.example.org）
"""
import json
import sys

text, fmt = sys.argv[1].replace("\\n", "\n"), (sys.argv[2] if len(sys.argv) > 2 else "slack")
if fmt == "email":
    import os, smtplib
    from email.message import EmailMessage
    status, target, report = (sys.argv[3:6] + ["", "", ""])[:3]
    d = {}
    if os.path.exists(".last_run_status.json"):
        d = json.load(open(".last_run_status.json", encoding="utf-8"))
    rd = os.environ.get("RUN_DIR_ABS")
    cur = [v for v in d.values() if not rd or os.path.realpath(v.get("run_dir", "")) == os.path.realpath(rd)]
    failed = [v.get("flow", "") for v in cur if not v.get("passed")]
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    allowed = [x.strip() for x in os.environ.get("MAIL_ALLOWED_DOMAINS", "").split(",") if x.strip()]
    if allowed:
        to = [a for a in to if a.split("@")[-1] in allowed]
    if not to or not os.environ.get("SMTP_HOST"):
        sys.exit(0)
    msg = EmailMessage()
    msg["Subject"] = f"[UI automation] {'PASS' if status == '0' else 'FAIL'} {target}"
    msg["From"], msg["To"] = os.environ.get("MAIL_FROM", "ui-automation@localhost"), ", ".join(to)
    msg.set_content(f"{len(cur)} flows / {len(failed)} failed\n" + "\n".join(failed[:20]) + (f"\n\nReport: {report}" if report else ""))
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "25")), timeout=30) as s:
        s.send_message(msg)
    sys.exit(0)
if fmt == "line":
    import os
    print(json.dumps({"to": os.environ.get("NOTIFY_TO", ""), "messages": [{"type": "text", "text": text[:4900]}]},
                     ensure_ascii=False))
elif fmt == "teams":
    card = {"type": "AdaptiveCard", "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": [{"type": "TextBlock", "text": line, "wrap": True} for line in text.split("\n")]}
    print(json.dumps({"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}]}, ensure_ascii=False))
else:
    print(json.dumps({"text": text}, ensure_ascii=False))
