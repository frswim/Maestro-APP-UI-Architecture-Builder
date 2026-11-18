"""判斷一支 flow 是否「真的失敗」的共用規則（generate_report.py / _summarize_results.py 共用）。

原則：只有「阻斷測試」的錯誤才算 fail，warning 不算。

為什麼不能再用 log 文字比對（舊規則：log 裡有 "Assertion is false" / "FAILED" 就算失敗）：
  Maestro 對 optional 指令（例如 wait_anchor_or_dismiss.yaml 分段等待用的
  `extendedWaitUntil ... optional: true`）失敗時只記 warning、flow 繼續跑：
      ... CommandWarned: Assertion is false: "<anchor text>" is visible
      ... Assert that (Optional) "..." is visible WARNED
  而且這段訊息還會被包進上層 runFlow 的 metadata（insight=Insight(message=Assertion is false..., level=WARNING)），
  所以 "Assertion is false" 字樣出現在 log 裡，不代表測試失敗。

判斷依據（依序）：
  1. 阻斷錯誤：log 有 CommandFailed（Maestro 中斷 flow 的錯誤一定會有），或 commands.json 有 status=FAILED
  2. watchdog 強制結束：run 目錄有 .watchdog_timeout（run_suite.sh 寫入）
  3. 執行未完成：flow 目錄沒有 commands.json
     Maestro 只有在 flow 正常結束（PASS 或 FAIL）時才寫 commands.json；
     沒有它代表 flow 被中斷（Ctrl-C、卡住後被手動停止、程式崩潰）
"""
import json
import os
from pathlib import Path
from typing import Optional

# 這些字串只會出現在真正中斷 flow 的情況
_BLOCKING_MARKERS = (
    "CommandFailed",
    "TestRunner.runCatching-ta8aW1Q: Failed",
    "Failed to run flow",
    "PKIX path building failed",  # SSL 證書驗證失敗
)

WATCHDOG_MARKER = ".watchdog_timeout"

_REASONS = {
    "zh-Hant": ("執行未完成：超過時間上限，被 watchdog 強制結束",
                "執行未完成：flow 中途被中斷（Ctrl-C、卡住後手動停止或程式崩潰），沒有產生結果檔"),
    "ja": ("未完了：制限時間超過により watchdog が強制終了", "未完了：途中で中断（Ctrl-C／手動停止／クラッシュ）、結果ファイルなし"),
    "en": ("Incomplete: killed by watchdog after time limit", "Incomplete: interrupted (Ctrl-C / manual stop / crash), no result file"),
}
_REASONS["ko"] = ("미완료: 제한 시간 초과로 watchdog 이 강제 종료", "미완료: 중간에 중단됨 (Ctrl-C / 수동 중지 / 크래시), 결과 파일 없음")
_R = _REASONS.get(os.environ.get("REPORT_LANG", "zh-Hant"), _REASONS["en"])

# 環境 / 資料問題（BLOCKED）：失敗但不是 App 缺陷 —— 例如前置帳號健康檢查失敗、環境刷新後帳號失效。
# flow 端用「明確的訊息」讓它出現在 log：例如 assertTrue label 或 API hook throw 的訊息以 "[BLOCKED]" 開頭。
# 報表顯示為 BLOCKED（灰色），不計入 FAIL、不算 flaky；exit code 仍非 0（需要人處理環境）。
_BLOCKED_MARKERS = ("[BLOCKED]",)


def is_blocked(log_text: str) -> bool:
    return any(m in log_text for m in _BLOCKED_MARKERS)


def is_warning_line(line: str) -> bool:
    """optional 指令失敗產生的 warning 行（報表找錯誤根源時要跳過）。"""
    return "CommandWarned" in line or line.rstrip().endswith(" WARNED")


def count_warnings(log_text: str) -> int:
    """optional 指令 warning 次數（僅供參考，不影響 PASS/FAIL）。"""
    return log_text.count("CommandWarned")


def _log_has_blocking_error(log_text: str) -> bool:
    return any(m in log_text for m in _BLOCKING_MARKERS)


def _commands_json_has_failed(commands_json: Path) -> bool:
    try:
        data = json.loads(commands_json.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return False

    def walk(node) -> bool:
        if isinstance(node, dict):
            meta = node.get("metadata")
            if isinstance(meta, dict) and meta.get("status") == "FAILED":
                return True
            return any(walk(v) for v in node.values())
        if isinstance(node, list):
            return any(walk(v) for v in node)
        return False

    return walk(data)


def _find_watchdog_marker(flow_dir: Path) -> bool:
    # run_suite.sh 把 marker 寫在 RUN_DIR；flow 目錄在它底下 1~3 層（Maestro 會自己加時間戳子目錄）
    for d in [flow_dir, *list(flow_dir.parents)[:3]]:
        if (d / WATCHDOG_MARKER).exists():
            return True
    return False


def judge(log_text: str, flow_dir: Optional[Path] = None) -> tuple[bool, Optional[str]]:
    """回傳 (是否失敗, 補充原因)。

    補充原因只在「log 裡找不到具體錯誤行」的情況才有值（watchdog / 未完成），
    有阻斷錯誤時回 None，由呼叫端從 log 找根因。
    """
    if _log_has_blocking_error(log_text):
        return True, None
    if flow_dir is not None:
        commands_json = flow_dir / "commands.json"
        if commands_json.exists() and _commands_json_has_failed(commands_json):
            return True, None
        if _find_watchdog_marker(flow_dir):
            return True, _R[0]
        if not commands_json.exists():
            return True, _R[1]
    return False, None


def has_failure(log_text: str, flow_dir: Optional[Path] = None) -> bool:
    return judge(log_text, flow_dir)[0]
