"""颜色/像素检测收口 — 框架通用，HSV/RGB 阈值游戏特定。

RingColorDetector/BlueButtonDetector + 颜色阈值常量 + 文本/槽位检测函数。
阈值数值来自旧项目实机标定, 新项目实跑后须按 docs/现有项目历史坑台账.md 在 T18 重校准。
重构自 d:/chengfeng/vision.py；详见 docs/新项目技术设计.md §6.1。
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass

import numpy as np
from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import Rect

logger = get_logger("vision")

_CV2_IMPORT_FAILED = False


@dataclass(frozen=True)
class ColorSignal:
    name: str
    confidence: float
    coverage: float


def estimate_endurance_ratio(image: Image.Image, rect: Rect) -> float:
    """耐力条（训练资源 endurance，非体力 HP）填充比例 0.0-1.0，CV 估自顶部 HUD 绿色条。

    耐力条是绿色渐变进度条（蓝绿→黄绿）配灰底：用饱和度（g 明显大于 r 或 b）区分填充绿
    与暗绿底色，从左连续前缀（容忍 ≤2 列间隙）算填充右边界 / 容器宽度。详见 设计方案 §22.1。
    返回 0.0 = 未读到（非该画面/region 缺/条空）。
    """
    crop = crop_region(image, rect)
    arr = np.asarray(crop.convert("RGB"), dtype=np.int16)
    if arr.size == 0:
        return 0.0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green = (g > 60) & ((g - r > 30) | (g - b > 30))
    col_has_green = green.any(axis=0)
    width = arr.shape[1]
    if width == 0 or not col_has_green.any():
        return 0.0
    fill_end = 0
    gap = 0
    for x in range(width):
        if col_has_green[x]:
            fill_end = x + 1
            gap = 0
        else:
            gap += 1
            if gap > 2:
                break
    return min(fill_end / width, 1.0)


class RingColorDetector:
    """Detect coarse training ring colors in a cropped region."""

    def detect(self, image: Image.Image) -> ColorSignal:
        global _CV2_IMPORT_FAILED
        if _CV2_IMPORT_FAILED:
            return _detect_with_pil(image)
        try:
            return _detect_with_cv2(image)
        except ImportError:
            _CV2_IMPORT_FAILED = True
            return _detect_with_pil(image)


class BlueButtonDetector:
    """Detect whether an action button is the enabled blue style."""

    def detect(self, image: Image.Image) -> ColorSignal:
        rgb = image.convert("RGB")
        pixel_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
        pixels = list(pixel_data)
        total = max(len(pixels), 1)
        # Lower saturation threshold — game uses muted blue-gray buttons (s≈0.22).
        coverage = _pil_coverage(pixels, 180, 250, 0.18, 0.30, total)
        if coverage < 0.03:
            return ColorSignal("inactive", 1.0 - coverage, coverage)
        return ColorSignal("active_blue", min(coverage * 6, 1.0), coverage)


def _detect_with_cv2(image: Image.Image) -> ColorSignal:
    import cv2
    import numpy as np

    rgb = np.array(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    total = max(int(hsv.shape[0] * hsv.shape[1]), 1)

    signals = {
        "rainbow": _coverage(hsv, (135, 45, 80), (175, 255, 255), total),
        "gold": _coverage(hsv, (18, 80, 90), (42, 255, 255), total),
        "blue": _coverage(hsv, (90, 60, 80), (125, 255, 255), total),
    }
    return _best_signal(signals)


def _detect_with_pil(image: Image.Image) -> ColorSignal:
    rgb = image.convert("RGB")
    pixel_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
    pixels = list(pixel_data)
    total = max(len(pixels), 1)
    signals = {
        "rainbow": _pil_coverage(pixels, 270, 350, 0.18, 0.31, total),
        "gold": _pil_coverage(pixels, 36, 84, 0.31, 0.35, total),
        "blue": _pil_coverage(pixels, 180, 250, 0.24, 0.31, total),
    }
    return _best_signal(signals)


def _best_signal(signals: dict[str, float]) -> ColorSignal:
    name, coverage = max(signals.items(), key=lambda item: item[1])
    if coverage < 0.01:
        return ColorSignal("none", 1.0 - coverage, coverage)
    return ColorSignal(name, min(coverage * 10, 1.0), coverage)


def _coverage(hsv, lower: tuple[int, int, int], upper: tuple[int, int, int], total: int) -> float:
    import cv2
    import numpy as np

    mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
    return float(cv2.countNonZero(mask)) / total


def _pil_coverage(
    pixels: list[tuple[int, int, int]],
    hue_min: int,
    hue_max: int,
    saturation_min: float,
    value_min: float,
    total: int,
) -> float:
    count = 0
    for red, green, blue in pixels:
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        hue_degrees = hue * 360
        if hue_min <= hue_degrees <= hue_max and saturation >= saturation_min and value >= value_min:
            count += 1
    return count / total


# ===========================================================================
# Pixel / color detection (consolidated here from screen_reader.py).
# Thresholds below are extracted verbatim from the original functions — the
# numbers and comparison conditions are UNCHANGED, only named and documented.
# ===========================================================================

# 祝福槽是否已装备：裁剪区灰度图的均值 / 标准差下限（已装备的槽更亮、对比更高）。
BLESSING_SLOT_FILLED_MEAN_MIN = 85
BLESSING_SLOT_FILLED_STDDEV_MIN = 45

# 卡片高亮亮边：判定一个像素属于"亮白描边"的 RGB 分量下限（选中卡片有亮描边）。
BRIGHT_BORDER_R_MIN = 220
BRIGHT_BORDER_G_MIN = 210
BRIGHT_BORDER_B_MIN = 190

# 详情面板子祝福槽是否填充：可见像素(r+g+b 之和)下限，以及可见像素占比下限。
DETAIL_SUB_VISIBLE_SUM_MIN = 220
DETAIL_SUB_FILLED_RATIO_MIN = 0.20

# 红字检测（委托"受理讨伐委托"红字横幅等）：红色像素条件 r>R_MIN 且 g,b<GB_MAX，及占比下限。
RED_TEXT_R_MIN = 180
RED_TEXT_GB_MAX = 100
RED_TEXT_RATIO_MIN = 0.05

# 黄字检测（训练主界面商店"到货"黄字提醒）：黄色像素条件 r>R_MIN 且 g>G_MIN 且 b<B_MAX，及占比下限。
YELLOW_TEXT_R_MIN = 180
YELLOW_TEXT_G_MIN = 130
YELLOW_TEXT_B_MAX = 100
YELLOW_TEXT_RATIO_MIN = 0.03


def is_blue_region(rect: Rect, image: Image.Image | None) -> bool:
    if image is None:
        return False
    signal = BlueButtonDetector().detect(crop_region(image, rect))
    return signal.name == "active_blue"


def is_blessing_slot_filled(rect: Rect, image: Image.Image | None) -> bool:
    if image is None:
        return False
    try:
        gray = crop_region(image, rect).convert("L")
        pixel_data = gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata()
        pixels = list(pixel_data)
        if not pixels:
            return False
        mean = sum(pixels) / len(pixels)
        variance = sum((pixel - mean) ** 2 for pixel in pixels) / len(pixels)
        stddev = variance**0.5
        return mean >= BLESSING_SLOT_FILLED_MEAN_MIN and stddev >= BLESSING_SLOT_FILLED_STDDEV_MIN
    except Exception as e:
        logger.debug(f"[is_blessing_slot_filled] pixel analysis failed: {e}")
        return False


def card_highlight_score(rect: Rect, image: Image.Image) -> float:
    try:
        rgb = image.convert("RGB")
        iw, ih = rgb.size

        def _safe_crop(left: int, upper: int, right: int, lower: int) -> Image.Image:
            left = max(0, min(left, iw))
            upper = max(0, min(upper, ih))
            right = max(left + 1, min(right, iw))
            lower = max(upper + 1, min(lower, ih))
            return rgb.crop((left, upper, right, lower))

        outside_top = _safe_crop(rect.x - 10, rect.y - 10, rect.x + rect.width + 10, rect.y + 2)
        outside_left = _safe_crop(rect.x - 12, rect.y - 10, rect.x, rect.y + rect.height + 10)
        inside_left = _safe_crop(rect.x, rect.y + 20, rect.x + 15, rect.y + min(180, rect.height))
        return max(bright_border_ratio(outside_top), bright_border_ratio(outside_left), bright_border_ratio(inside_left))
    except Exception as e:
        logger.debug(f"[card_highlight_score] highlight analysis failed: {e}")
        return 0.0


def bright_border_ratio(image: Image.Image) -> float:
    pixel_data = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    pixels = list(pixel_data)
    if not pixels:
        return 0.0
    bright_border = sum(
        1 for r, g, b in pixels if r > BRIGHT_BORDER_R_MIN and g > BRIGHT_BORDER_G_MIN and b > BRIGHT_BORDER_B_MIN
    )
    return bright_border / len(pixels)


def detail_sub_blessing_slot_filled(rect: Rect, image: Image.Image) -> bool:
    try:
        rgb = crop_region(image, rect).convert("RGB")
        pixel_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
        pixels = list(pixel_data)
        if not pixels:
            return False
        visible_pixels = sum(1 for r, g, b in pixels if r + g + b > DETAIL_SUB_VISIBLE_SUM_MIN)
        return visible_pixels / len(pixels) >= DETAIL_SUB_FILLED_RATIO_MIN
    except Exception as e:
        logger.debug(f"[detail_sub_blessing_slot_filled] pixel analysis failed: {e}")
        return False


def detect_red_text(image: Image.Image) -> bool:
    """Crude red-text detection: check if enough red-ish pixels exist."""
    try:
        rgb = image.convert("RGB")
        pixel_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
        pixels = list(pixel_data)
        total = max(len(pixels), 1)
        red_count = 0
        for r, g, b in pixels:
            if r > RED_TEXT_R_MIN and g < RED_TEXT_GB_MAX and b < RED_TEXT_GB_MAX:
                red_count += 1
        return red_count / total > RED_TEXT_RATIO_MIN
    except Exception as e:
        logger.debug(f"[detect_red_text] red detection failed: {e}")
        return False


def detect_yellow_text(image: Image.Image) -> bool:
    """Crude yellow-text detection for training-hub shop alerts."""
    try:
        rgb = image.convert("RGB")
        pixel_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
        pixels = list(pixel_data)
        total = max(len(pixels), 1)
        yellow_count = 0
        for r, g, b in pixels:
            if r > YELLOW_TEXT_R_MIN and g > YELLOW_TEXT_G_MIN and b < YELLOW_TEXT_B_MAX:
                yellow_count += 1
        return yellow_count / total > YELLOW_TEXT_RATIO_MIN
    except Exception as e:
        logger.debug(f"[detect_yellow_text] yellow detection failed: {e}")
        return False


def _is_head_template(path) -> bool:
    """判断文件名是否为新库头像模板命名（纯数字 .png，如 1.png、10.png）。

    新库使用纯数字命名（不含进度条），旧库 counting_head_*.png /
    non_counting_head_*.png 保留为遗留不再使用。
    """
    from pathlib import Path as _Path
    if not isinstance(path, _Path):
        path = _Path(path)
    return path.suffix == ".png" and path.stem.isdigit()


_HEAD_MATCH_THRESHOLD = 0.85


def count_heads(image: Image.Image, search_region: Rect | None = None) -> int:
    """数训练选择画面里"作数"支援卡人头(早期游戏选人头最多的训练)。

    每个支援卡头像是**固定角色**(每回合只是分配到不同训练)，存为 config/assets/
    新库模板 N.png（纯数字命名，如 1.png、2.png，不含羁绊进度条）。对每个模板
    matchTemplate，得分 > _HEAD_MATCH_THRESHOLD 即该头在场，数命中数。旧库
    counting_head_*.png / non_counting_head_*.png 保留为遗留不再使用。

    search_region 默认 None = **全图搜**（人头位置每回合变、且可能延伸到卡片区，
    限定小区域会把头切边导致漏匹配，故默认全图；模板足够独特不会误匹配卡片 UI）。
    比旧 std/edge 法准：精确数同卡多头(2+)、不误判不作数头。实机验证 guts=2 /
    wisdom=1 / speed(不作数)=0 全对。新支援卡头像可用 collect_head_templates 工具裁剪入库（新库命名 N.png）。
    """
    try:
        import cv2
        import numpy as np
        from pathlib import Path

        assets = Path(__file__).resolve().parent.parent / "config" / "assets"
        src = image if search_region is None else crop_region(image, search_region)
        search = cv2.cvtColor(np.array(src.convert("RGB")), cv2.COLOR_RGB2BGR)
        count = 0
        for tpl_path in sorted(assets.glob("*.png")):
            if not _is_head_template(tpl_path):
                continue
            tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl is None or tpl.shape[0] > search.shape[0] or tpl.shape[1] > search.shape[1]:
                continue
            res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
            if float(res.max()) > _HEAD_MATCH_THRESHOLD:
                count += 1
        return count
    except Exception as e:
        logger.debug(f"[count_heads] head count failed: {e}")
        return 0
