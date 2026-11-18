#!/usr/bin/env python3
"""
UI Diff 比對腳本(見 skill: references/architecture-modules.md M10/M9)

用法:
    # 檢查模式(預設):跟現有基線比對,產出 PASS/FAIL/LAYOUT_MISMATCH/MISSING_BASELINE/ERROR
    python3 scripts/ui_diff_check.py ui_compare/<baseline_key>/<run_timestamp> <baseline_key>

    # 截取 baseline 模式:把這次截圖寫入/覆蓋成基線,不比對,不判斷 PASS/FAIL
    python3 scripts/ui_diff_check.py ui_compare/<baseline_key>/<run_timestamp> <baseline_key> --capture-baseline

輸入:
    <run_dir>/_raw/chk_*.png   Maestro 用 --test-output-dir 直接寫入的原始扁平截圖

輸出:
    <run_dir>/<checkpoint_name>/actual.png                     整理歸檔後的截圖
    config/ui_baseline/<baseline_key>/<checkpoint_name>/current.png   基線圖(僅截取模式會寫入/更新)
    config/ui_baseline/<baseline_key>/<checkpoint_name>/settings.yaml 這個 checkpoint 專屬的設定
                                                                 (threshold/failOnDiff/color_tolerance/ignore,
                                                                 每張基線圖各自一份,不共用樣板,
    test-results/<run_timestamp>/ui_diff/summary.json           本次所有 checkpoint 的結果(給報表腳本讀)
    test-results/<run_timestamp>/ui_diff/diff_<checkpoint_name>.png  差異疊圖(僅檢查模式的 FAIL/PASS 才有)

注意:這支腳本本身不呼叫 Maestro、不操作裝置,純粹讀寫本機圖片檔案。
Maestro 只負責「截圖」,這支腳本負責「洗照片、跟舊照片比對、算出結論」——。
"""
import argparse
import json
import shutil
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows（cp949/cp950/cp932）主控台與管線不亂碼
except Exception:
    pass
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit(
        "缺少 Pillow,請先安裝:pip3 install -r requirements.txt --break-system-packages\n"
        "(如果公司網路擋 pip,改用已安裝好 Pillow 的環境執行這支腳本)"
    )

try:
    import yaml
except ImportError:
    sys.exit(
        "缺少 pyyaml,請先安裝:pip3 install -r requirements.txt --break-system-packages"
    )

ROOT = Path(__file__).resolve().parent.parent
CHK_PREFIX = "chk_"

# 單像素色彩距離的預設容忍值:ignore 區塊以外，預期是 0 容忍(逐像素完全一致才算 PASS)。
# 可以在每個 checkpoint 自己的 settings.yaml 底下用 color_tolerance 覆寫(例如遇到
# anti-aliasing 鋸齒噪訊常態性誤判 FAIL，才把個別 checkpoint 的容忍值調高)，。
# 0~441 是色彩距離的合法範圍(sqrt(255^2 * 3) 是三個通道全部拉滿的最大距離)。
DEFAULT_COLOR_TOLERANCE = 0

# 每個 checkpoint 第一次建立基線時，自動生成的預設設定內容。threshold 預設 0，呼應
# 「ignore 區塊以外 0 容忍」的整體設計哲學——一旦用框選工具把該遮的動態區塊都遮好，
# 剩下有任何差異就該被抓出來，不該有一個放寬的百分比空間。
DEFAULT_SETTINGS = {
    "threshold": 0,
    "failOnDiff": True,
    "color_tolerance": DEFAULT_COLOR_TOLERANCE,
    "ignore": [],
}

# 全域自動忽略區域,例外於「每個 checkpoint 各自一份設定、不共用」的原則):
# 手機系統狀態列(時間/wifi/飛行模式/電量圖示)每次截圖都在畫面最上方同一個位置,但內容(時間等)
# 每次跑必變。這不是 App 畫面內容,是裝置系統畫的 chrome,跟「這個 checkpoint 有沒有被個別
# debug 過」無關,所以不需要每個 checkpoint 各自框選——直接在程式碼層自動套用,對所有品牌、
# 所有 checkpoint 一體適用,使用者不用重複操作。
# 實測依據(某 1080x2400 裝置):狀態列差異像素集中在 y=17~44,這裡抓寬一點
# 蓋到 y:0~2.5% 高度,涵蓋不同裝置解析度下狀態列位置的些微誤差。
# 這一段跟每個 checkpoint 自己 settings.yaml 裡的 ignore 是「相加」關係,不會互相覆蓋。
GLOBAL_IGNORE_REGIONS = [
    {"x": "0%", "y": "0%", "w": "100%", "h": "2.5%"},
]


# ---------------------------------------------------------------------------
# 第一層:截圖檔名 -> checkpoint 名稱
# ---------------------------------------------------------------------------
def resolve_checkpoint_name(filename: str) -> str:
    """把 chk_<name>.png 去掉前綴跟副檔名,剩下的就是 checkpoint 名稱。"""
    stem = Path(filename).stem  # 去副檔名
    if stem.startswith(CHK_PREFIX):
        stem = stem[len(CHK_PREFIX):]
    return stem


# ---------------------------------------------------------------------------
# 第二層:checkpoint 名稱 -> 這個 checkpoint 自己的 settings.yaml
# (每個 checkpoint 的設定跟它的基線圖放在同一個
# 資料夾底下，一對一，不共用，
# ---------------------------------------------------------------------------
def checkpoint_dir_for(brand: str, checkpoint_name: str) -> Path:
    return ROOT / "config" / "ui_baseline" / brand / checkpoint_name


def baseline_path_for(brand: str, checkpoint_name: str) -> Path:
    return checkpoint_dir_for(brand, checkpoint_name) / "current.png"


def settings_path_for(brand: str, checkpoint_name: str) -> Path:
    return checkpoint_dir_for(brand, checkpoint_name) / "settings.yaml"


def load_settings(brand: str, checkpoint_name: str):
    """讀這個 checkpoint 專屬的 settings.yaml，不存在回傳 None(呼叫端決定要不要當錯誤)。"""
    path = settings_path_for(brand, checkpoint_name)
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def ensure_default_settings(brand: str, checkpoint_name: str) -> None:
    """第一次建立基線時，如果還沒有設定檔就生成一份預設值，讓你有東西可以編輯/框選。
    如果設定檔已經存在(例如重新截取 baseline 更新既有 checkpoint)，不會動它，
    避免把你已經調好的 ignore/threshold 洗掉。"""
    path = settings_path_for(brand, checkpoint_name)
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(DEFAULT_SETTINGS, allow_unicode=True, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Ignore 遮罩 + pixel diff
# ---------------------------------------------------------------------------
def _percent_to_float(value) -> float:
    """'20%' / 20 / 0.2 都能吃,統一轉成 0~1 的比例。"""
    if isinstance(value, str) and value.endswith("%"):
        return float(value[:-1]) / 100.0
    value = float(value)
    return value / 100.0 if value > 1 else value


def ignore_regions_to_pixel_boxes(ignore_regions: list, width: int, height: int):
    boxes = []
    for region in ignore_regions or []:
        x = _percent_to_float(region.get("x", 0)) * width
        y = _percent_to_float(region.get("y", 0)) * height
        w = _percent_to_float(region.get("w", 0)) * width
        h = _percent_to_float(region.get("h", 0)) * height
        boxes.append((int(x), int(y), int(x + w), int(y + h)))
    return boxes


def _point_in_any_box(x: int, y: int, boxes: list) -> bool:
    for (x0, y0, x1, y1) in boxes:
        if x0 <= x < x1 and y0 <= y < y1:
            return True
    return False


# 差異標記顏色:外框+箭頭用紅色(。已改成不逐像素上色
# (見下方 pixel_diff 的說明),只用外框+箭頭指出差異區塊,所以這裡只剩一個顏色常數。
CLUSTER_BOX_COLOR = (255, 0, 0, 255)
# 差異像素分群用的網格大小(px)。差異點數量可能到幾千甚至更多，逐點兩兩比對找連通
# 群集太慢；改成先把座標分進 GRID_SIZE x GRID_SIZE 的格子，格子之間 8-方向相鄰就視為
# 同一群，再取整群所有像素的外框——這樣即使一群差異只佔幾十個像素，也能在報表上看到
# 一個明顯的外框和箭頭指向它，而不是要放大很多倍才找到單顆像素。
_CLUSTER_GRID_SIZE = 20
_CLUSTER_MIN_PIXELS = 3  # 小於這個像素數的群集視為雜訊，不畫框(通常是四角零星 anti-aliasing)


def _cluster_diff_points(points: list, grid_size: int = _CLUSTER_GRID_SIZE) -> list:
    """把差異像素座標分群，回傳每一群的 (x0, y0, x1, y1, pixel_count)。

    用網格 + BFS 做連通分量分析，只在「有差異的格子」之間搜尋，不用掃過整張圖，
    所以即使差異點很多也不會太慢。
    """
    if not points:
        return []

    cell_points = {}
    for (x, y) in points:
        cell = (x // grid_size, y // grid_size)
        cell_points.setdefault(cell, []).append((x, y))

    visited = set()
    clusters = []
    for start_cell in cell_points:
        if start_cell in visited:
            continue
        stack = [start_cell]
        visited.add(start_cell)
        group_cells = [start_cell]
        while stack:
            cx, cy = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (cx + dx, cy + dy)
                    if neighbor in cell_points and neighbor not in visited:
                        visited.add(neighbor)
                        group_cells.append(neighbor)
                        stack.append(neighbor)

        xs, ys, count = [], [], 0
        for cell in group_cells:
            for (x, y) in cell_points[cell]:
                xs.append(x)
                ys.append(y)
                count += 1
        clusters.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1, count))

    return clusters


def _draw_cluster_markers(draw: "ImageDraw.ImageDraw", clusters: list, width: int, height: int) -> None:
    """幫每個差異群集畫一個外框 + 一個從外側指過來的箭頭，讓人不用逐像素找就能一眼看到
    「這裡有差異」。"""
    pad = 6
    for (x0, y0, x1, y1, count) in clusters:
        if count < _CLUSTER_MIN_PIXELS:
            continue
        bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
        bx1, by1 = min(width - 1, x1 + pad), min(height - 1, y1 + pad)
        draw.rectangle([bx0, by0, bx1, by1], outline=CLUSTER_BOX_COLOR, width=4)

        # 箭頭:從外框左上角再往外(左上方)拉一段線,箭頭指向外框角落。
        arrow_len = 50
        tip = (bx0, by0)
        tail = (max(0, bx0 - arrow_len), max(0, by0 - arrow_len))
        draw.line([tail, tip], fill=CLUSTER_BOX_COLOR, width=4)
        # 簡單箭頭頭部(小三角形)
        import math
        angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
        head_len = 14
        head_angle = math.radians(25)
        p1 = (
            tip[0] - head_len * math.cos(angle - head_angle),
            tip[1] - head_len * math.sin(angle - head_angle),
        )
        p2 = (
            tip[0] - head_len * math.cos(angle + head_angle),
            tip[1] - head_len * math.sin(angle + head_angle),
        )
        draw.polygon([tip, p1, p2], fill=CLUSTER_BOX_COLOR)


def pixel_diff(
    baseline_img: Image.Image,
    actual_img: Image.Image,
    ignore_regions: list,
    color_tolerance: float = DEFAULT_COLOR_TOLERANCE,
):
    """回傳 (diff_rate, diff_overlay_image)。假設兩張圖尺寸已確認相同。

    ignore 區塊以外的每一個像素，色彩距離只要超過 color_tolerance 就算「不一樣」；
    預設 color_tolerance=0，代表逐像素完全一致才算沒差異。

    疊圖除了逐像素標紅之外，還會把差異像素分群、畫紅色外框 + 箭頭，讓報表上一眼就能看到
    「差異在這裡」，不用自己放大逐像素找。
    """
    baseline_img = baseline_img.convert("RGB")
    actual_img = actual_img.convert("RGB")
    width, height = baseline_img.size
    boxes = ignore_regions_to_pixel_boxes(ignore_regions, width, height)

    base_px = baseline_img.load()
    act_px = actual_img.load()
    overlay = actual_img.copy()
    draw = ImageDraw.Draw(overlay, "RGBA")

    diff_count = 0
    compared_count = 0
    diff_points = []
    for y in range(height):
        for x in range(width):
            if _point_in_any_box(x, y, boxes):
                continue
            compared_count += 1
            br, bg, bb = base_px[x, y]
            ar, ag, ab = act_px[x, y]
            distance = ((br - ar) ** 2 + (bg - ag) ** 2 + (bb - ab) ** 2) ** 0.5
            if distance > color_tolerance:
                diff_count += 1
                diff_points.append((x, y))

    # 不逐像素上色。改成只用外框 + 箭頭指出差異區塊,Actual 的像素內容完全不動,
    # 保持可讀,只是多畫一個指標告訴你「這裡不一樣」。
    clusters = _cluster_diff_points(diff_points)
    _draw_cluster_markers(draw, clusters, width, height)

    diff_rate = (diff_count / compared_count) if compared_count else 0.0
    return diff_rate, overlay


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def organize_raw_screenshots(run_dir: Path) -> list:
    """把 _raw/ 底下所有 chk_*.png 解析、複製成 <checkpoint_name>/actual.png,回傳 checkpoint 名稱清單。

    用 rglob 遞迴掃描,不假設固定深度 —— 實測發現指定 --test-output-dir 時,
    Maestro 會在裡面再自己加一層時間戳子資料夾,實際截圖路徑深度不固定
    (例如 _raw/<maestro_timestamp>/<flow_name>/takeScreenshot/chk_x.png),
    
    """
    raw_dir = run_dir / "_raw"
    checkpoint_names = []
    if not raw_dir.exists():
        return checkpoint_names
    for png in sorted(raw_dir.rglob(f"{CHK_PREFIX}*.png")):
        name = resolve_checkpoint_name(png.name)
        dest_dir = run_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(png, dest_dir / "actual.png")
        checkpoint_names.append(name)
    return checkpoint_names


def capture_baseline(brand: str, checkpoint_name: str, actual_path: Path) -> dict:
    """截取 baseline 模式:寫入/覆蓋基線,不比對。"""
    dest = baseline_path_for(brand, checkpoint_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dest.exists():
            history_dir = dest.parent / "history"
            history_dir.mkdir(exist_ok=True)
            existing = list(history_dir.glob("v*_*.png"))
            next_version = len(existing) + 1
            date_str = _today_str()
            shutil.move(str(dest), history_dir / f"v{next_version}_{date_str}.png")
            status = "UPDATED"
        else:
            status = "NO_BASELINE"
        shutil.copy2(actual_path, dest)
        ensure_default_settings(brand, checkpoint_name)
        return {"status": status}
    except OSError as exc:
        return {"status": "ERROR", "error": str(exc)}


def check_against_baseline(checkpoint_name: str, brand: str, actual_path: Path) -> dict:
    """檢查模式:跟現有基線比對。

    設定完全來自這個 checkpoint 自己的 settings.yaml，不再查任何中央設定檔或樣板規則。
    """
    baseline_path = baseline_path_for(brand, checkpoint_name)
    if not baseline_path.exists():
        return {"status": "MISSING_BASELINE", "fail_on_diff": True}

    settings = load_settings(brand, checkpoint_name)
    if settings is None:
        settings_path = settings_path_for(brand, checkpoint_name)
        return {
            "status": "ERROR",
            "fail_on_diff": True,
            "error": f"缺少設定檔:{settings_path.relative_to(ROOT)}(基線圖存在但設定檔不見了,"
                     f"可能被手動刪除,請重新用 --capture-baseline 補建或手動建立)",
        }

    fail_on_diff = settings.get("failOnDiff", True)

    try:
        baseline_img = Image.open(baseline_path)
        actual_img = Image.open(actual_path)
    except OSError as exc:
        return {"status": "ERROR", "fail_on_diff": fail_on_diff, "error": str(exc)}

    if baseline_img.size != actual_img.size:
        return {"status": "LAYOUT_MISMATCH", "fail_on_diff": fail_on_diff}

    threshold = settings.get("threshold", 0)
    # 每個 checkpoint 自己框的 ignore + 全域自動忽略的狀態列區域(見 GLOBAL_IGNORE_REGIONS),
    # 兩者相加,使用者不需要每個 checkpoint 都重複框一次狀態列。
    ignore_regions = list(settings.get("ignore", [])) + GLOBAL_IGNORE_REGIONS
    color_tolerance = settings.get("color_tolerance", DEFAULT_COLOR_TOLERANCE)
    diff_rate, overlay = pixel_diff(baseline_img, actual_img, ignore_regions, color_tolerance)
    status = "PASS" if diff_rate <= threshold else "FAIL"
    return {
        "status": status,
        "fail_on_diff": fail_on_diff,
        "diff_rate": round(diff_rate, 4),
        "threshold": threshold,
        "color_tolerance": color_tolerance,
        "_diff_overlay": overlay,  # 內部用,寫檔後從 result 拿掉,不進 summary.json
    }


def _today_str() -> str:
    from datetime import date
    return date.today().isoformat()


def run(run_dir: Path, brand: str, capture_baseline_mode: bool) -> dict:
    checkpoint_names = organize_raw_screenshots(run_dir)

    run_timestamp = run_dir.name
    report_dir = ROOT / "test-results" / run_timestamp / "ui_diff"
    report_dir.mkdir(parents=True, exist_ok=True)

    checkpoints_result = []
    for checkpoint_name in checkpoint_names:
        actual_path = run_dir / checkpoint_name / "actual.png"
        entry = {
            "name": checkpoint_name,
            "actual_image": str(actual_path.relative_to(ROOT)),
        }

        if capture_baseline_mode:
            result = capture_baseline(brand, checkpoint_name, actual_path)
            entry.update(result)
        else:
            result = check_against_baseline(checkpoint_name, brand, actual_path)
            overlay = result.pop("_diff_overlay", None)
            entry.update(result)
            entry["baseline_image"] = str(
                baseline_path_for(brand, checkpoint_name).relative_to(ROOT)
            ) if baseline_path_for(brand, checkpoint_name).exists() else None
            if overlay is not None:
                diff_image_path = report_dir / f"diff_{checkpoint_name}.png"
                overlay.save(diff_image_path)
                entry["diff_image"] = str(diff_image_path.relative_to(ROOT))

        checkpoints_result.append(entry)

    summary = {
        "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "brand": brand,
        "mode": "capture" if capture_baseline_mode else "check",
        "checkpoints": checkpoints_result,
    }

    summary_path = report_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _print_human_summary(summary: dict) -> None:
    mode = summary["mode"]
    checkpoints = summary["checkpoints"]
    print(f"=== UI Diff 結果({'截取 baseline 模式' if mode == 'capture' else '檢查模式'}) ===")
    if not checkpoints:
        print("  沒有找到任何 chk_*.png,確認 _raw/ 底下是否真的有截圖。")
        return
    for entry in checkpoints:
        line = f"  [{entry['status']:>15}] {entry['name']}"
        if "diff_rate" in entry:
            line += f"  diff_rate={entry['diff_rate']} threshold={entry['threshold']}"
        if "error" in entry:
            line += f"  ({entry['error']})"
        print(line)
    n_fail = sum(1 for e in checkpoints if e["status"] in ("FAIL", "ERROR", "MISSING_BASELINE", "LAYOUT_MISMATCH"))
    print(f"共 {len(checkpoints)} 個 checkpoint,{n_fail} 個異常。詳細結果見 summary.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="ui_compare/<baseline_key>/<run_timestamp> 這個資料夾路徑")
    parser.add_argument("brand", metavar="baseline_key", help="基線 key = 讓畫面不同的維度組合,例如 brand_a/android/ja/pixel7(run_suite.sh 會自動組)")
    parser.add_argument("--capture-baseline", action="store_true", help="截取 baseline 模式,不比對")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        sys.exit(f"❌ run_dir 不存在:{run_dir}")

    summary = run(run_dir, args.brand, args.capture_baseline)
    _print_human_summary(summary)

    # 最終判定(僅檢查模式才有意義,,
    # 有任一 fail_on_diff=true 的 checkpoint 命中 FAIL/ERROR/MISSING_BASELINE 就讓這支腳本 exit 1,
    # 方便 run_suite.sh 串接判斷整體結果。
    if summary["mode"] == "check":
        hard_fail = any(
            e.get("fail_on_diff") and e["status"] in ("FAIL", "ERROR", "MISSING_BASELINE", "LAYOUT_MISMATCH")
            for e in summary["checkpoints"]
        )
        if hard_fail:
            sys.exit(1)


if __name__ == "__main__":
    main()
