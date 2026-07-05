"""真机采集潜质（技能）入模板库（独立脚本，不改游戏代码）。

滑动扫库识别全部潜质 → 入库 config/skills.json（battle_priority + breeding_priority
默认 99，用户手填前不学）。两套优先级存一个 JSON 避免重复维护潜质名。

== 流程 ==
1. 截图 + 找窗口 + activate
2. 滑动扫库：scrollbar 上滑（内容上移看下方潜质），每滑重 OCR，按名字集合判到底
3. 每个潜质读：name + 当前价格（习得后数字，含折扣）+ 类型推断（感知/技巧/天赋/通用）
4. 展示清单（name/价格/类型/已入库状态），确认后入库

== 实机结构（潜质管理窗口）==
每行潜质（行高 ~170px）：
- 潜质名（攻击感知等, x≈1030, y 偏下）
- 状态（未习得/已习得, 左 x≈1034, y 偏上）
- 折扣标签（35%SALE 等, x≈2006, y 偏上 ← 避开）
- 习得按钮文字（习得, x≈1882, y 居中）
- 价格数字（65/80 等, x≈2018-2091, y 居中）
潜质点数（2857 等, x≈2124, y≈1103）+ X 关闭（2159,332）+ scrollbar [2165,365,22,675]

== 安全 ==
- 只滑动 + 读，绝不点习得按钮
- 鼠标撞屏幕 4 角急停（pyautogui FAILSAFE）

用法：
    python scripts/collect_skills.py
    python scripts/collect_skills.py --window-title "StarSavior" --yes
    python scripts/collect_skills.py --dry-run   # 只读不入库
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Windows 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PIL import Image  # noqa: E402

from starsavior_trainer import skill_db  # noqa: E402
from starsavior_trainer import skill_reader  # noqa: E402
from starsavior_trainer.capture import activate_window, capture_window  # noqa: E402
from starsavior_trainer.models import Rect  # noqa: E402
from starsavior_trainer.ocr import RapidOcrEngine  # noqa: E402
from starsavior_trainer.text_utils import normalize_ocr_text, parse_first_int  # noqa: E402

# 滑动参数（用 skill_reader 共享）
_SCROLL_MAX = 20
_SCROLL_SETTLE = 0.8


@dataclass
class SkillRow:
    """单行潜质采集结果。"""

    name: str = ""
    price: int | None = None  # 当前价格（含折扣）；None=未读到
    kind: str = ""
    status: str = ""  # 未习得/已习得/空
    in_db: bool = False


def _check_corner_stop() -> None:
    """鼠标角落急停。"""
    try:
        import ctypes
        from ctypes import wintypes

        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)
        margin = 120
        if (pt.x <= margin or pt.x >= width - margin) and (pt.y <= margin or pt.y >= height - margin):
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        raise
    except Exception:
        pass


def _drag_scroll_up(anchor: tuple[int, int] = skill_reader.SCROLL_ANCHOR, pixels: int = skill_reader.SCROLL_PIXELS) -> None:
    """内容上滑（看下方潜质）。委托给 skill_reader 共享实现。"""
    skill_reader.drag_scroll_up(anchor, pixels)


def _read_skill_rows(image: Image.Image, engine: RapidOcrEngine) -> list[SkillRow]:
    """OCR 一帧，返回可见潜质行。委托给 skill_reader.read_skill_lines，转 SkillRow。"""
    return [
        SkillRow(name=ln.name, price=ln.price, kind=skill_db.infer_kind(ln.name), status=ln.status)
        for ln in skill_reader.read_skill_lines(image, engine)
    ]


def _scroll_and_collect(
    window_title: str,
    engine: RapidOcrEngine,
    max_scrolls: int = _SCROLL_MAX,
) -> list[SkillRow]:
    """滑动扫库：从顶部开始，反复上滑（看下方），累积所有潜质（按 name 去重）。

    停止条件：连续 2 次 OCR 名字集合不变 = 到底。
    """
    all_skills: dict[str, SkillRow] = {}  # name -> row（去重，后看到的覆盖价格）
    prev_names: frozenset[str] = frozenset()
    same_count = 0

    # 先读当前帧（顶部）
    img, _ = capture_window(window_title)
    for row in _read_skill_rows(img, engine):
        all_skills[row.name] = row
        prev_names = prev_names | {row.name}
    print(f"  [扫库] 初始读到 {len(all_skills)} 个潜质: {sorted(all_skills.keys())}")

    for i in range(max_scrolls):
        # 注: 滑动循环内不做角落急停检查——_drag_scroll_up 用 mouse_event 相对移动,
        # 光标会停在滑动锚点(右侧), 与屏幕角落距离判断可能误触发。靠 Ctrl+C 兜底中止。
        _drag_scroll_up(_SCROLL_ANCHOR)
        time.sleep(_SCROLL_SETTLE)
        img, _ = capture_window(window_title)
        cur_rows = _read_skill_rows(img, engine)
        cur_names = frozenset(r.name for r in cur_rows)
        new_count = 0
        for row in cur_rows:
            if row.name not in all_skills:
                all_skills[row.name] = row
                new_count += 1
            else:
                # 已存在: 价格取最大值(纠正 OCR 少读一位, 如 8→80)。多帧累积更准。
                old = all_skills[row.name]
                if row.price is not None and (old.price is None or row.price > old.price):
                    old.price = row.price
        print(f"  [扫库] 滑动 {i+1}: 本帧 {len(cur_rows)} 个, 新增 {new_count}, 累积 {len(all_skills)} 个")
        # 到底判定：名字集合不变
        if cur_names == prev_names:
            same_count += 1
            if same_count >= 2:
                print(f"  [扫库] 连续 2 次名字集合不变, 判定到底")
                break
        else:
            same_count = 0
        prev_names = cur_names

    return list(all_skills.values())


def _print_rows(rows: list[SkillRow]) -> int:
    """展示采集清单，返回新潜质数。"""
    print("\n" + "=" * 72)
    print("  采集清单（潜质名 / 价格 / 类型 / 状态 / 模板库状态）")
    print("=" * 72)
    new_count = 0
    for r in sorted(rows, key=lambda x: x.name):
        flag = "已入库" if r.in_db else "★新潜质（待入库）"
        if not r.in_db:
            new_count += 1
        price_s = str(r.price) if r.price is not None else "(未读到)"
        print(f"  {r.name:<12} | 价格={price_s:<6} | {r.kind} | {r.status or '?':<5} | [{flag}]")
    print(f"\n  合计 {len(rows)} 个潜质，其中 {new_count} 个新潜质待入库")
    return new_count


def main() -> int:
    parser = argparse.ArgumentParser(description="采集潜质（技能）入模板库（独立脚本）。")
    parser.add_argument("--window-title", default="StarSavior", help="游戏窗口标题子串")
    parser.add_argument("--dry-run", action="store_true", help="只读不入库")
    parser.add_argument("--yes", action="store_true", help="跳过确认直接入库新潜质")
    args = parser.parse_args()

    db_path = _PROJECT_ROOT / "config" / "skills.json"
    all_entries = skill_db.load_skills(db_path)
    print(f"[模板库] {db_path}  现有 {len(all_entries)} 条潜质记录")

    # 找窗口
    print(f"\n[窗口] 查找 '{args.window_title}' ...")
    image, window = capture_window(args.window_title)
    print(f"[窗口] 命中: hwnd={window.hwnd} title={window.title!r} client={window.rect.width}x{window.rect.height}")
    activate_window(window.hwnd)

    engine = RapidOcrEngine()

    print(f"\n[扫库] 滑动扫库识别全部潜质（鼠标撞屏幕 4 角可急停）...")
    print("  3 秒后开始...")
    time.sleep(3)
    try:
        rows = _scroll_and_collect(args.window_title, engine)
    except KeyboardInterrupt:
        print("\n[急停] 用户中止（鼠标角落 / Ctrl+C）")
        return 130

    # 标记已入库
    for row in rows:
        if skill_db.find_skill(all_entries, row.name):
            row.in_db = True

    if not rows:
        print("\n[警告] 未读到任何潜质，可能不在潜质学习窗口")
        return 1

    new_count = _print_rows(rows)
    new_rows = [r for r in rows if not r.in_db]

    if not new_rows:
        print("\n[完成] 无新潜质需入库（所有潜质已在模板库）")
        return 0

    if args.dry_run:
        print("\n[dry-run] 不入库。如需入库去掉 --dry-run")
        return 0

    if not args.yes:
        ans = input(f"\n即将入库 {len(new_rows)} 个新潜质（battle/breeding priority=99），确认？[y/N] ").strip().lower()
        if ans != "y":
            print("[取消] 用户取消，不入库")
            return 0

    print(f"\n[入库] 写入 {db_path.name} ...")
    for r in new_rows:
        skill_db.save_skill(db_path, r.name, effect="", kind=r.kind)
        price_s = str(r.price) if r.price is not None else "?"
        print(f"  ✓ 入库: {r.name} | 价格={price_s} | {r.kind} | priority=99/99")

    new_entries = skill_db.load_skills(db_path)
    print(f"\n[完成] 模板库现有 {len(new_entries)} 条潜质（原 {len(all_entries)} 条）")
    print("[提示] 新潜质 priority=99（不学）。手填 battle_priority/breeding_priority 0-5 后才会学。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
