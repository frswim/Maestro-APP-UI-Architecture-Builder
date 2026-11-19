#!/usr/bin/env bash
# 測試結果通知（M9 / M15）—— Slack / Teams / 其他 IM 的 incoming webhook
# 用法：scripts/notify.sh <final_exit 0|1> <target 描述> <報表位置或 URL>
# NOTIFY_WEBHOOK_URL 只從環境變數（CI secret）讀，不寫進任何設定檔
set -u
STATUS="$1"; TARGET="$2"; REPORT="${3:-}"
# NOTIFY_FORMAT=email：走內網 SMTP relay（SMTP_HOST / SMTP_PORT / MAIL_FROM / MAIL_TO），不需要 webhook URL
if [ "${NOTIFY_FORMAT:-}" = "email" ]; then
  python3 "$(dirname "$0")/notify_payload.py" "" email "$STATUS" "$TARGET" "$REPORT" || echo "⚠️ 郵件送出失敗（不影響測試結果）"
  exit 0
fi
[ -z "${NOTIFY_WEBHOOK_URL:-}" ] && exit 0
# 不得出內網時設 NOTIFY_ALLOWED_HOSTS（空白分隔），webhook 主機不在清單內就拒送
if [ -n "${NOTIFY_ALLOWED_HOSTS:-}" ]; then
  HOST=$(echo "$NOTIFY_WEBHOOK_URL" | sed -E 's#^[a-z]+://([^/:]+).*#\1#')
  case " $NOTIFY_ALLOWED_HOSTS " in *" $HOST "*) ;; *) echo "⚠️ 通知主機 $HOST 不在 NOTIFY_ALLOWED_HOSTS，拒送"; exit 0 ;; esac
fi
SUMMARY=$(python3 -c "
import json,os
p='.last_run_status.json'
d=json.load(open(p)) if os.path.exists(p) else {}
rd=os.environ.get('RUN_DIR_ABS')
d={k:v for k,v in d.items() if not rd or os.path.realpath(v.get('run_dir',''))==os.path.realpath(rd)}   # 只算本次 run
f=[k for k,v in d.items() if not v.get('passed')]; fl=[k for k,v in d.items() if v.get('flaky')]
print(f'{len(d)} flows / {len(f)} failed / {len(fl)} flaky' + (' — failed: ' + ', '.join(f[:5]) if f else ''))")
ICON=$([ "$STATUS" = "0" ] && echo "✅" || echo "❌")
TEXT="$ICON UI automation [$TARGET] $SUMMARY${REPORT:+\nReport: $REPORT}"
# 摘要只含 flow 名與數量；不要放帳號、錯誤原文等可能含個資的內容
# NOTIFY_FORMAT=slack（預設，Slack / Google Chat / Mattermost 皆吃 {"text": ...}）| teams | line
#   line：LINE Messaging API push（https://api.line.me/v2/bot/message/push），需 NOTIFY_AUTH_TOKEN（channel access token）
#         與 NOTIFY_TO（bot 加入群組後取得的 groupId）；舊 LINE Notify 已停止服務
#   teams：Teams「Workflows」webhook（舊 Office 365 Connector 已退役）要 Adaptive Card 包在 attachments 裡
PAYLOAD=$(python3 scripts/notify_payload.py "$TEXT" "${NOTIFY_FORMAT:-slack}" 2>/dev/null || python3 "$(dirname "$0")/notify_payload.py" "$TEXT" "${NOTIFY_FORMAT:-slack}")
# NOTIFY_AUTH_TOKEN（選填，放 secret）：需要 Bearer token 的服務（例如 LINE Messaging API push）
AUTH_HEADER=""; [ -n "${NOTIFY_AUTH_TOKEN:-}" ] && AUTH_HEADER="Authorization: Bearer ${NOTIFY_AUTH_TOKEN}"
curl -sS -X POST -H 'Content-Type: application/json' ${AUTH_HEADER:+-H "$AUTH_HEADER"} --data "$PAYLOAD" "$NOTIFY_WEBHOOK_URL" >/dev/null \
  || echo "⚠️ 通知送出失敗（不影響測試結果）"
