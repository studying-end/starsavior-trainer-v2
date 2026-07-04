"""画面注册表 — 唯一调度枢纽。

架构契约核心：classifier 画面匹配、policy.decide、live_loop payload 读取三处统一走本注册表。
加新画面 = 往 HANDLERS 注册一个 handler(+ 区域 JSON)，只动此处。

handler 是 DelegatingScreenHandler，转发到已迁的 parse_X(T10) / decide_X(T13) / _has_X_signature(T8)。
_decide_X 是薄包装(校验 payload + 调 policy.decide_X)，行为与旧 TrainerPolicy.decide 分支 1:1。
"""
from __future__ import annotations

from starsavior_trainer.classifier_signatures import (
    _has_battle_signature,
    _has_commission_select_signature,
    _has_dialogue_signature,
    _has_event_choice_signature,
    _has_game_menu_signature,
    _has_initial_signature,
    _has_post_training_signature,
    _has_region_move_signature,
    _has_rest_submenu_signature,
    _has_reward_signature,
    _has_shop_signature,
    _has_training_hub_shop_signature,
    _has_training_select_signature,
)
from starsavior_trainer.models import (
    Action,
    BattleScene,
    BlessingChoice,
    BlessingSetup,
    CharacterSelect,
    CommissionChoice,
    ConfirmDialog,
    DialogueScene,
    EventFastForwardSetting,
    EventOption,
    JourneyStart,
    Rect,
    RelicChoice,
    RelicOption,
    RestSubmenu,
    Screen,
    ShopItem,
    ShopScene,
    SkillOption,
    TrainingChoice,
    TrainingHubStatus,
)
from starsavior_trainer.policy.engine import _is_iterable_of
from starsavior_trainer.screens.base import DelegatingScreenHandler
from starsavior_trainer.screens.battle import parse_battle
from starsavior_trainer.screens.blessing import parse_blessing_choice, parse_blessing_setup
from starsavior_trainer.screens.character_select import parse_character_select
from starsavior_trainer.screens.commission import parse_commission_select
from starsavior_trainer.screens.event import parse_event_choice
from starsavior_trainer.screens.region_move import parse_region_move
from starsavior_trainer.screens.relic import parse_relic_choice
from starsavior_trainer.screens.rest import parse_rest_submenu
from starsavior_trainer.screens.shop import parse_shop
from starsavior_trainer.screens.simple import (
    PostTrainingResult,
    parse_confirm_dialog,
    parse_dialogue_scene,
    parse_event_fast_forward_setting,
    parse_journey_start,
    parse_post_training,
    parse_skill_select,
    parse_training_direction,
)
from starsavior_trainer.screens.training import parse_training_hub, parse_training_select


# Decision functions — verbatim copies of the old TrainerPolicy.decide branches.
# Each takes (observation, state, policy) and stays behaviourally identical.

def _decide_initial(obs, state, policy):
    return Action("click", policy.config.start_button, "initial screen, click start")


def _decide_character_select(obs, state, policy):
    if not isinstance(obs.payload, CharacterSelect):
        return Action("pause", None, "character select screen missing character observation")
    return policy.decide_character_select(obs.payload, state)


def _decide_blessing_setup(obs, state, policy):
    if not isinstance(obs.payload, BlessingSetup):
        return Action("pause", None, "blessing setup screen missing setup observation")
    return policy.decide_blessing_setup(obs.payload)


def _decide_blessing_choice(obs, state, policy):
    if not isinstance(obs.payload, BlessingChoice):
        return Action("pause", None, "blessing choice screen missing options")
    return policy.decide_blessing_choice(obs.payload, state)


def _decide_journey_start(obs, state, policy):
    if not isinstance(obs.payload, JourneyStart):
        return Action("pause", None, "journey start screen missing start button")
    return policy.decide_journey_start(obs.payload)


def _decide_confirm_dialog(obs, state, policy):
    if not isinstance(obs.payload, ConfirmDialog):
        return Action("pause", None, "confirm dialog missing button observation")
    return policy.decide_confirm_dialog(obs.payload)


def _decide_event_fast_forward_setting(obs, state, policy):
    if not isinstance(obs.payload, EventFastForwardSetting):
        return Action("pause", None, "event fast-forward setting missing option observation")
    return policy.decide_event_fast_forward_setting(obs.payload)


def _decide_dialogue(obs, state, policy):
    if isinstance(obs.payload, DialogueScene):
        return policy.decide_dialogue(obs.payload)
    return Action("click", policy.config.skip_button, "dialogue screen, click skip", repeat=3)


def _decide_training_hub(obs, state, policy):
    if isinstance(obs.payload, TrainingHubStatus):
        # §22.3: 缓存心情(mood)+耐力(endurance_ratio), 供 REST_SUBMENU 的 decide_rest 用。
        if obs.payload.mood is not None:
            policy._cached_mood = obs.payload.mood
        policy._cached_endurance = obs.payload.endurance_ratio
        # D-DAY 评鉴战日: 大厅变成「评鉴战」+「交易」。先交易(打过评鉴战交易就消失)再评鉴战。
        # 评鉴战打完后按钮 OCR 可能仍命中"评鉴战"文字 → _dday_rating_done 防止反复点击。
        if obs.payload.rating_battle_button is not None:
            if not policy._dday_rating_done:
                if not policy._dday_trading_done and obs.payload.trading_button is not None:
                    return Action("click", obs.payload.trading_button, "D-DAY 大厅: 先去交易")
                policy._dday_rating_done = True
                return Action("click", obs.payload.rating_battle_button, "D-DAY 大厅: 去评鉴战")
            # 评鉴战已打过但 D-DAY 检测仍命中(OCR 误判/按钮未刷新) → fall through 走正常 hub 流程
        else:
            # 非 D-DAY → 清标志, 下次评鉴战日再逛。
            policy._dday_trading_done = False
            policy._dday_rating_done = False
        # 刚从 TRAINING_SELECT 全失败率退出 → 休息(否则 hub<->training_select 死循环)。
        if getattr(policy, "_needs_rest", False):
            policy._needs_rest = False
            if obs.payload.rest_button is not None:
                return Action("click", obs.payload.rest_button, "low stamina (all training too risky), rest")
        if obs.payload.has_commission_alert and obs.payload.commission_button is not None:
            return Action("click", obs.payload.commission_button, "training hub, commission alert")
        if obs.payload.has_shop_alert and obs.payload.shop_button is not None:
            return Action("click", obs.payload.shop_button, "training hub, shop alert")
        if obs.payload.training_button is not None:
            flash = "✨闪光训练" if obs.payload.has_flash_training else "普通训练"
            return Action("click", obs.payload.training_button, f"training hub, enter training ({flash})")
    return Action("click", policy.config.start_button, "training hub, click training")


def _decide_training_select(obs, state, policy):
    if not _is_iterable_of(obs.payload, TrainingChoice):
        return Action("pause", None, "training screen missing training choices")
    return policy.decide_training(obs.payload, state)


def _decide_rest_submenu(obs, state, policy):
    if not isinstance(obs.payload, RestSubmenu):
        return Action("pause", None, "rest screen missing submenu observation")
    return policy.decide_rest(obs.payload)


def _decide_event_choice(obs, state, policy):
    if not _is_iterable_of(obs.payload, EventOption):
        return Action("pause", None, "event screen missing options")
    return policy.decide_event(obs.payload, state)


def _decide_relic_choice(obs, state, policy):
    if isinstance(obs.payload, RelicChoice):
        return policy.decide_relic_choice(obs.payload, state)
    if not _is_iterable_of(obs.payload, RelicOption):
        # relic_choice 分类但 parse 不出选项 → 多半是被误判的奖励/结果展示。点屏幕中心推进。
        return Action("click", policy.config.screen_center, "relic screen no options, click center to advance")
    return policy.decide_relic(obs.payload)


def _decide_commission_select(obs, state, policy):
    if not isinstance(obs.payload, CommissionChoice):
        policy._pending_commission = None
        return Action("pause", None, "commission screen missing options")
    return policy.decide_commission(obs.payload, state)


def _decide_shop(obs, state, policy):
    # Fallback (blue mode / no inspector). The live loop normally drives shop via
    # ShopInspector; here we decide on whatever item effects we already have.
    if isinstance(obs.payload, ShopScene):
        return policy.decide_shop(obs.payload.items)
    if not _is_iterable_of(obs.payload, ShopItem):
        return Action("pause", None, "shop screen missing item list")
    return policy.decide_shop(obs.payload)


def _decide_battle(obs, state, policy):
    if isinstance(obs.payload, BattleScene):
        if obs.payload.confirm_active and obs.payload.confirm_button is not None:
            return Action("click", obs.payload.confirm_button, "battle, accept battle")
        return Action("click", obs.payload.skip_button, "battle, open battle entry")
    return Action("click", policy.config.skip_button, "battle, click default action")


def _decide_skill_select(obs, state, policy):
    # 坑 #35: 学最优技能(旧项目规则缺失, decide_skill 一直闲置)。有可学技能 → 按 build
    # profile 评分学最优(decide_skill 对已习得返回 -inf 自动跳过); 全部已习得/无可学 → 点
    # ✕ 退出, 不 pause 卡死技能界面(decide_skill 此情形返 pause, 这里转成 ✕ 退出)。
    if _is_iterable_of(obs.payload, SkillOption):
        action = policy.decide_skill(obs.payload, state)
        if action.kind == "click":
            return action
    return Action("click", policy.config.skill_select_close_button, "skill select: 无可学技能, 点 ✕ 退出")


def _decide_post_training(obs, state, policy):
    if isinstance(obs.payload, PostTrainingResult) and obs.payload.skip_button is not None:
        return Action("click", obs.payload.skip_button, "post-training, click skip")
    return Action("click", policy.config.skip_button, "post-training, click skip")


def _decide_region_move(obs, state, policy):
    if not isinstance(obs.payload, Rect):
        return Action("pause", None, "region move screen, no target parsed")
    return Action("click", obs.payload, "region move: 选目的地/前往")


def _decide_game_menu(obs, state, policy):
    # 误触菜单弹窗: 点 ✕ 关闭。绝不点中部 重新观测/观测结束(会重开/结束本局)。
    return Action(
        "click",
        policy.config.game_menu_close_button,
        "game menu popup, click ✕ to close (avoid centre 重新观测/观测结束)",
    )


def _decide_reward(obs, state, policy):
    # 获得奖励 popup: 中心遗物卡是死点击区, 只有"点击以继续"推进。
    return Action(
        "click",
        policy.config.reward_continue_button,
        "reward obtained (获得奖励), click 点击以继续 to advance",
    )


def _parse_event_choice_combined(region_texts, profile):
    direction = parse_training_direction(region_texts, profile)
    if direction is not None:
        return direction
    return parse_event_choice(region_texts, profile)


HANDLERS: dict[Screen, DelegatingScreenHandler] = {
    Screen.INITIAL: DelegatingScreenHandler(
        Screen.INITIAL, _decide_initial, priority=1,
        anchor_fn=_has_initial_signature, anchor_confidence=1.0,
        parse_fn=None, ocr_prefixes=None,
    ),
    Screen.POST_TRAINING: DelegatingScreenHandler(
        Screen.POST_TRAINING, _decide_post_training, priority=2,
        anchor_fn=_has_post_training_signature, anchor_confidence=1.0,
        parse_fn=parse_post_training, ocr_prefixes=["post_training"],
    ),
    Screen.EVENT_CHOICE: DelegatingScreenHandler(
        Screen.EVENT_CHOICE, _decide_event_choice, priority=3,
        anchor_fn=_has_event_choice_signature, anchor_confidence=1.0,
        parse_fn=_parse_event_choice_combined, ocr_prefixes=["event_choice", "training_direction"],
    ),
    Screen.DIALOGUE: DelegatingScreenHandler(
        Screen.DIALOGUE, _decide_dialogue, priority=4,
        anchor_fn=_has_dialogue_signature, anchor_confidence=1.0,
        parse_fn=parse_dialogue_scene, ocr_prefixes=["dialogue"],
    ),
    Screen.REST_SUBMENU: DelegatingScreenHandler(
        Screen.REST_SUBMENU, _decide_rest_submenu, priority=5,
        anchor_fn=_has_rest_submenu_signature, anchor_confidence=1.0,
        parse_fn=parse_rest_submenu, ocr_prefixes=["rest_submenu"],
    ),
    Screen.COMMISSION_SELECT: DelegatingScreenHandler(
        Screen.COMMISSION_SELECT, _decide_commission_select, priority=6,
        anchor_fn=_has_commission_select_signature, anchor_confidence=1.0,
        parse_fn=parse_commission_select, parse_needs_image=True, ocr_prefixes=["commission_select"],
    ),
    Screen.SHOP: DelegatingScreenHandler(
        Screen.SHOP, _decide_shop, priority=7,
        anchor_fn=_has_shop_signature, anchor_confidence=1.0,
        parse_fn=parse_shop, parse_needs_image=True, ocr_prefixes=["shop_item", "shop_detail", "shop_buy", "shop_back"],
    ),
    Screen.TRAINING_HUB: DelegatingScreenHandler(
        Screen.TRAINING_HUB, _decide_training_hub, priority=8,
        anchor_fn=_has_training_hub_shop_signature, anchor_confidence=1.0,
        parse_fn=parse_training_hub, parse_needs_image=True, ocr_prefixes=["training_hub"],
    ),
    Screen.TRAINING_SELECT: DelegatingScreenHandler(
        Screen.TRAINING_SELECT, _decide_training_select, priority=9,
        anchor_fn=_has_training_select_signature, anchor_confidence=0.90,
        parse_fn=parse_training_select, parse_needs_image=True, ocr_prefixes=["training_select"],
    ),
    # Screens resolved by the classifier's fallback anchor-text scoring (no signature).
    Screen.CHARACTER_SELECT: DelegatingScreenHandler(
        Screen.CHARACTER_SELECT, _decide_character_select,
        parse_fn=parse_character_select, ocr_prefixes=["character"],
    ),
    Screen.BLESSING_SETUP: DelegatingScreenHandler(
        Screen.BLESSING_SETUP, _decide_blessing_setup,
        parse_fn=parse_blessing_setup, parse_needs_image=True, ocr_prefixes=["blessing"],
    ),
    Screen.BLESSING_CHOICE: DelegatingScreenHandler(
        Screen.BLESSING_CHOICE, _decide_blessing_choice,
        parse_fn=parse_blessing_choice, parse_needs_image=True, ocr_prefixes=["blessing"],
    ),
    Screen.JOURNEY_START: DelegatingScreenHandler(
        Screen.JOURNEY_START, _decide_journey_start,
        parse_fn=parse_journey_start, ocr_prefixes=["journey_start"],
    ),
    Screen.CONFIRM_DIALOG: DelegatingScreenHandler(
        Screen.CONFIRM_DIALOG, _decide_confirm_dialog,
        parse_fn=parse_confirm_dialog, ocr_prefixes=["confirm_dialog"],
    ),
    Screen.EVENT_FAST_FORWARD_SETTING: DelegatingScreenHandler(
        Screen.EVENT_FAST_FORWARD_SETTING, _decide_event_fast_forward_setting,
        parse_fn=parse_event_fast_forward_setting, parse_needs_image=True,
        ocr_prefixes=["event_fast_forward"],
    ),
    Screen.RELIC_CHOICE: DelegatingScreenHandler(
        Screen.RELIC_CHOICE, _decide_relic_choice,
        parse_fn=parse_relic_choice, parse_needs_image=True, ocr_prefixes=["relic_choice"],
    ),
    Screen.BATTLE: DelegatingScreenHandler(
        Screen.BATTLE, _decide_battle, priority=10,
        anchor_fn=_has_battle_signature, anchor_confidence=1.0,
        parse_fn=parse_battle, parse_needs_image=True, ocr_prefixes=["battle"],
    ),
    Screen.SKILL_SELECT: DelegatingScreenHandler(
        Screen.SKILL_SELECT, _decide_skill_select,
        parse_fn=parse_skill_select, ocr_prefixes=["skill_select"],
    ),
    Screen.REGION_MOVE: DelegatingScreenHandler(
        Screen.REGION_MOVE, _decide_region_move, priority=6,
        anchor_fn=_has_region_move_signature, anchor_confidence=1.0,
        parse_fn=parse_region_move, ocr_prefixes=["region_move"],
    ),
    # 获得奖励 reward popup. priority=2 早检查, 避免角色选择 fallback 误判(坑 #9)。
    Screen.REWARD: DelegatingScreenHandler(
        Screen.REWARD, _decide_reward, priority=2,
        anchor_fn=_has_reward_signature, anchor_confidence=1.0,
        parse_fn=None, ocr_prefixes=None,
    ),
    # 误触菜单弹窗. priority=2 早检查(坑 #10), 绝不点中部 重新观测/观测结束。
    Screen.GAME_MENU: DelegatingScreenHandler(
        Screen.GAME_MENU, _decide_game_menu, priority=2,
        anchor_fn=_has_game_menu_signature, anchor_confidence=1.0,
        parse_fn=None, ocr_prefixes=None,
    ),
}

ANCHOR_HANDLERS: list[DelegatingScreenHandler] = []
"""按 priority 升序、仅含 anchor_fn 的 handler 列表。classifier 锚点匹配按此顺序检查。"""


def rebuild_anchor_handlers() -> None:
    """按 priority 升序重建 ANCHOR_HANDLERS(仅含带 anchor_fn 的 handler)。

    原地替换内容(而非 reassign)以保持对象身份, 让 `from ... import ANCHOR_HANDLERS`
    的引用在 rebuild 后仍指向同一(已更新)对象。
    """
    ANCHOR_HANDLERS[:] = sorted(
        (h for h in HANDLERS.values() if h._anchor_fn is not None),
        key=lambda h: h.priority,
    )


# 模块加载时构建初始 ANCHOR_HANDLERS（handler 已全部注册 above）。
rebuild_anchor_handlers()
