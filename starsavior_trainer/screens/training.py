"""训练画面 parser — 训练大厅 hub + 训练选择 select。

重构自 screen_reader.py §5（行 838-1031）。hub 含 D-DAY 评鉴战日分支(评鉴战/交易按钮取代
训练/委托/休息); select 的失败率只在选中卡显示, 未显示=None(坑 #24: 绝不当 0% 赌博)。
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import TrainingChoice, TrainingHubStatus
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_constants import TRAINING_NAME_ALIASES
from starsavior_trainer.text_utils import (
    _ocr_int_token_to_int,
    _or_none,
    contains_any_text,
    normalize_ocr_text,
    parse_first_int,
)
from starsavior_trainer.vision import (
    RingColorDetector,
    detect_flash_card,
    detect_flash_training,
    detect_red_text,
    detect_yellow_text,
    estimate_endurance_ratio,
)

logger = get_logger("screens.training")


def parse_training_hub(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> TrainingHubStatus | None:
    """Recognize the training hub screen and extract status information."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_training_hub_anchor(texts, profile):
        return None

    turn_label = _or_none(texts.get("training_hub_turn_label"))
    rank_label = _or_none(texts.get("training_hub_rank_label"))
    coins = parse_first_int(texts.get("training_hub_coin_count", ""))
    potential_points = parse_first_int(texts.get("training_hub_potential_points", ""))
    alert_text = texts.get("training_hub_commission_alert", "")
    has_commission_alert = contains_any_text(alert_text, ("受理", "讨伐", "委托", "commission"))
    alert_rect = profile.regions.get("training_hub_commission_alert")
    if not has_commission_alert and alert_rect is not None and image is not None:
        has_commission_alert = detect_red_text(crop_region(image, alert_rect))
    shop_alert_text = texts.get("training_hub_shop_alert", "")
    has_shop_alert = contains_any_text(shop_alert_text, ("商品", "到货", "交易", "shop"))
    shop_alert_rect = profile.regions.get("training_hub_shop_alert")
    if not has_shop_alert and shop_alert_rect is not None and image is not None:
        has_shop_alert = detect_yellow_text(crop_region(image, shop_alert_rect))
    can_learn_skill = contains_any_text(
        texts.get("training_hub_skill_available", ""),
        ("可获得", "习得", "learn"),
    )

    # D-DAY (评鉴战日) hub: the right column swaps 训练/委托/休息 for 评鉴战(top) +
    # 交易(bottom). When those buttons OCR there, surface both so the policy goes
    # 交易 first (打过评鉴战交易就消失), then 评鉴战. Detection keys off the button
    # text so a normal hub (训练/休息 there) leaves these None.
    is_dday = contains_any_text(
        texts.get("training_hub_rating_battle", ""), ("评鉴战", "鉴战")
    ) or contains_any_text(texts.get("training_hub_trading", ""), ("交易",))
    rating_battle_button = profile.regions.get("training_hub_rating_battle") if is_dday else None
    trading_button = profile.regions.get("training_hub_trading") if is_dday else None

    endurance_ratio = 0.0
    endurance_rect = profile.regions.get("training_hub_endurance_bar")
    if endurance_rect is not None and image is not None:
        endurance_ratio = estimate_endurance_ratio(image, endurance_rect)
    mood = _parse_mood(texts.get("training_hub_mood_label", ""))
    has_flash_training = False
    training_btn = profile.regions.get("training_hub_action_training")
    if training_btn is not None and image is not None:
        has_flash_training = detect_flash_training(image, training_btn)
    flash_tag = "✨闪光训练 " if has_flash_training else ""
    logger.info(f"训练大厅: {flash_tag}耐力 {endurance_ratio:.0%}, 心情 {mood or '未知'}")

    return TrainingHubStatus(
        turn_label=turn_label,
        coins=coins,
        rank_label=rank_label,
        potential_points=potential_points,
        training_button=profile.regions.get("training_hub_action_training"),
        commission_button=profile.regions.get("training_hub_action_commission"),
        rest_button=profile.regions.get("training_hub_action_rest"),
        skill_button=profile.regions.get("training_hub_nav_potential"),
        shop_button=profile.regions.get("training_hub_action_shop"),
        goal_button=profile.regions.get("goal_button"),
        has_commission_alert=has_commission_alert,
        has_shop_alert=has_shop_alert,
        can_learn_skill=can_learn_skill,
        rating_battle_button=rating_battle_button,
        trading_button=trading_button,
        endurance_ratio=endurance_ratio,
        mood=mood,
        has_flash_training=has_flash_training,
    )


def _parse_mood(text: str) -> str | None:
    """心情等级 OCR 容错匹配: BEST > GOOD > NORMAL; None = 未识别。详见 §22.3。"""
    t = normalize_ocr_text(text).upper()
    if not t:
        return None
    if "BEST" in t or "BES" in t or "BST" in t:
        return "BEST"
    if "GOOD" in t or "GOO" in t:
        return "GOOD"
    if "NORMAL" in t or "NORM" in t or "NOR" in t:
        return "NORMAL"
    return None


def _has_training_hub_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    training_btn = profile.regions.get("training_hub_action_training")
    commission_btn = profile.regions.get("training_hub_action_commission")
    rest_btn = profile.regions.get("training_hub_action_rest")
    if training_btn is None or commission_btn is None or rest_btn is None:
        return False
    title = texts.get("training_hub_anchor_title", "")
    distance = texts.get("training_hub_distance", "")
    turn = texts.get("training_hub_turn_label", "")
    actions = " ".join(
        texts.get(name, "")
        for name in (
            "training_hub_action_training",
            "training_hub_action_commission",
            "training_hub_action_shop",
            "training_hub_action_rest",
            "training_hub_nav_potential",
        )
    )
    return contains_any_text(
        title + distance + turn + actions,
        (
            "距离目标",
            "参加",
            "旅程",
            "训练",
            "委托",
            "交易",
            "休息",
            "潜质",
        ),
    )


# ---------------------------------------------------------------------------
# Training Select parser
# ---------------------------------------------------------------------------

TRAINING_CARD_ATTRIBUTES = ("power", "stamina", "guts", "wisdom", "speed")


def parse_training_select(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> list[TrainingChoice] | None:
    """Read the five training options from the training-select screen."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_training_select_anchor(texts, profile):
        return None

    confirm_button = profile.regions.get("training_select_confirm_button")
    back_button = profile.regions.get("top_back_button")

    # §22.1: SELECT 顶部 HUD 也有耐力条(同坐标)，读当前耐力(绿前缀；灰=训练消耗预览不判)。
    endurance_ratio = 0.0
    endurance_rect = profile.regions.get("training_select_endurance_bar")
    if endurance_rect is not None and image is not None:
        endurance_ratio = estimate_endurance_ratio(image, endurance_rect)

    choices: list[TrainingChoice] = []
    for attr in TRAINING_CARD_ATTRIBUTES:
        card_rect = profile.regions.get(f"training_select_card_{attr}")
        if card_rect is None:
            continue

        card_text = texts.get(f"training_select_card_{attr}", "")
        name_text = texts.get(f"training_select_card_{attr}_name", "")
        fail_text = texts.get(f"training_select_card_{attr}_fail_rate", "")
        gain_text = texts.get(f"training_select_stat_gain_{attr}", "")

        recognized_name = _match_training_name(name_text) or _match_training_name(card_text) or attr
        # Fail rate must be a percentage; never fall back to a bare integer so
        # decorative digits inside the card box are not mistaken for a fail rate.
        card_fail = _parse_fail_rate(fail_text)
        if card_fail is None:
            card_fail = _parse_fail_rate(card_text)
        # The failure rate is only rendered on the currently highlighted card, so
        # its presence is a reliable "this card is selected" signal. When it is NOT
        # shown the rate is UNKNOWN (None), never 0 — a 0 here would read as "safe 0%"
        # and let the policy gamble on an un-inspected, possibly ~99%-fail card.
        selected = card_fail is not None
        fail_rate = card_fail
        stat_gain = parse_first_int(gain_text) or 0

        ring = "none"
        is_flash = False
        if image is not None:
            ring_rect = profile.regions.get("training_select_ring_detect")
            if ring_rect is not None:
                ring_signal = RingColorDetector().detect(crop_region(image, ring_rect))
                ring = ring_signal.name
            is_flash = detect_flash_card(image, card_rect)

        choices.append(
            TrainingChoice(
                name=recognized_name,
                stat_gain=stat_gain,
                ring=ring,
                fail_rate=fail_rate,
                target=card_rect,
                selected=selected,
                confirm_button=confirm_button,
                back_button=back_button,
                endurance_ratio=endurance_ratio,
                is_flash=is_flash,
            )
        )

    if not choices:
        return None
    return choices


def _has_training_select_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    confirm = profile.regions.get("training_select_confirm_button")
    if confirm is None:
        return False
    for attr in TRAINING_CARD_ATTRIBUTES:
        name_text = texts.get(f"training_select_card_{attr}_name", "") or texts.get(f"training_select_card_{attr}", "")
        if _match_training_name(name_text) is not None:
            return True
    return False


def _match_training_name(text: str) -> str | None:
    for name, aliases in TRAINING_NAME_ALIASES.items():
        if contains_any_text(text, aliases):
            return name
    return None


def _parse_fail_rate(text: str) -> int | None:
    """Parse a failure-rate percentage, requiring an explicit '%' sign.

    Unlike parse_percent, this never falls back to a bare integer, so decorative
    digits or icon glyphs inside a training card are not read as a fail rate.
    """
    if not text or not text.strip():
        return None
    normalized = normalize_ocr_text(text)
    match = re.search(r"([0-9olis][0-9olis,]*)\s*%", normalized)
    if match is None:
        return None
    return _ocr_int_token_to_int(match.group(1))
