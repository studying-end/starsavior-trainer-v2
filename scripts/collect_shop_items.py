"""真机采集商店交易商品入库（独立脚本，不改游戏代码）。

项目现有自动入库逻辑只在 live_loop 跑交易流程时触发（shop_inspector 逐行点击
+ OCR + save_shop）。本脚本独立完成同样的事，无需跑完整 live_loop：逐个点开
商品读 effect/name/price → 查 shop_db → 未入库的 save_shop（priority=99，用户
手填前不买）→ 入库前展示清单让用户确认。

== 流程 ==
1. 截图 + 加载 region profile + shop_db
2. OCR 读 3 个商品行的 name/price
3. 逐行点击商品（选中后中央面板显示 effect），等面板刷新 → OCR 读 shop_detail_effect
4. 对每个商品 name+effect+price 查 shop_db，标记新商品
5. 展示清单（已入库 / 新商品）让用户确认
6. 确认后对新商品调 save_shop（priority=99）

== 复用 game logic（与 live_loop 入库一致）==
- region 字段：shop_item_N / shop_item_N_name / shop_item_N_price / shop_detail_effect
- shop_db.find_shop / save_shop（与 shop_inspector.decide 入库逻辑同款）
- 首商品坑：游戏默认打开第一个商品（selected_effect 非空）→ 第一个不点直接读
- 面板刷新坑：点击后 OCR 可能仍读旧 effect → 等待 effect 变化（最多 3 帧）

== 安全 ==
- 只点商品行（shop_item_N）+ back_button，绝不碰 shop_buy_button
- 鼠标撞屏幕 4 角急停（pyautogui FAILSAFE）
- 入库前必须用户确认（--yes 跳过确认直接入库）

用法：
    python scripts/collect_shop_items.py
    python scripts/collect_shop_items.py --window-title "StarSavior" --yes
    python scripts/collect_shop_items.py --dry-run   # 只读不入库
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Windows 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PIL import Image  # noqa: E402

from starsavior_trainer import shop_db  # noqa: E402
from starsavior_trainer.capture import activate_window, capture_window  # noqa: E402
from starsavior_trainer.models import Rect  # noqa: E402
from starsavior_trainer.ocr import RapidOcrEngine  # noqa: E402
from starsavior_trainer.ocr_reader import RegionOcrReader  # noqa: E402
from starsavior_trainer.regions import RegionProfile, load_region_profile  # noqa: E402
from starsavior_trainer.text_utils import normalize_ocr_text, parse_first_int  # noqa: E402

# 详情面板刷新等待（点击商品后中央面板渲染 effect 需要时间）
_DEFAULT_PANEL_DELAY = 0.8
# effect 稳定判定：连续读到相同 effect 的帧数（防瞬态）
_EFFECT_SETTLE_FRAMES = 2
# 倒数秒数
_DEFAULT_COUNTDOWN = 3


@dataclass
class ShopRow:
    """单个商品行的采集结果。"""

    idx: int  # 1-based
    name: str = ""
    price: int = 0
    effect: str = ""
    in_db: bool = False  # 是否已在模板库
    db_priority: int | None = None  # 已入库时的 priority


def _load_profile() -> RegionProfile:
    path = _PROJECT_ROOT / "config" / "regions" / "2560x1440.json"
    return load_region_profile(path)


def _shop_db_path() -> Path:
    return _PROJECT_ROOT / "config" / "shop_items.json"


def _check_corner_stop() -> None:
    """鼠标角落急停 — 撞 4 角立即抛 KeyboardInterrupt 退出。"""
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


def _click_center(rect: Rect, client_window_rect: Rect) -> None:
    """截图坐标(2560x1440) → 屏幕坐标点击。"""
    import pyautogui

    sx = client_window_rect.width / 2560.0
    sy = client_window_rect.height / 1440.0
    screen_x = client_window_rect.x + round(rect.center[0] * sx)
    screen_y = client_window_rect.y + round(rect.center[1] * sy)
    _check_corner_stop()
    pyautogui.click(screen_x, screen_y)


def _read_effect_stable(
    window_title: str,
    profile: RegionProfile,
    engine: RapidOcrEngine,
    prev_effect: str,
) -> str:
    """点击商品后读 shop_detail_effect，等待稳定（防面板未刷新读到旧值）。

    每帧新建 RegionOcrReader（reader 内部 lazy 缓存 _lines，复用 reader 会读到旧帧）。
    最多重试 _EFFECT_SETTLE_FRAMES+3 帧：effect 与 prev_effect 不同即认为刷新成功，
    再连续 N 帧相同 effect 视为稳定（同 effect 商品也会被记录）。
    """
    last_effect = prev_effect
    same_count = 0
    for _ in range(_EFFECT_SETTLE_FRAMES + 3):
        time.sleep(_DEFAULT_PANEL_DELAY)
        _check_corner_stop()
        img, _ = capture_window(window_title)
        # 每帧新 reader（避免 _lines 缓存旧帧）
        reader = RegionOcrReader(profile, engine)
        rt_list = reader.read_names(img, ("shop_detail_effect",))
        text = ""
        if rt_list:
            text = normalize_ocr_text(rt_list[0].text.strip())
        # effect 变了 → 刷新成功，再确认一次稳定
        if text and text != prev_effect:
            if text == last_effect:
                same_count += 1
                if same_count >= _EFFECT_SETTLE_FRAMES:
                    return text
            else:
                same_count = 1
                last_effect = text
        elif text and text == prev_effect:
            # 仍读旧值 → 继续等
            same_count = 0
    return last_effect


def _read_rows(profile: RegionProfile, reader: RegionOcrReader, image: Image.Image) -> list[ShopRow]:
    """OCR 读 3 个商品行的 name/price（不点击，从单张截图）。"""
    # 一次性读所有 shop_item_N_name / shop_item_N_price
    names_to_read = []
    for idx in range(1, 6):
        if profile.regions.get(f"shop_item_{idx}") is None:
            continue
        names_to_read.append(f"shop_item_{idx}_name")
        names_to_read.append(f"shop_item_{idx}_price")
    texts: dict[str, str] = {}
    if names_to_read:
        for rt in reader.read_names(image, names_to_read):
            texts[rt.name] = rt.text

    rows: list[ShopRow] = []
    for idx in range(1, 6):
        if profile.regions.get(f"shop_item_{idx}") is None:
            continue
        name = normalize_ocr_text(texts.get(f"shop_item_{idx}_name", "").strip())
        price_text = texts.get(f"shop_item_{idx}_price", "")
        parsed = parse_first_int(price_text)
        price = parsed if parsed is not None else 0
        rows.append(ShopRow(idx=idx, name=name, price=price))
    return rows


def _countdown(seconds: int) -> None:
    for i in range(seconds, 0, -1):
        print(f"\r  {i} 秒后开始（鼠标撞屏幕 4 角可急停）...", end="", flush=True)
        time.sleep(1)
    print("\r  开始！" + " " * 30)


def _print_rows(rows: list[ShopRow]) -> None:
    """展示采集清单（已入库 / 新商品）。"""
    print("\n" + "=" * 72)
    print("  采集清单（商品行 name / price / effect / 模板库状态）")
    print("=" * 72)
    new_count = 0
    for r in rows:
        status = f"已入库 priority={r.db_priority}" if r.in_db else "★新商品（待入库）"
        if not r.in_db:
            new_count += 1
        print(f"  #{r.idx} [{status}]")
        print(f"     name : {r.name or '(空)'}")
        print(f"     price: {r.price}")
        print(f"     effect: {r.effect or '(空)'}")
    print()
    print(f"  合计 {len(rows)} 个商品，其中 {new_count} 个新商品待入库")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="采集商店交易商品入模板库（独立脚本）。")
    parser.add_argument("--window-title", default="StarSavior", help="游戏窗口标题子串")
    parser.add_argument("--countdown", type=int, default=_DEFAULT_COUNTDOWN, help="开始前倒数秒数")
    parser.add_argument("--dry-run", action="store_true", help="只读不入库（不写 shop_items.json）")
    parser.add_argument("--yes", action="store_true", help="跳过确认直接入库新商品")
    args = parser.parse_args()

    profile = _load_profile()
    db_path = _shop_db_path()
    all_entries = shop_db.load_shop(db_path)
    print(f"[region] config/regions/2560x1440.json")
    print(f"[模板库] {db_path}  现有 {len(all_entries)} 条商品记录")

    # 找窗口
    print(f"\n[窗口] 查找 '{args.window_title}' ...")
    image, window = capture_window(args.window_title)
    print(f"[窗口] 命中: hwnd={window.hwnd} title={window.title!r} client={window.rect.width}x{window.rect.height}")
    activate_window(window.hwnd)

    # OCR reader（profile 必传；image 在 read_names 时按帧传入）
    engine = RapidOcrEngine()
    reader = RegionOcrReader(profile, engine)

    # 1. 读 3 个商品行 name/price
    rows = _read_rows(profile, reader, image)
    if not rows:
        print("[警告] 没读到任何商品行，当前可能不在交易界面")
        return 1
    print(f"\n[扫描] 读到 {len(rows)} 个商品行")

    # 2. 倒数
    _countdown(args.countdown)

    # 3. 逐行点击读 effect
    print("\n[采集] 逐个点开商品读 effect（不会点购买按钮）...")
    try:
        # 首商品坑：游戏默认打开第一个商品 → selected_effect 已显示，第一个不点直接读
        initial_effect = ""
        et_list = reader.read_names(image, ("shop_detail_effect",))
        if et_list:
            initial_effect = normalize_ocr_text(et_list[0].text.strip())
        if initial_effect.strip() and rows:
            print(f"  #{rows[0].idx} 首商品已默认选中，直接读 effect: {initial_effect!r}")
            rows[0].effect = initial_effect
            start_idx = 1
        else:
            start_idx = 0

        prev_effect = initial_effect
        for i in range(start_idx, len(rows)):
            row = rows[i]
            item_rect = profile.regions.get(f"shop_item_{row.idx}")
            if item_rect is None:
                continue
            print(f"  #{row.idx} 点击商品行 ...")
            _click_center(item_rect, window.rect)
            effect = _read_effect_stable(args.window_title, profile, engine, prev_effect)
            row.effect = effect
            prev_effect = effect
            print(f"  #{row.idx} name={row.name!r} price={row.price} effect={effect!r}")
    except KeyboardInterrupt:
        print("\n[急停] 用户中止（鼠标角落 / Ctrl+C）")
        # 仍展示已采集的部分
        if not rows:
            return 130
        # 回退：点 back 离开商品详情（不买）
        back = profile.regions.get("shop_back_button")
        if back is not None:
            try:
                _click_center(back, window.rect)
            except Exception:
                pass

    # 4. 查模板库标记新商品
    for row in rows:
        if row.name:
            entry = shop_db.find_shop(all_entries, row.name)
            if entry is not None:
                row.in_db = True
                row.db_priority = entry.priority

    # 5. 展示清单
    _print_rows(rows)
    new_rows = [r for r in rows if not r.in_db and r.name]

    if not new_rows:
        print("\n[完成] 无新商品需入库（所有商品已在模板库）")
        # 回退点 back
        back = profile.regions.get("shop_back_button")
        if back is not None:
            try:
                _click_center(back, window.rect)
                print("[安全] 已点返回按钮离开商品详情（未购买）")
            except Exception:
                pass
        return 0

    if args.dry_run:
        print("\n[dry-run] 不入库。如需入库去掉 --dry-run")
        return 0

    # 6. 确认入库
    if not args.yes:
        print(f"\n即将入库 {len(new_rows)} 个新商品（priority=99，用户手填前不买）：")
        for r in new_rows:
            print(f"  - {r.name} | {r.effect} | {r.price}")
        ans = input("\n确认入库？[y/N] ").strip().lower()
        if ans != "y":
            print("[取消] 用户取消，不入库")
            back = profile.regions.get("shop_back_button")
            if back is not None:
                try:
                    _click_center(back, window.rect)
                except Exception:
                    pass
            return 0

    # 入库（save_shop priority 默认 99）
    print("\n[入库] 写入 shop_items.json ...")
    for r in new_rows:
        shop_db.save_shop(db_path, r.name, r.effect, r.price)
        print(f"  ✓ 入库: {r.name} | {r.effect} | {r.price} | priority=99")

    # 回退点 back（安全：不点 buy）
    back = profile.regions.get("shop_back_button")
    if back is not None:
        try:
            _click_center(back, window.rect)
            print("[安全] 已点返回按钮离开商品详情（未购买）")
        except Exception:
            pass

    # 重新加载确认
    new_entries = shop_db.load_shop(db_path)
    print(f"\n[完成] 模板库现有 {len(new_entries)} 条商品记录（原 {len(all_entries)} 条）")
    print("[提示] 新商品 priority=99（不买）。手填 priority 0-5 + classes 后才会购买。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
