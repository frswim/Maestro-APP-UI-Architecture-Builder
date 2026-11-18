#!/usr/bin/env python3
"""
Ignore 區塊框選工具(Python + matplotlib 版)。

用滑鼠在指定 checkpoint 的基線截圖上框選要忽略的矩形區域,自動換算成相對百分比座標,
寫進這個 checkpoint 專屬的設定檔:
    config/ui_baseline/<baseline_key>/<checkpoint_name>/settings.yaml

**設計**:color_tolerance 完全獨立,不共用任何樣板規則,即使多個渠道畫面很像也要各自框選、
各自維護一份。原因:功能推上線前每個 checkpoint 都要能個別 debug 過,共用樣板會讓
「這個渠道到底有沒有真的被檢查過」變得不透明。

前提:該 checkpoint 必須已經有基線(config/ui_baseline/<baseline_key>/<checkpoint_name>/current.png),
     先用 --capture-baseline 跑一次建立基線(順便會自動產生一份預設 settings.yaml),
     才能用這支工具框選、調整。

用法:
    python3 scripts/ui_diff_define_ignore.py <baseline_key> <checkpoint_name>

操作(視窗打開後):
    - 滑鼠左鍵拖曳畫一個矩形,可以畫多個
    - 按 z 撤銷最後一個矩形
    - 按 Enter 儲存並寫回 settings.yaml(只更新 ignore,threshold/failOnDiff/color_tolerance
      維持原值不動;要調這幾個參數,直接編輯 settings.yaml 這個 YAML 檔案即可,不需要透過這支工具)
    - 直接關掉視窗、不按 Enter 就是放棄,不會寫入任何東西
"""
import argparse
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.widgets import RectangleSelector
except ImportError:
    sys.exit(
        "缺少 matplotlib,請先安裝:pip3 install -r requirements.txt --break-system-packages\n"
        "(如果公司網路擋 pip 安裝，可改寫成 HTML+Canvas 版的框選工具)"
    )

try:
    import yaml
except ImportError:
    sys.exit("缺少 pyyaml，請先安裝:pip3 install -r requirements.txt --break-system-packages")

# 跟 ui_diff_check.py 共用同一份全域自動忽略區域常數(狀態列),這支工具不需要讓使用者
# 框選這塊,但畫出來當作參考,避免使用者誤以為那塊沒被排除、又手動重複框一次。
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from ui_diff_check import GLOBAL_IGNORE_REGIONS
except ImportError:
    GLOBAL_IGNORE_REGIONS = [{"x": "0%", "y": "0%", "w": "100%", "h": "2.5%"}]

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SETTINGS = {
    "threshold": 0,
    "failOnDiff": True,
    "color_tolerance": 0,
    "ignore": [],
}


def checkpoint_dir_for(brand: str, checkpoint_name: str) -> Path:
    return ROOT / "config" / "ui_baseline" / brand / checkpoint_name


def load_settings(settings_path: Path) -> dict:
    if settings_path.exists():
        return yaml.safe_load(settings_path.read_text(encoding="utf-8")) or dict(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


def pct_to_pixel_box(region: dict, width: int, height: int) -> tuple:
    def _pct(v):
        if isinstance(v, str) and v.endswith("%"):
            return float(v[:-1]) / 100.0
        v = float(v)
        return v / 100.0 if v > 1 else v

    x0 = _pct(region.get("x", 0)) * width
    y0 = _pct(region.get("y", 0)) * height
    w = _pct(region.get("w", 0)) * width
    h = _pct(region.get("h", 0)) * height
    return x0, y0, x0 + w, y0 + h


def pixel_boxes_to_ignore_regions(rects_px: list, width: int, height: int) -> list:
    return [
        {
            "x": f"{x0 / width * 100:.1f}%",
            "y": f"{y0 / height * 100:.1f}%",
            "w": f"{(x1 - x0) / width * 100:.1f}%",
            "h": f"{(y1 - y0) / height * 100:.1f}%",
        }
        for (x0, y0, x1, y1) in rects_px
    ]


def save_ignore_regions(settings_path: Path, settings: dict, ignore_regions: list) -> None:
    """只更新 ignore，threshold/failOnDiff/color_tolerance 保留原值(用 setdefault 補上
    第一次還沒有的欄位，避免手動編輯過的 settings.yaml 被這支工具意外重置)。"""
    settings["ignore"] = ignore_regions
    settings.setdefault("threshold", DEFAULT_SETTINGS["threshold"])
    settings.setdefault("failOnDiff", DEFAULT_SETTINGS["failOnDiff"])
    settings.setdefault("color_tolerance", DEFAULT_SETTINGS["color_tolerance"])
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(yaml.safe_dump(settings, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brand", help="基線 key，例如 brand_a/android/ja")
    parser.add_argument("checkpoint_name", help="checkpoint 名稱(例如 payin_order_confirm_card)")
    args = parser.parse_args()

    brand, checkpoint_name = args.brand, args.checkpoint_name
    ckpt_dir = checkpoint_dir_for(brand, checkpoint_name)
    baseline_path = ckpt_dir / "current.png"
    settings_path = ckpt_dir / "settings.yaml"

    if not baseline_path.exists():
        sys.exit(
            f"❌ 找不到基線:{baseline_path.relative_to(ROOT)}\n"
            f"請先用 --capture-baseline 跑一次建立這個 checkpoint 的基線，再用這支工具框選。"
        )

    img = plt.imread(str(baseline_path))
    height, width = img.shape[0], img.shape[1]

    settings = load_settings(settings_path)
    existing_ignore_pct = settings.get("ignore", [])

    rects_px = []  # [(x0, y0, x1, y1), ...] in pixel coords
    patch_list = []

    fig, ax = plt.subplots(figsize=(8, 8 * height / width if width else 8))
    ax.imshow(img)
    ax.set_title(
        f"{brand} / {checkpoint_name}\n"
        f"拖曳畫框 = 新增忽略區塊 | z = 撤銷上一個 | Enter = 儲存並離開"
    )

    # 先把設定檔裡既有的 ignore 區塊畫出來(橘色=已存在，紅色=這次新畫的)，
    # 方便你知道目前已經有哪些區塊，不用憑記憶重畫一次。
    for region in existing_ignore_pct:
        x0, y0, x1, y1 = pct_to_pixel_box(region, width, height)
        rects_px.append((x0, y0, x1, y1))
        p = patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=2, edgecolor="orange", facecolor="orange", alpha=0.2)
        ax.add_patch(p)
        patch_list.append(p)
    if existing_ignore_pct:
        print(f"已載入 {len(existing_ignore_pct)} 個既有的 ignore 區塊(橘色，可以按 z 撤銷或保留)")

    # 畫出全域自動忽略區域(灰色、斜線，僅供參考，不能撤銷、不會存進 settings.yaml)——
    # 這塊(手機狀態列)每次比對都會自動排除，不需要也不應該手動再框一次。
    for region in GLOBAL_IGNORE_REGIONS:
        x0, y0, x1, y1 = pct_to_pixel_box(region, width, height)
        p = patches.Rectangle(
            (x0, y0), x1 - x0, y1 - y0, linewidth=1, edgecolor="gray",
            facecolor="gray", alpha=0.35, hatch="//",
        )
        ax.add_patch(p)
    print(f"灰色斜線區域 = 系統狀態列，全域自動忽略(不需要手動框，這支工具不會讓你動它)")

    print(f"目前設定:threshold={settings.get('threshold')} color_tolerance={settings.get('color_tolerance')} "
          f"failOnDiff={settings.get('failOnDiff')}(這幾個參數這支工具不會動，要改請直接編輯 "
          f"{settings_path.relative_to(ROOT)})")

    def onselect(eclick, erelease):
        x0, y0 = eclick.xdata, eclick.ydata
        x1, y1 = erelease.xdata, erelease.ydata
        if x0 is None or y0 is None or x1 is None or y1 is None:
            return
        x0, x1 = sorted([x0, x1])
        y0, y1 = sorted([y0, y1])
        rects_px.append((x0, y0, x1, y1))
        p = patches.Rectangle((x0, y0), x1 - x0, y1 - y0, linewidth=2, edgecolor="red", facecolor="red", alpha=0.25)
        ax.add_patch(p)
        patch_list.append(p)
        fig.canvas.draw_idle()
        print(f"  新增區塊 #{len(rects_px)}: pixel=({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")

    selector = RectangleSelector(
        ax, onselect, useblit=True,
        button=[1], minspanx=5, minspany=5, spancoords="pixels", interactive=True,
    )

    state = {"saved": False}

    def on_key(event):
        if event.key == "z" and rects_px:
            rects_px.pop()
            patch_list.pop().remove()
            fig.canvas.draw_idle()
            print(f"  撤銷,目前剩 {len(rects_px)} 個區塊")
        elif event.key == "enter":
            state["saved"] = True
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    print("視窗已打開:拖曳畫框、z 撤銷、Enter 儲存離開(直接關視窗 = 放棄不寫入)")
    plt.show()

    if not state["saved"]:
        print("沒有按 Enter,放棄,設定檔沒有被修改。")
        return

    ignore_regions = pixel_boxes_to_ignore_regions(rects_px, width, height)
    save_ignore_regions(settings_path, settings, ignore_regions)
    print(f"✅ 已寫入 {settings_path.relative_to(ROOT)}")
    print(f"   checkpoint={checkpoint_name}，{len(ignore_regions)} 個 ignore 區塊")


if __name__ == "__main__":
    main()
