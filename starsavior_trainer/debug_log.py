"""调试模式详细日志：每帧 dump 识别(payload) + 决策(action)。

仅 live_loop `--debug` 时加载（正常模式 live_loop 不 import 本模块，零开销）。
dump 逻辑被 scripts/detailed_frame_log.py 复用。详见 docs/设计方案.md §22.7。
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass

from starsavior_trainer.models import (
    BlessingChoice,
    CommissionChoice,
    Rect,
    RestSubmenu,
    ShopScene,
    TrainingChoice,
    TrainingHubStatus,
)


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
    end = choices[0].endurance_ratio if choices else 0.0
    print(f"  [画面] 训练选择 TRAINING_SELECT  候选卡数={len(choices)}  当前耐力={end:.0%}")
    for c in choices:
        flash = "✨闪光 " if c.is_flash else ""
        print(
            f"  [卡] {c.name}: {flash}训练值(gain)={c.stat_gain}  环(ring)={c.ring}  "
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
            print(f"  {f.name} = {getattr(payload, f.name)!r}")
    elif isinstance(payload, (list, tuple)):
        print(f"  [列表 {len(payload)} 项]")
        for i, item in enumerate(payload):
            print(f"  [{i}] {item!r}")
    else:
        print(f"  payload = {payload!r}")


def dump_payload(payload) -> None:
    """dump payload 全字段（按画面类型定制 + 通用兜底）。"""
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


def dump_observation(observation) -> None:
    """调试：dump 当前帧识别（画面 + payload 全字段）。每帧 classify+parse 后调。"""
    print(f"  [debug 识别] 画面={observation.screen.value}  置信度={observation.confidence:.2f}")
    dump_payload(observation.payload)


def dump_decision(action) -> None:
    """调试：dump 决策 Action（动作/目标/理由）。每帧 decide 后调。"""
    target = _r(action.target) if hasattr(action.target, "x") else repr(action.target)
    repeat = f" ×{action.repeat}" if getattr(action, "repeat", 1) and action.repeat > 1 else ""
    print(f"  [debug 决策] {action.kind} → {target}{repeat} | {action.reason}")
