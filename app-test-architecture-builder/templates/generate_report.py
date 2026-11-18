#!/usr/bin/env python3
"""
產生合併報表(見 skill: references/architecture-modules.md M10/M9)。

讀取:
- test-results/<run>/<flow資料夾>/logs/maestro.log   Maestro 原生功能測試 log(一定會有)
- test-results/<run>/ui_diff/summary.json             UI Diff 結果(見 scripts/ui_diff_check.py)
                                                       這次執行沒開 ui_diff_enabled 就不存在,
                                                       報表會照實顯示「本次沒有 UI Diff 資料」,
                                                       不會假裝有資料硬畫圖表。

輸出:
- test-results/<run>/report_merged.html

用法:
    python3 scripts/generate_report.py                # 自動挑 test-results/ 底下最新的 run
    python3 scripts/generate_report.py <run_dir>       # 指定某一次 run(可以是舊資料,見下方)

備註:這支腳本可以直接套用在 UI Diff 功能上線前累積的舊 test-results/<run>/ 資料 —— 那些
run 本來就沒有 ui_diff/summary.json,報表會自動退化成「只有功能測試結果」的版本,不會報錯。

圖片是用 base64 直接內嵌進 HTML(不是 <img src="相對路徑">),所以這份報表可以整份檔案
單獨複製、搬到別的地方、寄給別人,圖片都還在,不會因為離開專案資料夾就變成死圖。
代價是檔案會比較大(截圖數量多時,幾 MB 是正常的)。
"""
import base64
import json
import re
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows（cp949/cp950/cp932）主控台與管線不亂碼
except Exception:
    pass
from datetime import datetime
from pathlib import Path
from typing import Optional

import failure_rules  # 同目錄；python3 scripts/xxx.py 執行時 scripts/ 會在 sys.path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "test-results"

TIME_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})")


# ---------------------------------------------------------------------------
# flow 資料夾名稱 -> 原始 yaml 路徑 / tags(跟 _summarize_results.py 的作法一致)
# ---------------------------------------------------------------------------
def build_flow_index() -> dict:
    import flow_index  # 同目錄
    return flow_index.build_flow_index(ROOT)


def has_failure(log_text: str) -> bool:
    """只有阻斷測試的錯誤才算失敗；optional 指令的 warning（CommandWarned / WARNED）不算。

    規則集中在 scripts/failure_rules.py，跟 _summarize_results.py 共用。
    只看 log 文字（不看 commands.json）；完整判斷請用 failure_rules.judge(log_text, flow_dir)。
    """
    return failure_rules.has_failure(log_text)


def estimate_duration_seconds(log_text: str) -> Optional[float]:
    """用 log 裡第一行跟最後一行的時間戳算耗時,只是粗估,不是精確計時。"""
    times = TIME_RE.findall(log_text)
    if len(times) < 2:
        return None
    fmt = "%H:%M:%S.%f"
    try:
        first = datetime.strptime(times[0], fmt)
        last = datetime.strptime(times[-1], fmt)
    except ValueError:
        return None
    delta = (last - first).total_seconds()
    return delta if delta >= 0 else None


# ---------------------------------------------------------------------------
# 錯誤分析（純 post-processing；細節見 skill 的 architecture-modules.md
# ---------------------------------------------------------------------------
_SELECTOR_LABELS_CACHE: Optional[dict] = None


def _selector_labels() -> dict:
    global _SELECTOR_LABELS_CACHE
    if _SELECTOR_LABELS_CACHE is None:
        p = ROOT / "config" / "selector_labels.json"
        _SELECTOR_LABELS_CACHE = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _SELECTOR_LABELS_CACHE


def _pretty_key(k: str) -> str:
    return k.replace("_", " ").title()


def _label(kind: str, key: str) -> str:
    return _selector_labels().get(kind, {}).get(key) or _pretty_key(key)


def resolve_selector_context(path: str) -> dict:
    """`checkout_page.address_form.submit` → {flow, phase, action}."""
    segs = path.split(".") if path else []
    return {
        "flow": _label("flow", segs[0]) if segs else None,
        "phase": " → ".join(_label("phase", m) for m in segs[1:-1]) if len(segs) >= 3 else None,
        "action": _label("action", segs[-1]) if len(segs) >= 2 else (_label("flow", segs[0]) if segs else None),
    }


# 錯誤根源行：最後一個 [ERROR] ... CommandFailed
_ERROR_LINE_RE = re.compile(
    r"^(\d{2}:\d{2}:\d{2}\.\d{3}[^\n]*?\[ERROR\][^\n]*?CommandFailed:[^\n]*)$",
    re.MULTILINE,
)

# 執行過的最內層失敗命令（FAILED 行）
_FAILED_LINE_RE = re.compile(
    r"^(\d{2}:\d{2}:\d{2}\.\d{3}[^\n]*?)\s+FAILED\s*$",
    re.MULTILINE,
)

# 有意義的 selector 引用：支援 `output.selector.page.…` 或 `output.page.…`（舊 flow）
# 頁面名稱清單：預設取 selector_labels.json 的 "flow" keys（新增頁面只要補 labels）；
# labels 不存在時退回任何 *_page
def _build_selector_ref_re():
    pages = list(_selector_labels().get("flow", {}).keys())
    page_pat = "|".join(re.escape(p) for p in pages) if pages else r"[a-z_]+_page"
    return re.compile(r"output\.(?:selector\.)?(" + page_pat + r")((?:\.[a-z_][a-z0-9_]*)+)")


_SELECTOR_REF_RE = _build_selector_ref_re()

# 動態指派給 output.currentType 的字面值：從 evalScript / condition 的字面 `output.currentType == "type_a"`
_CURRENT_TYPE_RE = re.compile(r'output\.currentType\s*==\s*"([a-z_]+)"')


def _find_root_error(log_text: str) -> Optional[tuple[int, str]]:
    last = None
    for m in _ERROR_LINE_RE.finditer(log_text):
        last = m
    if last:
        return last.start(), last.group(1).strip()
    # fallback：沒有 [ERROR] 但有 Assertion is false / Element not found
    # 跳過 optional 指令的 warning 行（CommandWarned / WARNED），那些不是中斷測試的原因
    for pat in (
        r"^(\d{2}:\d{2}:\d{2}\.\d{3}[^\n]*Assertion is false[^\n]*)$",
        r"^(\d{2}:\d{2}:\d{2}\.\d{3}[^\n]*Element not found[^\n]*)$",
    ):
        matches = [m for m in re.finditer(pat, log_text, re.MULTILINE)
                   if not failure_rules.is_warning_line(m.group(1))]
        if matches:
            m = matches[-1]
            return m.start(), m.group(1).strip()
    return None


def _last_selector_before(log_text: str, error_pos: int) -> Optional[tuple[str, Optional[str], int]]:
    """從錯誤位置往上找最近一個真正被執行到的命令中出現的 selector 引用。

    只掃 error 前的 FAILED 行，避免抓到 log 中內嵌的 selector JS 定義。
    """
    search = log_text[:error_pos]
    best = None
    for fm in _FAILED_LINE_RE.finditer(search):
        line = fm.group(0)
        # 跳過巨型 wrapper（Repeat / Run flow / Run subflow 這種只是傳遞失敗）
        skip = any(kw in line for kw in ("Repeat while", "Run flow when ", "Run ../"))
        for sm in _SELECTOR_REF_RE.finditer(line):
            page, rest = sm.group(1), sm.group(2)
            parts = rest.lstrip(".").split(".")
            leaf = parts[-1] if parts[-1] in ("text", "id", "point", "index") else None
            path_parts = [page] + (parts[:-1] if leaf else parts)
            if len(path_parts) < 2:
                continue
            path = ".".join(path_parts)
            # 深度優先取最後一個非 wrapper 的 selector；wrapper 只在沒別的可選時使用
            if not skip or best is None:
                best = (path, leaf, fm.start())
    return best


# 共用等待 helper：內部命令只看得到 ${output.waAnchor} 這類中繼變數，看不到原本的 selector 路徑，
# 失敗時改從「呼叫 helper 那一行」的 metadata env 反查（例如 env={anchor_text=${output.selector.…}}）
_HELPER_FLOW_RE = r"(?:wait_anchor_or_dismiss|retry_tap_until_visible)\.yaml"
_HELPER_FAILED_RE = re.compile(rf"^[^\n]*Run (\S*{_HELPER_FLOW_RE}) FAILED\s*$", re.MULTILINE)
# 依「最能代表等待目標」的順序挑 env：先錨點，最後才是點擊目標
_HELPER_ENV_KEYS = ("anchor_text", "anchor_id", "gone_text", "success_anchor", "tap_text", "target_text")
# 錯誤原文裡的實際值：Assertion is false: "X" is visible / id: X is visible
_ERROR_VALUE_RE = re.compile(r'Assertion is false: (?:"(.+?)"|id: (\S+)) is (?:not )?visible')


def _helper_selector_before(log_text: str, error_pos: int, error_line: str) -> Optional[tuple[str, Optional[str], Optional[str], int]]:
    """失敗發生在共用等待 helper 內時，回傳 (path, leaf, value, pos)；否則 None。"""
    search = log_text[:error_pos]
    fails = list(_HELPER_FAILED_RE.finditer(search))
    if not fails:
        return None
    fm = fails[-1]
    helper = re.escape(fm.group(1))
    metas = list(re.finditer(rf"^[^\n]*Run {helper} metadata[^\n]*$", search[:fm.start()], re.MULTILINE))
    if not metas:
        return None
    meta_line = metas[-1].group(0)
    for key in _HELPER_ENV_KEYS:
        km = re.search(rf"[{{,\s]{key}=([^,}}]*)", meta_line)
        if not km:
            continue
        sm = _SELECTOR_REF_RE.search(km.group(1))
        if not sm:
            continue
        page, rest = sm.group(1), sm.group(2)
        parts = rest.lstrip(".").split(".")
        leaf = parts[-1] if parts[-1] in ("text", "id", "point", "index") else None
        path_parts = [page] + (parts[:-1] if leaf else parts)
        if len(path_parts) < 2:
            continue
        vm = _ERROR_VALUE_RE.search(error_line)
        value = (vm.group(1) or vm.group(2)) if vm else None
        return ".".join(path_parts), leaf, value, fm.start()
    return None


_ELEMENT_FIELDS = "textRegex|idRegex|size|below|above|leftOf|rightOf|containsChild|containsDescendants|traits|index|enabled|optional|selected|checked|focused|childOf|css"


def _grab_selector_value(log_text: str, from_pos: int, path: str, leaf: Optional[str]) -> Optional[str]:
    """抓 selector 展開後的實際值。優先找命名匹配的 metadata 行，避免撈到附近其他命令。"""
    window = log_text[max(0, from_pos - 8000): from_pos + 500]

    ref_needle = re.escape(path)
    meta_line_re = re.compile(
        rf"output\.(?:selector\.)?{ref_needle}(?:\.(?:text|id|point|index))?[^\n]*?metadata\s+CommandMetadata\([^\n]*",
    )
    matches = list(meta_line_re.finditer(window))
    if matches:
        line = matches[-1].group(0)
    else:
        line = window  # 退而求其次

    text_m = re.search(rf"textRegex=(.+?),\s*(?:{_ELEMENT_FIELDS})=", line)
    id_m = re.search(rf"idRegex=(.+?),\s*(?:{_ELEMENT_FIELDS})=", line)
    pt_m = re.search(r"RelativePoint\(x=([0-9.]+),\s*y=([0-9.]+)\)", line)

    def _ok(m):
        return m and m.group(1).strip() not in ("", "null")

    if leaf == "text" and _ok(text_m):
        return text_m.group(1).strip()
    if leaf == "id" and _ok(id_m):
        return id_m.group(1).strip()
    if leaf == "point" and pt_m:
        return f"{pt_m.group(1)}, {pt_m.group(2)}"
    # 沒有指定 leaf 或該 leaf 沒抓到，回落到任何一個非 null
    if _ok(text_m):
        return text_m.group(1).strip()
    if _ok(id_m):
        return id_m.group(1).strip()
    if pt_m:
        return f"{pt_m.group(1)}, {pt_m.group(2)}"
    return None


def _extract_case_tag(log_text: str, before_pos: int) -> dict:
    """從錯誤前的 log 抓 case tag：channel_type + case_index。"""
    window = log_text[:before_pos]

    # channel_type：最後一個 `output.currentType == "X"` 命中
    types = _CURRENT_TYPE_RE.findall(window)
    channel_type = types[-1] if types else "unknown"

    # case_index：數執行過幾次 `${output.currentCase = output.currentAccount.cases[output.caseIndex]}` COMPLETED
    # 第 N 次執行 → case_index = N - 1
    #（比對 RUNNING 更穩，避免匯入時的定義字串被算進去）
    case_start_count = len(
        re.findall(
            r"Run \$\{output\.currentCase = output\.currentAccount\.cases\[output\.caseIndex\]\}\s+COMPLETED",
            window,
        )
    )
    case_index = case_start_count - 1 if case_start_count > 0 else -1

    return {"channel_type": channel_type, "case_index": case_index}


def analyze_flow_error(log_text: str) -> Optional[dict]:
    """回傳單一錯誤報告，或 None（沒偵測到根因錯誤）。"""
    root = _find_root_error(log_text)
    if not root:
        return None
    err_pos, err_line = root
    tag = _extract_case_tag(log_text, err_pos)

    # 失敗在共用等待 helper 內 → 用呼叫端 env 的 selector（比 helper 內部的中繼變數有意義）
    helper_sel = _helper_selector_before(log_text, err_pos, err_line)
    if helper_sel:
        path, leaf, value, _ = helper_sel
        full_ref = f"output.selector.{path}" + (f".{leaf}" if leaf else "")
        return {
            "kind": "selector",
            "error_line": err_line,
            "selector_path": full_ref,
            "selector_value": value,
            "context": resolve_selector_context(path),
            "tag": tag,
        }

    sel = _last_selector_before(log_text, err_pos)
    if sel:
        path, leaf, sel_pos = sel
        context = resolve_selector_context(path)
        value = _grab_selector_value(log_text, sel_pos, path, leaf)
        full_ref = f"output.selector.{path}" + (f".{leaf}" if leaf else "")
        return {
            "kind": "selector",
            "error_line": err_line,
            "selector_path": full_ref,
            "selector_value": value,
            "context": context,
            "tag": tag,
        }
    return {"kind": "other", "error_line": err_line, "tag": tag}


_STEP_NUM_RE = re.compile(r"step-(\d+)-")


def get_error_screenshots(flow_dir: Path) -> list:
    """收集 flow 目錄下所有 PNG，附上絕對路徑供 base64 內嵌用。"""
    screenshots = []
    for png in sorted(flow_dir.glob("*.png")):
        screenshots.append({
            "name": png.name,
            "abs_path": str(png),
            "path": str(png.relative_to(flow_dir.parent.parent)),
            "type": "error" if "error_" in png.name.lower() else "default",
        })
    steps_dir = flow_dir / "screenshots"
    if steps_dir.exists():
        for png in sorted(steps_dir.glob("*.png")):
            m = _STEP_NUM_RE.match(png.name)
            screenshots.append({
                "name": f"screenshots/{png.name}",
                "abs_path": str(png),
                "path": str(png.relative_to(flow_dir.parent.parent)),
                "type": "step",
                "step_no": int(m.group(1)) if m else -1,
            })
    take_dir = flow_dir / "takeScreenshot"
    if take_dir.exists():
        for png in sorted(take_dir.glob("*.png")):
            screenshots.append({
                "name": f"takeScreenshot/{png.name}",
                "abs_path": str(png),
                "path": str(png.relative_to(flow_dir.parent.parent)),
                "type": "manual",
            })
    return screenshots


def _pick_failure_screenshot(screenshots: list) -> Optional[dict]:
    """挑失敗當下最相關的一張：優先 error_*，再挑 step 編號最大的一張，最後任何一張。"""
    if not screenshots:
        return None
    for s in screenshots:
        if s.get("type") == "error":
            return s
    steps = [s for s in screenshots if s.get("type") == "step"]
    if steps:
        return max(steps, key=lambda s: s.get("step_no", -1))
    return screenshots[-1]


def _embed_png_data_uri(abs_path: str) -> Optional[str]:
    try:
        data = Path(abs_path).read_bytes()
    except OSError:
        return None
    rects = _mask_rules().get("screenshot_rects")
    if rects:
        try:
            import io
            from PIL import Image, ImageDraw
            img = Image.open(io.BytesIO(data)).convert("RGB")
            w, h = img.size
            d = ImageDraw.Draw(img)
            pct = lambda v: float(str(v).rstrip("%")) / 100.0
            for r in rects:
                x, y = pct(r["x"]) * w, pct(r["y"]) * h
                d.rectangle([x, y, x + pct(r["w"]) * w, y + pct(r["h"]) * h], fill=(0, 0, 0))
            buf = io.BytesIO(); img.save(buf, format="PNG"); data = buf.getvalue()
        except Exception:
            return None   # 遮罩失敗就不嵌圖，寧可缺圖也不外洩
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _flaky_names(run_dir: Optional[Path] = None) -> dict:
    """讀 .last_run_status.json（runner 先跑 _summarize_results.py 再產報表），取本次 flaky 的 flow 名稱。"""
    p = ROOT / ".last_run_status.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {v.get("flow", k.split("@")[0]): True for k, v in d.items()
            if v.get("flaky") and (run_dir is None or v.get("run_dir") == str(run_dir))}


def collect_functional_results(run_dir: Path, flow_index: dict) -> list:
    """遞迴找遍 run_dir 底下所有 logs/maestro.log，不假設固定深度。

    實測發現:指定 --test-output-dir 時，Maestro 會在裡面再自己加一層時間戳
    子資料夾（例如 <run_dir>/<YYYY-MM-DD_HHMMSS>/<flow_name>/logs/maestro.log），不是一定
    直接 <run_dir>/<flow_name>/logs/maestro.log 這種固定深度。用 rglob 遞迴掃描，
    log 檔案的上一層資料夾名稱就是 flow_name，跟實際巢狀幾層無關。
    """
    results = []
    seen_flow_dirs = set()
    for log_path in sorted(run_dir.rglob("maestro.log")):
        if log_path.parent.name != "logs":
            continue
        flow_dir = log_path.parent.parent
        if flow_dir in seen_flow_dirs:
            continue
        seen_flow_dirs.add(flow_dir)

        flow_name = flow_dir.name
        meta = flow_index.get(flow_name, {"path": "", "tags": []})
        text = log_path.read_text(encoding="utf-8", errors="ignore")

        error_screenshots = get_error_screenshots(flow_dir)
        # 只有阻斷測試的錯誤才算 FAIL；optional 指令的 warning 不算（規則見 scripts/failure_rules.py）
        failed, fail_reason = failure_rules.judge(text, flow_dir)
        blocked = failure_rules.is_blocked(text)
        error_report = analyze_flow_error(text) if failed else None
        if failed and not error_report and fail_reason:
            # 沒有具體錯誤行（被中斷 / watchdog）：用原因當錯誤原文，tag 取 log 結尾當下跑到的 case
            error_report = {"kind": "other", "error_line": fail_reason,
                            "tag": _extract_case_tag(text, len(text))}

        results.append({
            "flaky": _flaky_names(run_dir).get(flow_name, False),
            "name": flow_name,
            "path": meta["path"],
            "tags": meta["tags"],
            "passed": not failed,
            "blocked": failed and blocked,
            "duration": estimate_duration_seconds(text),
            "error_report": error_report,
            "error_screenshots": error_screenshots,
            "log_path": str(log_path.relative_to(run_dir.parent)),
        })
    return results


# ---------------------------------------------------------------------------
# 非 Maestro 工具的輸入：<run_dir>/**/*.result.json（schema 見 tool-adaptation.md §3.1）
# 有這種檔案就用它，不解析 maestro.log
# ---------------------------------------------------------------------------
def collect_json_results(run_dir: Path) -> list:
    results = []
    for jp in sorted(run_dir.rglob("*.result.json")):
        try:
            r = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        status = str(r.get("status", "failed")).lower()
        passed = status in ("passed", "flaky_pass")
        report = None
        if not passed:
            tag = {"channel_type": r.get("variant_type", "unknown"), "case_index": r.get("case_index", -1)}
            key = r.get("locator_key")
            if key:
                path = key.replace("output.selector.", "")
                report = {"kind": "selector", "error_line": r.get("reason", ""), "selector_path": key,
                          "selector_value": r.get("locator_value"), "context": resolve_selector_context(path), "tag": tag}
            else:
                report = {"kind": "other", "error_line": r.get("reason", ""), "tag": tag}
        shots = []
        for sp in r.get("screenshots", []):
            ap = (jp.parent / sp) if not Path(sp).is_absolute() else Path(sp)
            shots.append({"name": Path(sp).name, "abs_path": str(ap), "path": sp, "type": "error" if not passed else "manual"})
        results.append({
            "name": r.get("name", jp.stem) + "".join(f" [{r[k]}]" for k in ("platform", "locale", "device") if r.get(k)),
            "path": r.get("path", ""), "tags": r.get("tags", []),
            "passed": passed, "blocked": status == "blocked", "flaky": status == "flaky_pass",
            "duration": r.get("duration_s"), "error_report": report, "error_screenshots": shots,
            "log_path": str(jp.relative_to(run_dir.parent)),
        })
    return results


def resolve_run_ts(functional_dir: Path) -> str:
    """從傳入的功能測試結果目錄推回這次執行的 run_timestamp。

    一般跑法(沒開 UI Diff):傳入的就是 test-results/<run_ts> 本身，.name 直接是 run_ts。
    UI Diff 開啟時:傳入的是 ui_compare/<brand>/<run_ts>/_raw，.name 會是 "_raw"，
    要往上一層拿 run_ts(見 scripts/ui_diff_check.py 的 run_dir.name 邏輯，兩邊要對齊）。
    """
    return functional_dir.parent.name if functional_dir.name == "_raw" else functional_dir.name


def load_ui_diff_summary(run_ts: str) -> Optional[dict]:
    """ui_diff_check.py 一律把 summary.json 寫在 test-results/<run_ts>/ui_diff/ 底下，
    跟功能測試 log 實際放在哪裡(test-results/ 或 ui_compare/.../_raw/)無關。
    """
    summary_path = RESULTS_DIR / run_ts / "ui_diff" / "summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def latest_run_dir() -> Optional[Path]:
    if not RESULTS_DIR.exists():
        return None
    dirs = [p for p in RESULTS_DIR.iterdir() if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime, default=None)


# ---------------------------------------------------------------------------
# HTML 產生(Bootstrap + 純 CSS conic-gradient 圓餅圖)
# ---------------------------------------------------------------------------
STATUS_BADGE_CLASS = {
    "PASS": "badge-pass",
    "FAIL": "badge-fail",
    "MISSING_BASELINE": "badge-missing",
    "ERROR": "badge-error",
    "LAYOUT_MISMATCH": "badge-layout",
    "NO_BASELINE": "badge-nobaseline",
    "UPDATED": "badge-nobaseline",
}


# case tag 顏色：依專案的 variant type 調整；沒列到的用 dark
_CHANNEL_BADGE_COLOR = {
    "type_a": "warning",
    "type_b": "success",
    "type_c": "info",
    "type_d": "primary",
    "type_e": "danger",
}


def _render_case_tag(tag: dict) -> str:
    ct = (tag or {}).get("channel_type", "unknown")
    ci = (tag or {}).get("case_index", -1)
    color = _CHANNEL_BADGE_COLOR.get(ct, "dark")
    ct_label = _selector_labels().get("channel_type_labels", {}).get(ct, ct.upper())
    ci_str = f"#{ci}" if ci >= 0 else "#?"
    return f'<span class="badge bg-{color} me-1">Case {ci_str} · {ct_label}</span>'


# ---------------------------------------------------------------------------
# 遮罩（合規需求）：config/report_mask.json
#   { "text": [{"pattern": "\\b\\d{7,}\\b", "replace": "****"}],   # 帳號、卡號、姓名、OTP 等
#     "screenshot_rects": [{"x": "0%", "y": "10%", "w": "100%", "h": "8%"}] }  # 失敗截圖嵌入前塗黑
# 沒有這個檔案 = 不遮罩。log 原檔歸檔前要另外用同一份規則處理（見 M17）。
# ---------------------------------------------------------------------------
_MASK_CACHE: Optional[dict] = None


def _mask_rules() -> dict:
    global _MASK_CACHE
    if _MASK_CACHE is None:
        p = ROOT / "config" / "report_mask.json"
        _MASK_CACHE = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _MASK_CACHE


def mask_text(s: str) -> str:
    for rule in _mask_rules().get("text", []):
        s = re.sub(rule["pattern"], rule.get("replace", "****"), s)
    return s


def _html_escape(s) -> str:
    s = mask_text(str(s if s is not None else ""))
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# 報表語言：REPORT_LANG=zh-Hant | ja | en | ko（預設 zh-Hant；未知語言退回 en）；要改字串就改這張表
# ---------------------------------------------------------------------------
import os

_I18N = {
    "zh-Hant": {"title": "測試報表", "func": "功能測試結果", "ui": "UI Diff Checkpoint 結果", "flows": "Flow 清單",
                "ctx": "錯誤情境", "flow": "流程", "phase": "當前階段", "action": "動作 or 預期目標",
                "detail": "詳細資料", "err": "錯誤", "log": "日誌", "raw": "錯誤原文",
                "no_ui": "本次執行沒有 UI Diff 資料", "no_flow": "這個 run 目錄底下找不到任何 flow 結果。",
                "blocked": "環境/資料問題（BLOCKED，不計入失敗）", "unknown": "未知",
                "no_path": "(找不到對應的 flow 檔案)", "zoom": "點圖放大看原始解析度", "threshold": "閥值",
                "tolerance": "色彩容忍值", "no_ui_hint": "(ui_diff_enabled 未開啟)", "no_err": "測試失敗但沒偵測到具體錯誤", "ui_note": "每個 checkpoint 都顯示 Baseline / Actual / Diff（缺的用灰框標明原因）。", "ui_mode": "模式", "no_cp": "沒有任何 checkpoint 結果。", "h1": "Flow + UI Diff 執行摘要", "total": "Flow 總數", "failed": "失敗", "succeeded": "成功", "img_missing": "圖片檔案讀不到", "none": "無", "baseline": "基線", "shot": "截圖", "diff": "Diff 圖", "miss_base": "從未建立過基線，帶 --capture-baseline 重跑一次補建", "layout": "基線跟這次截圖尺寸不同，未逐像素比對", "capture": "建立基線模式：這次沒有比對，只寫入/更新基線", "flaky": "重跑才通過（flaky）"},
    "ja": {"title": "テストレポート", "func": "機能テスト結果", "ui": "UI Diff チェックポイント結果", "flows": "フロー一覧",
           "ctx": "エラー状況", "flow": "フロー", "phase": "フェーズ", "action": "操作／期待対象",
           "detail": "詳細", "err": "エラー", "log": "ログ", "raw": "エラー原文",
           "no_ui": "今回の実行には UI Diff データがありません", "no_flow": "この実行ディレクトリにフロー結果がありません。",
           "blocked": "環境／データ起因（BLOCKED、失敗に計上しない）", "unknown": "不明",
           "no_path": "(対応するフローファイルが見つかりません)", "zoom": "クリックで原寸表示", "threshold": "しきい値",
           "tolerance": "色許容値", "no_ui_hint": "(ui_diff_enabled が無効)", "no_err": "失敗したが具体的なエラーを検出できません", "ui_note": "各チェックポイントに Baseline / Actual / Diff を表示（欠落は灰色枠で理由を表示）。", "ui_mode": "モード", "no_cp": "チェックポイント結果はありません。", "h1": "フロー + UI Diff 実行サマリー", "total": "フロー数", "failed": "失敗", "succeeded": "成功", "img_missing": "画像を読み込めません", "none": "なし", "baseline": "ベースライン", "shot": "スクリーンショット", "diff": "差分画像", "miss_base": "ベースライン未作成。--capture-baseline で再実行", "layout": "ベースラインとサイズが異なるため比較せず", "capture": "ベースライン作成モード：比較なし", "flaky": "再実行で成功（flaky）"},
    "en": {"title": "Test Report", "func": "Functional results", "ui": "UI Diff checkpoints", "flows": "Flows",
           "ctx": "Failure context", "flow": "Flow", "phase": "Phase", "action": "Action / expected target",
           "detail": "Details", "err": "Error", "log": "Log", "raw": "Raw error",
           "no_ui": "No UI Diff data in this run", "no_flow": "No flow results found in this run directory.",
           "blocked": "Environment/data issue (BLOCKED, not counted as failure)", "unknown": "unknown",
           "no_path": "(flow file not found)", "zoom": "click to view full size", "threshold": "threshold",
           "tolerance": "color tolerance", "no_ui_hint": "(ui_diff_enabled is off)", "no_err": "Failed, but no specific error was detected", "ui_note": "Each checkpoint shows Baseline / Actual / Diff (missing images are shown as grey boxes with the reason).", "ui_mode": "mode", "no_cp": "No checkpoint results.", "h1": "Flow + UI Diff Execution Summary", "total": "Total Flows", "failed": "Failed", "succeeded": "Succeeded", "img_missing": "image not readable", "none": "no", "baseline": "baseline", "shot": "screenshot", "diff": "diff image", "miss_base": "No baseline yet; rerun with --capture-baseline", "layout": "Size differs from baseline; not compared pixel by pixel", "capture": "Capture mode: baseline written/updated, not compared", "flaky": "passed on rerun (flaky)"},
}
_I18N["ko"] = {"title": "테스트 리포트", "func": "기능 테스트 결과", "ui": "UI Diff 체크포인트 결과", "flows": "플로우 목록",
               "ctx": "오류 상황", "flow": "플로우", "phase": "단계", "action": "동작 / 기대 대상", "detail": "상세",
               "err": "오류", "log": "로그", "raw": "오류 원문", "no_ui": "이번 실행에는 UI Diff 데이터가 없습니다",
               "no_flow": "이 실행 디렉터리에 플로우 결과가 없습니다.", "blocked": "환경/데이터 문제 (BLOCKED, 실패로 집계하지 않음)",
               "unknown": "알 수 없음", "no_path": "(플로우 파일을 찾을 수 없음)", "zoom": "클릭하여 원본 크기로 보기",
               "threshold": "임계값", "tolerance": "색상 허용치", "no_ui_hint": "(ui_diff_enabled 꺼짐)",
               "no_err": "실패했지만 구체적인 오류를 찾지 못했습니다", "ui_note": "각 체크포인트에 Baseline / Actual / Diff 를 표시합니다.",
               "ui_mode": "모드", "no_cp": "체크포인트 결과가 없습니다.", "h1": "플로우 + UI Diff 실행 요약", "total": "전체 플로우", "failed": "실패", "succeeded": "성공", "img_missing": "이미지를 읽을 수 없음", "none": "없음", "baseline": "기준선", "shot": "스크린샷", "diff": "차이 이미지", "miss_base": "기준선 없음. --capture-baseline 으로 다시 실행", "layout": "기준선과 크기가 달라 비교하지 않음", "capture": "기준선 생성 모드: 비교 없음", "flaky": "재실행 후 통과 (flaky)"}
# 新增語言：複製 "en" 一份翻譯後加進 _I18N；未知語言退回 en 並警告
REPORT_LANG = os.environ.get("REPORT_LANG", "zh-Hant")
if REPORT_LANG not in _I18N:
    print(f"⚠️ REPORT_LANG={REPORT_LANG} 沒有字串表，改用 en（在 generate_report.py 的 _I18N 補上）", file=sys.stderr)
    REPORT_LANG = "en"
T = _I18N[REPORT_LANG]


def _render_error_details(f: dict) -> str:
    """兩種錯誤 layout：selector 錯（三行情境）/ 其他錯（原 log 行）。詳細資料收在 <details>，右側顯示失敗截圖。"""
    if f["passed"]:
        return ""
    report = f.get("error_report")
    log_path = f.get("log_path", "N/A")

    if not report:
        return (
            '<div class="mt-3"><div class="alert alert-warning" role="alert">'
            f'<strong>⚠️ {T["no_err"]}</strong><br>'
            f'<small class="text-muted">{T["log"]}：{_html_escape(log_path)}</small>'
            '</div></div>'
        )

    tag_html = _render_case_tag(report.get("tag", {}))
    left = [f'<div class="mb-2">{tag_html}</div>']

    if report["kind"] == "selector":
        ctx = report.get("context") or {}
        flow = ctx.get("flow") or "?"
        phase = ctx.get("phase") or "-"
        action = ctx.get("action") or "?"
        left.append(f'<div><strong>🔴 {T["ctx"]}</strong></div>')
        left.append(
            f'<ul class="mb-2 mt-1">'
            f'<li><strong>{T["flow"]}：</strong>{_html_escape(flow)}</li>'
            f'<li><strong>{T["phase"]}：</strong>{_html_escape(phase)}</li>'
            f'<li><strong>{T["action"]}：</strong>{_html_escape(action)}</li>'
            f'</ul>'
        )
        detail_rows = [("Selector Key", f'<code>{_html_escape(report.get("selector_path", ""))}</code>')]
        val = report.get("selector_value")
        if val:
            detail_rows.append(("Selector Value", f'<code>{_html_escape(val)}</code>'))
        detail_rows.append((T["raw"], f'<code>{_html_escape(report.get("error_line", ""))}</code>'))
        detail_rows.append((T["log"], _html_escape(log_path)))
    else:
        left.append(
            f'<div><strong>💥 {T["err"]}：</strong>'
            f'<code>{_html_escape(report.get("error_line", ""))}</code></div>'
        )
        detail_rows = [(T["log"], _html_escape(log_path))]

    left.append('<details class="mt-2"><summary class="text-muted" style="cursor:pointer;">' + T["detail"] + '</summary>')
    left.append('<ul class="mt-2 mb-0">')
    for k, v in detail_rows:
        left.append(f'<li><strong>{k}：</strong>{v}</li>')
    left.append('</ul></details>')

    # 右側失敗截圖（base64 內嵌）
    shot = _pick_failure_screenshot(f.get("error_screenshots") or [])
    right_html = ""
    if shot:
        uri = _embed_png_data_uri(shot["abs_path"])
        if uri:
            right_html = (
                f'<div class="text-center">'
                f'<img src="{uri}" alt="failure screenshot" '
                f'style="max-width:100%; max-height:420px; border:1px solid #ddd; border-radius:4px;">'
                f'<div class="mt-1"><small class="text-muted">{_html_escape(shot["name"])}</small></div>'
                f'</div>'
            )

    return (
        '<div class="mt-3"><div class="alert alert-danger" role="alert">'
        '<div class="row g-3">'
        f'<div class="col-md-8">{"".join(left)}</div>'
        f'<div class="col-md-4">{right_html}</div>'
        '</div></div></div>'
    )


# ---------------------------------------------------------------------------
# 外部資源：預設從 CDN 載 Bootstrap。內網 / 資料駐留 / 證據長期保存時設 REPORT_INLINE_ASSETS=1，
# 並把 bootstrap.min.css、bootstrap.min.js 放在 config/vendor/（一次性下載後進版控）→ 內嵌進 HTML，完全離線可開。
# 設了 REPORT_INLINE_ASSETS=1 但找不到檔案 → 不載任何外部資源（排版較陽春，但不會連外）。
# ---------------------------------------------------------------------------
_CDN_CSS = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
_CDN_JS = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.min.js"
_OFFLINE_FALLBACK_JS = """document.addEventListener('click',function(e){var b=e.target.closest('[data-bs-toggle=collapse]');
if(!b)return;var t=document.querySelector(b.getAttribute('data-bs-target'));if(t)t.classList.toggle('show');});"""


def _inline_assets() -> bool:
    return os.environ.get("REPORT_INLINE_ASSETS", "") == "1"


def _asset_css() -> str:
    if not _inline_assets():
        return f'<link href="{_CDN_CSS}" rel="stylesheet">'
    p = ROOT / "config" / "vendor" / "bootstrap.min.css"
    css = p.read_text(encoding="utf-8") if p.exists() else ".collapse:not(.show){display:none}"
    return f"<style>{css}</style>"


def _asset_js() -> str:
    if not _inline_assets():
        return f'<script src="{_CDN_JS}"></script>'
    p = ROOT / "config" / "vendor" / "bootstrap.min.js"
    js = p.read_text(encoding="utf-8") if p.exists() else _OFFLINE_FALLBACK_JS
    return f"<script>{js}</script>"


def render_html(run_label: str, functional: list, ui_diff: Optional[dict]) -> str:
    n_total = len(functional)
    n_blocked = sum(1 for f in functional if f.get("blocked"))
    n_fail = sum(1 for f in functional if not f["passed"]) - n_blocked
    n_pass = n_total - n_fail - n_blocked

    flow_cards = []
    for idx, f in enumerate(functional):
        status_word = ("FLAKY" if f.get("flaky") else "SUCCESS") if f["passed"] else ("BLOCKED" if f.get("blocked") else "FAILED")
        btn_class = ("btn-warning" if f.get("flaky") else "btn-success") if f["passed"] else ("btn-secondary" if f.get("blocked") else "btn-danger")
        duration_str = f"{f['duration']:.1f}s" if f.get("duration") is not None else T["unknown"]
        tags_html = "".join(
            f'<span class="badge bg-primary">{_html_escape(t)}</span> ' for t in f.get("tags", [])
        )
        anchor = f"{idx}_" + re.sub(r"[^a-zA-Z0-9_-]", "_", f["name"])

        # 生成錯誤詳情
        error_details = _render_error_details(f)

        flow_cards.append(f"""
  <div class="card mb-3">
    <div class="card-header d-flex justify-content-between align-items-center">
      <button class="btn {btn_class} btn-sm" type="button" data-bs-toggle="collapse" data-bs-target="#flow-{anchor}">
        {_html_escape(f['name'])} : {status_word}
      </button>
    </div>
    <div class="collapse" id="flow-{anchor}">
      <div class="card-body">
        <p class="card-text">Status: {status_word} | Duration: {duration_str}{' | Tags: ' + tags_html if tags_html else ''}</p>
        <p class="note">yaml: {_html_escape(f.get('path')) or T['no_path']}</p>
        {error_details}
      </div>
    </div>
  </div>""")

    ui_diff_section = _render_ui_diff_section(ui_diff)

    func_pie_js = f"""
  renderPie(
    document.getElementById('funcPie'), document.getElementById('funcLegend'),
    ['Passed', 'Failed', 'Blocked'], [{n_pass}, {n_fail}, {n_blocked}], ['#2e7d32', '#c62828', '#757575']
  );"""

    return f"""<!DOCTYPE html>
<html lang="{REPORT_LANG}">
<head>
<meta charset="UTF-8">
<title>{T["title"]} - {_html_escape(run_label)}</title>
{_asset_css()}
<style>
  .pie {{ width:200px; height:200px; border-radius:50%; margin:0 auto; }}
  .legend {{ list-style:none; padding:0; margin-top:16px; font-size:14px; }}
  .legend li {{ display:flex; align-items:center; gap:8px; margin-bottom:4px; }}
  .legend .swatch {{ width:14px; height:14px; border-radius:3px; display:inline-block; flex-shrink:0; }}
  body {{ background:#f5f6f8; padding-bottom: 60px; }}
  .badge-pass {{ background:#2e7d32; color:#fff; }}
  .badge-fail {{ background:#c62828; color:#fff; }}
  .badge-missing {{ background:#6a1b9a; color:#fff; }}
  .badge-error {{ background:#e65100; color:#fff; }}
  .badge-layout {{ background:#f9a825; color:#000; }}
  .badge-nobaseline {{ background:#546e7a; color:#fff; }}
  .note {{ font-size:12px; color:#888; }}
  .diff-row {{ display:flex; gap:10px; align-items:flex-start; flex-wrap:wrap; }}
  .diff-col {{ text-align:center; width:220px; }}
  .diff-col img {{ width:220px; height:auto; max-height:460px; border:1px solid #ccc; border-radius:6px; object-fit:contain; display:block; background:#eee; cursor:zoom-in; }}
  .diff-col .missing {{ width:220px; height:390px; border:1px solid #ccc; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size:12px; color:#999; text-align:center; padding:6px; background:#eee; }}
  .diff-col .label {{ font-size:12px; color:#555; margin-top:4px; }}
  .diff-col .zoom-hint {{ font-size:11px; color:#aaa; }}
  .diff-rate {{ font-weight:bold; }}
  /* 全螢幕看圖用的 lightbox,點縮圖放大、點背景或按 Esc 關閉,圖片保持原始解析度不裁切 */
  .lightbox {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:2000; align-items:center; justify-content:center; cursor:zoom-out; }}
  .lightbox.open {{ display:flex; }}
  .lightbox img {{ max-width:95vw; max-height:95vh; object-fit:contain; border-radius:4px; }}
  /* 列印 / 轉 PDF（證據報告）：所有卡片展開、隱藏互動元件 */
  @media print {{ .collapse {{ display:block !important; }} .lightbox, .zoom-hint {{ display:none !important; }}
                  .card {{ break-inside: avoid; }} body {{ background:#fff; }} }}
</style>
</head>
<body>
<div class="container py-4">
  <h1 class="text-center mb-1">{T["h1"]}</h1>
  <p class="text-center note">run: {run_label}</p>

  <div class="row mt-4 mb-4">
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-body">
          <h5 class="card-title text-center">{T["func"]}</h5>
          <div id="funcPie" class="pie"></div>
          <ul id="funcLegend" class="legend"></ul>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-body">
          <h5 class="card-title text-center">{T["ui"]}</h5>
          {"<div id='uiPie' class='pie'></div><ul id='uiLegend' class='legend'></ul>" if ui_diff else "<p class='note text-center mt-5'>" + T["no_ui"] + "<br>" + T["no_ui_hint"] + "</p>"}
        </div>
      </div>
    </div>
  </div>

  <div class="card-group mb-4">
    <div class="card"><div class="card-body"><h6 class="card-title text-center">{T["total"]}</h6><h3 class="text-center">{n_total}</h3></div></div>
    <div class="card text-white bg-danger"><div class="card-body"><h6 class="card-title text-center">{T["failed"]}</h6><h3 class="text-center">{n_fail}</h3></div></div>
    <div class="card text-white bg-success"><div class="card-body"><h6 class="card-title text-center">{T["succeeded"]}</h6><h3 class="text-center">{n_pass}</h3></div></div>
  </div>

  <h4 class="mt-5">{T["flows"]}</h4>
  {"".join(flow_cards) if flow_cards else "<p class='note'>" + T["no_flow"] + "</p>"}

  {ui_diff_section}
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightboxImg" src="" alt="zoom">
</div>

{_asset_js()}
<script>
  function openLightbox(src) {{
    document.getElementById('lightboxImg').src = src;
    document.getElementById('lightbox').classList.add('open');
  }}
  function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('open');
  }}
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') closeLightbox();
  }});
  function renderPie(pieEl, legendEl, labels, data, colors) {{
    var total = data.reduce(function (a, b) {{ return a + b; }}, 0);
    var stops = [];
    var acc = 0;
    for (var i = 0; i < data.length; i++) {{
      var start = total ? (acc / total) * 360 : 0;
      acc += data[i];
      var end = total ? (acc / total) * 360 : 0;
      stops.push(colors[i] + ' ' + start + 'deg ' + end + 'deg');
    }}
    pieEl.style.background = total ? 'conic-gradient(' + stops.join(', ') + ')' : '#e0e0e0';
    legendEl.innerHTML = labels.map(function (label, i) {{
      var pct = total ? Math.round((data[i] / total) * 1000) / 10 : 0;
      return '<li><span class="swatch" style="background:' + colors[i] + '"></span>' +
             label + ' — ' + data[i] + ' (' + pct + '%)</li>';
    }}).join('');
  }}
  {func_pie_js}
  {_render_ui_diff_pie_js(ui_diff)}
</script>
</body>
</html>
"""


def _render_ui_diff_pie_js(ui_diff: Optional[dict]) -> str:
    if not ui_diff:
        return ""
    counts = {}
    for cp in ui_diff.get("checkpoints", []):
        counts[cp["status"]] = counts.get(cp["status"], 0) + 1
    labels = list(counts.keys())
    data = list(counts.values())
    colors_map = {
        "PASS": "#2e7d32", "FAIL": "#c62828", "MISSING_BASELINE": "#6a1b9a",
        "LAYOUT_MISMATCH": "#f9a825", "ERROR": "#e65100", "NO_BASELINE": "#546e7a",
        "UPDATED": "#546e7a",
    }
    colors = [colors_map.get(label, "#999") for label in labels]
    return f"""
  renderPie(
    document.getElementById('uiPie'), document.getElementById('uiLegend'),
    {json.dumps(labels, ensure_ascii=False)}, {json.dumps(data)}, {json.dumps(colors)}
  );"""


def _image_to_data_uri(relative_path: str) -> Optional[str]:
    """把 ROOT 相對路徑的圖片讀成 base64 data URI，讀不到就回傳 None(交給呼叫端顯示佔位框)。"""
    full_path = ROOT / relative_path
    if not full_path.exists():
        return None
    try:
        data = full_path.read_bytes()
    except OSError:
        return None
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _img_or_placeholder(path: Optional[str], label: str) -> str:
    """不管成功或失敗都要在報表上看到圖片：有圖就直接內嵌 base64，
    沒有(路徑本來就是 None，或圖片實際上讀不到)就畫一個佔位框並寫清楚原因，
    不要整段消失讓人以為是排版壞了。內嵌是為了讓 report.html 可以整份搬走、寄給別人，
    不會因為離開專案資料夾就變成死圖。

    圖片點擊後用 lightbox 開全尺寸原圖(見 openLightbox JS)，縮圖本身也改用 object-fit:contain
    不裁切，確保像素級的差異標記(單像素紅點)不會因為縮圖裁切/縮放而看不到。"""
    if path:
        data_uri = _embed_png_data_uri(str(ROOT / path)) if (ROOT / path).exists() else None
        if data_uri:
            return (
                f'<img src="{data_uri}" alt="{label}" onclick="openLightbox(this.src)">'
                f'<div class="zoom-hint">{T["zoom"]}</div>'
            )
        return f'<div class="missing">({T["img_missing"]}: {_html_escape(path)})</div>'
    return f'<div class="missing">({T["none"]} {label})</div>'


def _render_checkpoint_card(cp: dict) -> str:
    badge = STATUS_BADGE_CLASS.get(cp["status"], "badge-nobaseline")

    info_lines = []
    if "diff_rate" in cp:
        rate_pct = f"{cp['diff_rate'] * 100:.1f}%"
        info_lines.append(f"<div class='diff-rate'>{rate_pct}</div>")
        info_lines.append(f"<div class='label'>{T['threshold']}:{cp.get('threshold', 0) * 100:.1f}%</div>")
        if "color_tolerance" in cp:
            info_lines.append(f"<div class='label'>{T['tolerance']}:{cp['color_tolerance']}</div>")
    if "fail_on_diff" in cp:
        info_lines.append(f"<div class='label'>failOnDiff:{cp['fail_on_diff']}</div>")
    if "error" in cp:
        info_lines.append(f"<div class='label text-danger'>{cp['error']}</div>")
    if cp["status"] == "MISSING_BASELINE":
        info_lines.append(f"<div class='label'>{T['miss_base']}</div>")
    if cp["status"] == "LAYOUT_MISMATCH":
        info_lines.append(f"<div class='label'>{T['layout']}</div>")
    if cp["status"] in ("NO_BASELINE", "UPDATED"):
        info_lines.append(f"<div class='label'>{T['capture']}</div>")

    # 不管 PASS/FAIL/其他狀態，都把三張圖(有的話)一起畫出來，缺的用佔位框標明原因
    diff_row = f"""
        <div class="diff-row mt-3">
          <div class="diff-col">
            {_img_or_placeholder(cp.get('baseline_image'), T['baseline'])}
            <div class="label">Baseline</div>
          </div>
          <div class="diff-col">
            {_img_or_placeholder(cp.get('actual_image'), T['shot'])}
            <div class="label">Actual</div>
          </div>
          <div class="diff-col">
            {_img_or_placeholder(cp.get('diff_image'), T['diff'])}
            <div class="label">Diff</div>
          </div>
          <div class="diff-col" style="width:140px;">
            <div class="p-2">{"".join(info_lines)}</div>
          </div>
        </div>"""

    # 收合預設全收起——樣式跟層級
    # 對齊上面「Flow 清單」的卡片(card-header 包一個 btn-sm 小按鈕,不是整條卡片變成色塊),
    # 保持兩個區塊視覺一致。
    anchor = "ckpt-" + re.sub(r"[^a-zA-Z0-9_-]", "_", cp["name"])
    return f"""
    <div class="card mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <button class="btn {badge} btn-sm" type="button" data-bs-toggle="collapse" data-bs-target="#{anchor}">
          {_html_escape(cp['name'])} : {cp['status']}
        </button>
      </div>
      <div class="collapse" id="{anchor}">
        <div class="card-body">
          {diff_row}
        </div>
      </div>
    </div>"""


def _render_ui_diff_section(ui_diff: Optional[dict]) -> str:
    if not ui_diff:
        return ""
    mode = ui_diff.get("mode", "check")
    rows = [_render_checkpoint_card(cp) for cp in ui_diff.get("checkpoints", [])]
    note = T["ui_note"]
    return f"""
  <h4 class="mt-5">UI Diff Checkpoints ({T["ui_mode"]}: {mode})</h4>
  <p class="note">{note}</p>
  {"".join(rows) if rows else "<p class='note'>" + T["no_cp"] + "</p>"}
"""


def main():
    if len(sys.argv) > 1:
        run_dir = Path(sys.argv[1]).resolve()
    else:
        run_dir = latest_run_dir()
        if run_dir is None:
            sys.exit("❌ test-results/ 底下找不到任何 run 目錄,也沒有指定 run_dir 參數")

    if not run_dir.exists():
        sys.exit(f"❌ run_dir 不存在:{run_dir}")

    run_ts = resolve_run_ts(run_dir)
    flow_index = build_flow_index()
    functional = collect_json_results(run_dir) or collect_functional_results(run_dir, flow_index)
    ui_diff = load_ui_diff_summary(run_ts)

    html = render_html(run_ts, functional, ui_diff)
    # 報表一律寫在 test-results/<run_ts>/report_merged.html，跟 ui_diff/summary.json 同一個父目錄，
    # 不管功能測試的原始 log 實際放在 test-results/ 還是 ui_compare/.../_raw/(見 resolve_run_ts)。
    out_dir = RESULTS_DIR / run_ts
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report_merged.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"✅ 報表已產生:{out_path.relative_to(ROOT)}")
    print(f"   功能測試:{len(functional)} 個 flow,{sum(1 for f in functional if not f['passed'])} 個失敗")
    print(f"   UI Diff:{'有資料,' + str(len(ui_diff.get('checkpoints', []))) + ' 個 checkpoint' if ui_diff else '這次 run 沒有資料'}")
    print(str(out_path))


if __name__ == "__main__":
    main()
