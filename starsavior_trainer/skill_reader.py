"""潜质行 OCR 识别 + 滑动（共享模块，collect_skills 和 skill_inspector 复用）。

§22.12/§22.13：以"未习得/已习得"状态标签为锚点定位潜质行（不依赖名字尾字，
能识别任意命名潜质如洞察星痕/锐利得势）。每行读 name + price + status + name_cy。

== 潜质学习窗口行结构 ==
每行(行高 ~170px): 状态(未习得/已习得, x≈1034) + 折扣(35%SALE, x≈2006, y偏上) +
习得按钮(习得, x≈1882, y居中) + 价格(65/80, x≈2018-2091, y居中) + 潜质名(x≈1030, y偏下)。
"""
from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image
    from starsavior_trainer.ocr import RapidOcrEngine

from starsavior_trainer.text_utils import normalize_ocr_text, parse_first_int

# 滑动参数（scrollbar 中心，上滑看下方）
SCROLL_ANCHOR = (2176, 700)
SCROLL_PIXELS = 340


@dataclass(frozen=True)
class SkillLine:
    """识别到的一行潜质。button_rect 是"习得/升级"按钮 bbox(点击用, 直接来自 OCR)。"""

    name: str
    price: int | None
    status: str  # "未习得"/"升级"
    name_cy: int  # 潜质名 y 中心(行定位用)
    level: int = 0  # 当前等级(0=未习得, 1-4=可升级, 从"Lv.N"读)
    button_rect: tuple[int, int, int, int] | None = None  # 习得/升级按钮 bbox (x1,y1,x2,y2)


def drag_scroll_up(anchor: tuple[int, int] = SCROLL_ANCHOR, pixels: int = SCROLL_PIXELS) -> None:
    """内容上滑（看下方潜质）。复用 executor._drag_scroll 的 ctypes 实现。"""
    _drag(anchor, -pixels)  # 上滑(dy负)= 手指向上 = 内容上移 = 看下方


def drag_scroll_down(anchor: tuple[int, int] = SCROLL_ANCHOR, pixels: int = SCROLL_PIXELS) -> None:
    """内容下滑（看上方/滑回顶部）。反方向: 手指向下 = 内容下移 = 看上方。"""
    _drag(anchor, pixels)


def _drag(anchor: tuple[int, int], dy_total: int) -> None:
    """低层拖拽(ctypes mouse_event)。dy_total<0=上滑看下方, >0=下滑看上方。"""
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    user32 = ctypes.windll.user32
    steps = 25
    user32.SetCursorPos(anchor[0], anchor[1])
    time.sleep(0.1)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.18)
    step_dy = int(dy_total / steps) or (1 if dy_total > 0 else -1)
    for _ in range(steps):
        user32.mouse_event(MOUSEEVENTF_MOVE, 0, step_dy, 0, 0)
        time.sleep(0.008)
    time.sleep(0.12)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.SetCursorPos(anchor[0], anchor[1])


def read_skill_lines(image: "Image.Image", engine: "RapidOcrEngine") -> list[SkillLine]:
    """OCR 一帧，返回可见潜质行（按 y 排序）。

    §22.13 用"习得"/"升级"按钮(右侧 x>1800)作锚点定位行——每个可操作潜质都有这俩按钮
    之一(满级 Lv.MAX 无按钮, 跳过)。同 y±60 找 name(左) + price(右最右数字, 避开 SALE)
    + level(左"Lv.N")。status 从按钮文字推断: "习得"→未习得, "升级"→可升级。
    """
    import re as _re
    lines = engine.read_lines(image)
    # 1) 找"习得"/"升级"按钮(右侧 x>1800)作行锚点
    button_lines = []
    for ln in lines:
        t = normalize_ocr_text(ln.text).strip()
        lx1 = ln.box[0]
        if lx1 < 1800:
            continue
        if "习得" in t:
            button_lines.append((ln.box, "未习得"))
        elif "升级" in t or "并级" in t:  # OCR 容错
            button_lines.append((ln.box, "升级"))
    if not button_lines:
        return []

    # 2) 每个按钮对应一个潜质行
    out: list[SkillLine] = []
    for sbox, status in button_lines:
        sx1, sy1, sx2, sy2 = sbox
        anchor_cy = (sy1 + sy2) // 2
        # 找潜质名（左 x 1000-1800 非状态/习得/升级/SALE/Lv 文字）
        name = ""
        name_cy = anchor_cy
        for ln in lines:
            lx1, ly1, lx2, ly2 = ln.box
            lcy = (ly1 + ly2) // 2
            if abs(lcy - anchor_cy) > 60:
                continue
            t = normalize_ocr_text(ln.text).strip()
            if not t:
                continue
            # 排除按钮/状态/折扣/Lv 文字(大小写不敏感)
            t_upper = t.upper()
            if any(k in t for k in ("习得", "升级", "并级")) or "SALE" in t_upper or "LV" in t_upper or "MAX" in t_upper:
                continue
            if 1000 <= lx1 < 1800 and not t.replace(",", "").replace(".", "").isdigit():
                clean = t
                if clean and len(clean) >= 2 and not clean.isascii():
                    name = clean
                    name_cy = lcy
                    break
                if clean and len(clean) >= 3:
                    name = clean
                    name_cy = lcy
                    break
        if not name:
            continue
        # 找价格（右 x>1950 最右数字，避开 SALE）
        best_price: int | None = None
        best_price_x = -1
        for ln in lines:
            lx1, ly1, lx2, ly2 = ln.box
            lcy = (ly1 + ly2) // 2
            if abs(lcy - anchor_cy) > 60:
                continue
            t = normalize_ocr_text(ln.text).strip()
            if lx1 > 1950 and "SALE" not in t.upper():
                num = parse_first_int(t)
                if num is not None and lx1 > best_price_x:
                    best_price_x = lx1
                    best_price = num
        # 找等级(左"Lv.N", 升级状态时读当前等级)
        level = 0
        if status == "升级":
            for ln in lines:
                lx1, ly1, lx2, ly2 = ln.box
                lcy = (ly1 + ly2) // 2
                if abs(lcy - anchor_cy) > 60 or lx1 > 1800:
                    continue
                t = normalize_ocr_text(ln.text).strip()
                m = _re.search(r"Lv\.?\s*(\d)", t, _re.IGNORECASE)
                if m:
                    level = int(m.group(1))
                    break
        # button_rect: 习得/升级按钮 bbox(点击用)。直接用 OCR 检测到的按钮位置,
        # 不依赖 button region 匹配(后者 x 偏右会点错位置)。
        out.append(SkillLine(
            name=name, price=best_price, status=status, name_cy=name_cy, level=level,
            button_rect=(sx1, sy1, sx2, sy2),
        ))
    return out
