"""画面 anchor 区域/文本常量 + _match_screen 注册表分发 + classify_by_filename 离线分类。

重构自 classifier.py §5（行 301-511）。_match_screen 先走 ANCHOR_HANDLERS 签名检查,
再 fallback anchor 文本评分。classify_by_filename 供离线截图按文件名分类。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import Observation, Screen
from starsavior_trainer.ocr import OcrEngine
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text

logger = get_logger("classifier")


def classify_by_filename(path: str | Path) -> Observation:
    """Temporary classifier for offline screenshots (named with a screen state)."""
    name = Path(path).stem.lower()
    if "route_select" in name or "journey_select" in name:
        return Observation(screen=Screen.INITIAL, confidence=0.80, source=str(path))
    if "character_select" in name or "select_character" in name or "runner_select" in name:
        return Observation(screen=Screen.CHARACTER_SELECT, confidence=0.80, source=str(path))
    if "blessing_setup" in name or "blessing_equip" in name:
        return Observation(screen=Screen.BLESSING_SETUP, confidence=0.80, source=str(path))
    if "blessing_choice" in name or "select_blessing" in name:
        return Observation(screen=Screen.BLESSING_CHOICE, confidence=0.80, source=str(path))
    if "journey_start" in name or "journey_origin" in name or "arcana" in name:
        return Observation(screen=Screen.JOURNEY_START, confidence=0.80, source=str(path))
    if "confirm_dialog" in name or "entry_confirm" in name:
        return Observation(screen=Screen.CONFIRM_DIALOG, confidence=0.80, source=str(path))
    if "event_fast_forward" in name or "fast_forward_setting" in name:
        return Observation(screen=Screen.EVENT_FAST_FORWARD_SETTING, confidence=0.80, source=str(path))
    if "dialogue_intro" in name or "story_skip" in name or "journey_dialogue" in name:
        return Observation(screen=Screen.DIALOGUE, confidence=0.80, source=str(path))
    if "training_hub" in name or "training_main" in name or "action_hub" in name:
        return Observation(screen=Screen.TRAINING_HUB, confidence=0.80, source=str(path))
    if "training_select" in name and "training_hub" not in name:
        return Observation(screen=Screen.TRAINING_SELECT, confidence=0.80, source=str(path))
    if "training_direction" in name:
        return Observation(screen=Screen.EVENT_CHOICE, confidence=0.80, source=str(path))
    if "post_training" in name:
        return Observation(screen=Screen.POST_TRAINING, confidence=0.80, source=str(path))
    if "battle" in name or "评鉴战" in name or "skip_battle" in name:
        return Observation(screen=Screen.BATTLE, confidence=0.80, source=str(path))
    if "skill" in name or "技能" in name or "潜质" in name:
        return Observation(screen=Screen.SKILL_SELECT, confidence=0.80, source=str(path))
    for screen in Screen:
        if screen != Screen.UNKNOWN and screen.value in name:
            return Observation(screen=screen, confidence=0.80, source=str(path))
    return Observation(screen=Screen.UNKNOWN, confidence=0.0, source=str(path))


# ---- OCR-based anchor matching ----

ANCHOR_REGIONS_BY_SCREEN: dict[Screen, list[str]] = {
    Screen.INITIAL: ["route_select_anchor_title", "route_select_route_title", "start_button"],
    Screen.CHARACTER_SELECT: ["character_select_anchor_title"],
    Screen.BLESSING_SETUP: ["blessing_setup_anchor_title"],
    Screen.BLESSING_CHOICE: ["blessing_choice_anchor_archive"],
    Screen.JOURNEY_START: ["journey_start_anchor_title"],
    Screen.CONFIRM_DIALOG: ["confirm_dialog_title"],
    Screen.EVENT_FAST_FORWARD_SETTING: ["event_fast_forward_title"],
    Screen.DIALOGUE: [
        "dialogue_intro_skip_button",
        "dialogue_journey_title",
        "dialogue_journey_event_label",
        "dialogue_journey_text_area",
    ],
    Screen.TRAINING_HUB: [
        "training_hub_anchor_title",
        "training_hub_distance",
        "training_hub_action_training",
        "training_hub_action_commission",
        "training_hub_action_shop",
        "training_hub_action_rest",
        "training_hub_shop_alert",
        "training_hub_nav_potential",
    ],
    Screen.TRAINING_SELECT: [
        "training_select_anchor_title",
        "training_select_card_power",
        "training_select_card_stamina",
        "training_select_card_guts",
        "training_select_card_wisdom",
        "training_select_card_speed",
    ],
    Screen.REST_SUBMENU: ["rest_submenu_option_1", "rest_submenu_option_2", "rest_submenu_option_3"],
    Screen.EVENT_CHOICE: [
        "event_choice_title",
        "event_choice_option_1",
        "event_choice_option_2",
        "event_choice_option_3",
        "event_choice_option_4",
    ],
    Screen.RELIC_CHOICE: ["relic_choice_title"],
    Screen.REWARD: ["reward_title"],
    Screen.GOAL_DIALOG: ["goal_dialog_anchor_title"],
    Screen.COMMISSION_SELECT: [
        "commission_select_anchor_title",
        "commission_select_option_1_name",
        "commission_select_option_2_name",
        "commission_select_option_3_name",
        "commission_select_accept_button",
    ],
    Screen.SHOP: [
        "shop_refresh_button",
        "shop_buy_button",
        "shop_detail_effect",
        "shop_item_1_name",
        "shop_item_2_name",
        "shop_item_3_name",
        "shop_item_1_price",
        "shop_item_2_price",
        "shop_item_3_price",
    ],
    Screen.BATTLE: [
        "battle_skip_button",
        "battle_title",
        "battle_entry_button",
        "battle_accept_button",
        "battle_skip_battle_button",
        "battle_confirm_title",
    ],
    Screen.SKILL_SELECT: ["skill_select_title"],
    Screen.POST_TRAINING: [
        "post_training_result_text",
        "post_training_title",
        "post_training_success_text",
        "post_training_event_title",
    ],
    Screen.REGION_MOVE: ["region_move_button"],
}

ANCHOR_TEXT_BY_SCREEN: dict[Screen, tuple[str, ...]] = {
    Screen.INITIAL: ("选择旅程", "星光引导者", "starsavior", "开始"),
    Screen.CHARACTER_SELECT: ("旅程起点",),
    Screen.BLESSING_SETUP: ("旅程起点",),
    Screen.BLESSING_CHOICE: ("星辰档案",),
    Screen.JOURNEY_START: ("旅程起点",),
    Screen.CONFIRM_DIALOG: ("入场确认",),
    Screen.EVENT_FAST_FORWARD_SETTING: ("事件快转设定",),
    Screen.DIALOGUE: ("skip", "跳过", "旅程事件"),
    Screen.TRAINING_HUB: ("距离目标", "训练", "委托", "交易", "休息", "潜质", "商品"),
    Screen.TRAINING_SELECT: ("力量训练", "体力训练", "韧性训练", "集中训练"),
    Screen.REST_SUBMENU: ("露宿", "冥想"),
    Screen.EVENT_CHOICE: ("旅程事件", "事件"),
    Screen.RELIC_CHOICE: ("选择奖励",),
    Screen.REWARD: ("获得奖励",),
    Screen.GOAL_DIALOG: ("旅程信息", "目标"),
    Screen.COMMISSION_SELECT: ("委托",),
    Screen.SHOP: ("购买",),
    Screen.BATTLE: ("跳过战斗", "评鉴战", "战斗", "接受"),
    Screen.SKILL_SELECT: ("潜质", "技能", "学习"),
    Screen.POST_TRAINING: ("提升", "事件", "+"),
    Screen.REGION_MOVE: ("移动",),
}


def _read_anchor_regions(
    reader,
    image: Image.Image,
    names: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """读 anchor 区域文字。走 reader 的全图 OCR 缓存(read_lines 一次), 一帧内 classify
    的 fast/full 两遍 + payload parse 共享同一次 read_lines —— 提速关键(原逐区域 OCR)。
    """
    if names is None:
        all_anchor_names: set[str] = set()
        for region_names in ANCHOR_REGIONS_BY_SCREEN.values():
            all_anchor_names.update(region_names)
        names = tuple(all_anchor_names)
    return {rt.name: rt.text for rt in reader.read_names(image, names) if rt.text}


def _match_screen(anchors: dict[str, str]) -> tuple[Screen, float]:
    # Ordered signature checks dispatch through the screen registry. ANCHOR_HANDLERS
    # is sorted by priority to reproduce the exact original order. Imported lazily
    # to avoid an import cycle (screens/__init__ imports this module's signatures).
    from starsavior_trainer.screens import ANCHOR_HANDLERS

    for handler in ANCHOR_HANDLERS:
        matched, confidence = handler.has_anchor(anchors)
        if matched:
            return handler.screen, confidence

    best_screen = Screen.UNKNOWN
    best_score = 0.0

    for screen, region_names in ANCHOR_REGIONS_BY_SCREEN.items():
        expected_texts = ANCHOR_TEXT_BY_SCREEN.get(screen, ())
        if not expected_texts:
            continue

        match_count = 0
        seen_regions = 0
        for name in region_names:
            text = anchors.get(name, "")
            if text.strip():
                seen_regions += 1
            if text.strip() and contains_any_text(text, expected_texts):
                match_count += 1

        if seen_regions > 0 and match_count > 0:
            score = match_count / seen_regions
            if score > best_score:
                best_score = score
                best_screen = screen

    return best_screen, min(best_score, 1.0)
