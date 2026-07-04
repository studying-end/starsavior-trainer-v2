"""真机测试：逐张点训练卡统计人头（总数 / 作数 / 不作数 / 羁绊达标变不作数）。

独立测试脚本，不改游戏代码。用于验证"支援卡羁绊达标 → 人头从作数变不作数"
功能在真机上工作正常。复用 vision 的判定函数（_is_head_template / _is_bond_maxed
/ _HEAD_MATCH_THRESHOLD），与 count_heads 同款逻辑分类人头。

== 流程 ==
1. 找窗口 + activate + capture（2560x1440）
2. 倒数 3 秒（给用户准备）
3. 逐张点击 5 张训练卡（power/stamina/guts/wisdom/speed），只点卡选中，**绝不点确认**
4. 每次点击后等面板刷新 → 重新截图 → 分类统计人头
5. 输出每张卡 4 类人头 + 汇总表

== 安全 ==
- 只 activate 一次（抢焦点到游戏），后续靠 pyautogui.click
- 鼠标角落急停（pyautogui FAILSAFE，撞 4 角立即抛异常退出）
- 只 click 卡 rect 的 center，绝不碰 training_select_confirm_button

== 人头分类（4 类，自洽：总数 = 作数 + 不作数 + 达标变不作数）==
- 作数(未达标) = 作数模板 N.png 在场 且 羁绊进度条非黄
- 羁绊达标变不作数 = 作数模板 N.png 在场 且 羁绊进度条黄（_is_bond_maxed）
- 不作数 = 不作数模板 non_counting_head_N.png 在场
- 旧库 counting_head_*.png 跳过（与 count_heads 语义一致）

用法：
    python scripts/inspect_training_heads.py
    python scripts/inspect_training_heads.py --window-title "StarSavior" --delay 0.8
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Windows 强制 UTF-8 输出（中文叙述 + 表格）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 让脚本能从项目根目录直接 run（python scripts/xxx.py）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PIL import Image  # noqa: E402

from starsavior_trainer.capture import activate_window, capture_window  # noqa: E402
from starsavior_trainer.models import Rect  # noqa: E402
from starsavior_trainer.regions import RegionProfile, load_region_profile, scale_region_profile  # noqa: E402
from starsavior_trainer.vision import (  # noqa: E402
    _HEAD_MATCH_THRESHOLD,
    _is_bond_maxed,
    _is_head_template,
)

# 5 张训练卡代码名（与 EARLY_GAME_HEAD_ATTRS 一致，按 y 从上到下）
TRAINING_CARDS = ("power", "stamina", "guts", "wisdom", "speed")

# 中文名（用于输出表，与 EARLY_GAME_HEAD_ATTRS 注释一致）
CARD_CN = {
    "power": "力量",
    "stamina": "体力",
    "guts": "韧性",
    "wisdom": "专注",
    "speed": "保护",
}

# 不作数模板命名（旧库 + 新库）
import re  # noqa: E402

_NON_COUNTING_RE = re.compile(r"^non_counting_head_\d+\.png$")

# 面板刷新等待（秒）。点击卡后右侧详情面板要时间渲染支援卡头像。
_DEFAULT_PANEL_DELAY = 0.7

# 倒数秒数
_DEFAULT_COUNTDOWN = 3


@dataclass
class HeadBreakdown:
    """单张训练卡的人头分类统计。"""

    counting: int = 0  # 作数(未达标) — 贡献给 count_heads 的头
    bond_maxed: int = 0  # 羁绊达标变不作数 — 模板是作数但进度条黄
    non_counting: int = 0  # 不作数 — non_counting_head 模板
    matched_counting_templates: list[str] = None  # 命中的作数模板文件名（诊断用）
    matched_non_counting_templates: list[str] = None  # 命中的不作数模板文件名
    matched_bond_maxed_templates: list[str] = None  # 达标作数模板文件名

    def __post_init__(self):
        if self.matched_counting_templates is None:
            self.matched_counting_templates = []
        if self.matched_non_counting_templates is None:
            self.matched_non_counting_templates = []
        if self.matched_bond_maxed_templates is None:
            self.matched_bond_maxed_templates = []

    @property
    def total(self) -> int:
        """总人头（含达标变不作数）。"""
        return self.counting + self.bond_maxed + self.non_counting


def _load_profile() -> tuple[RegionProfile, str]:
    """加载 2560x1440 region profile（capture_window 默认缩放到该分辨率）。"""
    path = _PROJECT_ROOT / "config" / "regions" / "2560x1440.json"
    profile = load_region_profile(path)
    return profile, str(path)


def _list_assets() -> tuple[list[Path], list[Path]]:
    """返回 (作数模板列表, 不作数模板列表)。

    作数 = 新库 N.png（_is_head_template）；不作数 = non_counting_head_N.png。
    旧库 counting_head_*.png 跳过（与 count_heads 语义一致）。
    """
    assets = _PROJECT_ROOT / "config" / "assets"
    counting, non_counting = [], []
    for f in sorted(assets.glob("*.png")):
        if _is_head_template(f):
            counting.append(f)
        elif _NON_COUNTING_RE.match(f.name):
            non_counting.append(f)
    return counting, non_counting


def _classify_heads(image: Image.Image) -> HeadBreakdown:
    """对一张截图分类人头（与 count_heads 同款判定，但拆 4 类）。

    复用 vision 的 _is_head_template / _is_bond_maxed / _HEAD_MATCH_THRESHOLD，
    保证判定与 game logic 完全一致。
    """
    import cv2
    import numpy as np

    breakdown = HeadBreakdown()
    search = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

    counting_templates, non_counting_templates = _list_assets()

    # 作数模板：在场则进一步看羁绊进度条是否黄（达标 → bond_maxed，否则 counting）
    for tpl_path in counting_templates:
        tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
        if tpl is None or tpl.shape[0] > search.shape[0] or tpl.shape[1] > search.shape[1]:
            continue
        res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        if float(res.max()) <= _HEAD_MATCH_THRESHOLD:
            continue
        # 命中：定位最佳点查羁绊进度条
        _, _, _, loc = cv2.minMaxLoc(res)
        if _is_bond_maxed(search, loc, tpl.shape[1], tpl.shape[0]):
            breakdown.bond_maxed += 1
            breakdown.matched_bond_maxed_templates.append(tpl_path.name)
        else:
            breakdown.counting += 1
            breakdown.matched_counting_templates.append(tpl_path.name)

    # 不作数模板：在场即 non_counting（与 count_heads 一致：根本不扫这批模板）
    for tpl_path in non_counting_templates:
        tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
        if tpl is None or tpl.shape[0] > search.shape[0] or tpl.shape[1] > search.shape[1]:
            continue
        res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        if float(res.max()) > _HEAD_MATCH_THRESHOLD:
            breakdown.non_counting += 1
            breakdown.matched_non_counting_templates.append(tpl_path.name)

    return breakdown


def _check_corner_stop() -> None:
    """鼠标角落急停 — 撞 4 角立即抛异常退出。

    独立测试脚本用 pyautogui 自带 FAILSAFE（点 4 角即抛 FailSafeException），
    这里在每次点击前额外查一次，给用户中途退出的机会。
    """
    try:
        import ctypes
        from ctypes import wintypes

        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)
        margin = 120
        near_x = pt.x <= margin or pt.x >= width - margin
        near_y = pt.y <= margin or pt.y >= height - margin
        if near_x and near_y:
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        raise
    except Exception:
        pass


def _click_card_center(card_rect: Rect, client_window_rect: Rect) -> None:
    """点击训练卡 center（截图坐标 → 屏幕坐标）。

    截图缩放到 2560x1440，region profile 也是 2560x1440，但实际窗口 client
    可能是其他尺寸 → 按比例映射回屏幕坐标（与 live_loop map_action_to_rect 同款）。
    """
    import pyautogui

    sx = client_window_rect.width / 2560.0
    sy = client_window_rect.height / 1440.0
    screen_x = client_window_rect.x + round(card_rect.center[0] * sx)
    screen_y = client_window_rect.y + round(card_rect.center[1] * sy)
    _check_corner_stop()
    pyautogui.click(screen_x, screen_y)


def _countdown(seconds: int) -> None:
    """倒数 N 秒，给用户切到游戏窗口 + 准备急停。"""
    for i in range(seconds, 0, -1):
        print(f"\r  {i} 秒后开始（鼠标撞屏幕 4 角可急停）...", end="", flush=True)
        time.sleep(1)
    print("\r  开始！" + " " * 30)


def _format_row(name: str, cn: str, b: HeadBreakdown) -> str:
    return f"| {name:<8} | {cn:<4} | {b.counting:^6} | {b.non_counting:^8} | {b.bond_maxed:^14} | {b.total:^4} |"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="逐张点训练卡统计人头分类（总数/作数/不作数/羁绊达标变不作数）。"
    )
    parser.add_argument("--window-title", default="StarSavior", help="游戏窗口标题子串（默认 StarSavior）")
    parser.add_argument(
        "--delay",
        type=float,
        default=_DEFAULT_PANEL_DELAY,
        help=f"点击卡后面板刷新等待秒数（默认 {_DEFAULT_PANEL_DELAY}）",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=_DEFAULT_COUNTDOWN,
        help=f"开始前倒数秒数（默认 {_DEFAULT_COUNTDOWN}）",
    )
    parser.add_argument("--no-click", action="store_true", help="不点击，只统计当前画面（用于已选中某卡时）")
    args = parser.parse_args()

    # 1. 加载 region profile + 模板库诊断
    profile, profile_path = _load_profile()
    counting_tpls, non_counting_tpls = _list_assets()
    print(f"[region] {profile_path}")
    print(f"[模板库] 作数(counting) {len(counting_tpls)} 个: {', '.join(p.name for p in counting_tpls) or '(无)'}")
    print(f"[模板库] 不作数(non_counting) {len(non_counting_tpls)} 个: {', '.join(p.name for p in non_counting_tpls) or '(无)'}")
    if not counting_tpls and not non_counting_tpls:
        print("[警告] 模板库为空，所有统计将是 0。请先用 collect_head_templates 采集头像。")
        return 1

    # 2. 找窗口 + activate（只一次）
    print(f"\n[窗口] 查找 '{args.window_title}' ...")
    image, window = capture_window(args.window_title)
    print(f"[窗口] 命中: hwnd={window.hwnd} title={window.title!r} client={window.rect.width}x{window.rect.height}")
    activate_window(window.hwnd)

    if args.no_click:
        print("\n[模式] no-click：仅统计当前画面（假设某卡已选中）")
        breakdown = _classify_heads(image)
        print(f"  → 作数(未达标)={breakdown.counting}  不作数={breakdown.non_counting}  羁绊达标变不作数={breakdown.bond_maxed}  总数={breakdown.total}")
        if breakdown.matched_counting_templates:
            print(f"    作数模板: {breakdown.matched_counting_templates}")
        if breakdown.matched_bond_maxed_templates:
            print(f"    达标模板: {breakdown.matched_bond_maxed_templates}")
        if breakdown.matched_non_counting_templates:
            print(f"    不作数模板: {breakdown.matched_non_counting_templates}")
        return 0

    # 3. 倒数
    _countdown(args.countdown)

    # 4. 逐张点训练卡 + 统计
    print("\n[扫描] 逐张点击训练卡统计人头（不会点确认按钮）...\n")
    results: dict[str, HeadBreakdown] = {}
    try:
        for attr in TRAINING_CARDS:
            card_rect = profile.regions.get(f"training_select_card_{attr}")
            if card_rect is None:
                print(f"  [{attr}/{CARD_CN[attr]}] region 缺失，跳过")
                continue
            _click_card_center(card_rect, window.rect)
            time.sleep(args.delay)
            _check_corner_stop()
            # 重新截图（面板已刷新支援卡头像）
            screenshot, _ = capture_window(args.window_title)
            breakdown = _classify_heads(screenshot)
            results[attr] = breakdown
            print(f"  [{attr}/{CARD_CN[attr]}] 作数={breakdown.counting}  不作数={breakdown.non_counting}  羁绊达标变不作数={breakdown.bond_maxed}  总数={breakdown.total}")
            if breakdown.matched_counting_templates:
                print(f"      作数模板: {breakdown.matched_counting_templates}")
            if breakdown.matched_bond_maxed_templates:
                print(f"      ★达标模板: {breakdown.matched_bond_maxed_templates}")
            if breakdown.matched_non_counting_templates:
                print(f"      不作数模板: {breakdown.matched_non_counting_templates}")
    except KeyboardInterrupt:
        print("\n[急停] 用户中止（鼠标角落 / Ctrl+C）")
        return 130

    # 5. 汇总表
    print("\n" + "=" * 72)
    print("  汇总表（每张训练卡的人头分类）")
    print("=" * 72)
    print(f"| {'属性':<8} | {'中文':<4} | {'作数':^6} | {'不作数':^8} | {'达标变不作数':^14} | {'总数':^4} |")
    print("|" + "-" * 10 + "|" + "-" * 6 + "|" + "-" * 8 + "|" + "-" * 10 + "|" + "-" * 16 + "|" + "-" * 6 + "|")
    for attr in TRAINING_CARDS:
        if attr in results:
            print(_format_row(attr, CARD_CN[attr], results[attr]))
    print()
    total_counting = sum(r.counting for r in results.values())
    total_non_counting = sum(r.non_counting for r in results.values())
    total_bond = sum(r.bond_maxed for r in results.values())
    print(f"  全卡合计：作数(未达标)={total_counting}  不作数={total_non_counting}  羁绊达标变不作数={total_bond}")
    if total_bond > 0:
        print(f"  ✓ 检测到 {total_bond} 个羁绊达标人头（已从作数变不作数），功能生效中")
    else:
        print("  （未检测到羁绊达标人头 — 可能本回合无支援卡达标，或阈值需校准）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
