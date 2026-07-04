"""极其详细的单帧运行日志（dry-run，不点击）。

对当前游戏帧（或指定截图）跑完整管线 capture → classify → parse → decide，
事无巨细输出：识别到的画面+置信度、payload 全字段（耐力/心情/金币/闪光/训练卡/按钮…）、
决策过程（policy.decide 的 Action + 理由）。调试 / 验证 bot 决策用，不执行任何点击。

用法:
  python -m scripts.detailed_frame_log                       # 实时截当前 StarSavior 帧
  python -m scripts.detailed_frame_log --image screenshots/flash_check.png
  python -m scripts.detailed_frame_log --build stamina_tank  # 指定 build profile
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import fields, is_dataclass

from PIL import Image

from starsavior_trainer.capture import capture_window
from starsavior_trainer.classifier import classify_hybrid
from starsavior_trainer.cli.blue_parsers import _read_screen_payload_ocr
from starsavior_trainer.models import (
    BlessingChoice,
    CommissionChoice,
    GameState,
    Observation,
    Rect,
    RestSubmenu,
    ShopScene,
    TrainingChoice,
    TrainingHubStatus,
)
from starsavior_trainer.ocr import RapidOcrEngine
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.policy.engine import TrainerPolicy
from starsavior_trainer.regions import load_region_profile, scale_region_profile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _r(rect) -> str:
    """Rect 紧凑表示。"""
    if rect is None:
        return "None"
    if isinstance(rect, Rect):
        return f"Rect({rect.x},{rect.y},{rect.width},{rect.height})"
    return repr(rect)


def _dump_training_hub(p: TrainingHubStatus) -> None:
    print("  [画面] 训练大厅 TRAINING_HUB")
    print(f"  [HUD ] 耐力(endurance)={p.endurance_ratio:.0%}  心情(mood)={p.mood}  金币(coins)={p.coins}")
    print(
        f"  [告警] 受理讨伐委托={p.has_commission_alert}  商店到货={p.has_shop_alert}  "
        f"可学技能={p.can_learn_skill}  ✨闪光训练={p.has_flash_training}"
    )
    print(f"  [回合] 日期={p.turn_label!r}  RANK={p.rank_label!r}  潜质点={p.potential_points}")
    print(
        f"  [按钮] 训练={_r(p.training_button)}  委托={_r(p.commission_button)}  "
        f"休息={_r(p.rest_button)}  商店={_r(p.shop_button)}  技能={_r(p.skill_button)}"
    )
    if p.rating_battle_button is not None or p.trading_button is not None:
        print(f"  [D-DAY] 评鉴战={_r(p.rating_battle_button)}  交易={_r(p.trading_button)}")


def _dump_training_select(choices) -> None:
    choices = list(choices)
    print(f"  [画面] 训练选择 TRAINING_SELECT  候选卡数={len(choices)}")
    for c in choices:
        print(
            f"  [卡] {c.name}: 训练值(gain)={c.stat_gain}  环(ring)={c.ring}  "
            f"失败率={c.fail_rate}%  选中={c.selected}  目标={_r(c.target)}  确认={_r(c.confirm_button)}"
        )


def _dump_rest(p: RestSubmenu) -> None:
    print("  [画面] 休息菜单 REST_SUBMENU")
    print(f"  [HUD ] 金币={p.coins}  有冥想室={p.has_meditation_room}")
    print(
        f"  [选项] 冥想室={_r(p.meditation_room)}  住处={_r(p.lodging)}  "
        f"露宿={_r(p.rough_sleep)}  确认={_r(p.confirm_button)}"
    )


def _dump_generic(payload) -> None:
    """通用 dataclass dump：遍历所有字段（事无巨细）。"""
    if is_dataclass(payload):
        for f in fields(payload):
            v = getattr(payload, f.name)
            print(f"  {f.name} = {v!r}")
    elif isinstance(payload, (list, tuple)):
        print(f"  [列表 {len(payload)} 项]")
        for i, item in enumerate(payload):
            print(f"  [{i}] {item!r}")
    else:
        print(f"  payload = {payload!r}")


def dump_payload(payload) -> None:
    print("=== 识别到的详细信息（payload）===")
    if payload is None:
        print("  (无 payload 解析)")
        return
    if isinstance(payload, TrainingHubStatus):
        _dump_training_hub(payload)
    elif isinstance(payload, (list, tuple)) and payload and isinstance(payload[0], TrainingChoice):
        _dump_training_select(payload)
    elif isinstance(payload, RestSubmenu):
        _dump_rest(payload)
    else:
        _dump_generic(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description="极其详细的单帧运行日志（dry-run，不点击）")
    ap.add_argument("--window-title", default="StarSavior", help="实时截屏的窗口标题")
    ap.add_argument("--image", help="用指定截图而非实时截屏")
    ap.add_argument("--profile", default="config/regions/2560x1440.json", help="region profile JSON")
    ap.add_argument("--build", default="balanced", help="build profile: balanced/power_focus/stamina_tank/...")
    ap.add_argument("--save", help="把当前帧保存到此路径")
    args = ap.parse_args()

    print("=" * 64)
    # 1. capture
    if args.image:
        screenshot = Image.open(args.image)
        print(f"=== 截图来源: 文件 {args.image} ({screenshot.size[0]}x{screenshot.size[1]}) ===")
    else:
        screenshot, window = capture_window(args.window_title)
        print(f"=== 截图来源: 实时窗口 {window.title!r} ({screenshot.size[0]}x{screenshot.size[1]}) ===")
    if args.save:
        screenshot.save(args.save)
        print(f"  已保存帧到 {args.save}")

    profile = scale_region_profile(load_region_profile(args.profile), screenshot.size)
    reader = RegionOcrReader(profile, RapidOcrEngine())

    # 2. classify
    print("=== 第1步 识别画面（classify_hybrid）===")
    obs = classify_hybrid(screenshot, profile, reader)
    print(f"  → 画面={obs.screen.value}  置信度={obs.confidence:.2f}")

    # 3. parse payload
    print("=== 第2步 解析画面元素（parse payload）===")
    payload = _read_screen_payload_ocr(obs.screen, screenshot, profile, reader, verbose=False)
    dump_payload(payload)
    obs = Observation(screen=obs.screen, confidence=obs.confidence, payload=payload)

    # 4. decide
    print("=== 第3步 决策（policy.decide）===")
    state = GameState(build_profile=args.build)
    policy = TrainerPolicy()
    action = policy.decide(state, obs)
    print(f"  → 动作={action.kind}  目标={_r(action.target)}  理由={action.reason}")
    if getattr(action, "repeat", 1) and action.repeat > 1:
        print(f"  → 重复 {action.repeat} 次（连点过场）")

    # 5. 结论
    print("=" * 64)
    print(f"➡ 最终选择: {action.kind}  |  {action.reason}")
    print("=" * 64)


if __name__ == "__main__":
    main()
