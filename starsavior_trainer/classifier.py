"""画面分类器核心 — classify_by_ocr(两遍加速)/classify_by_blue_button/classify_hybrid(实跑默认)。

重构自 classifier.py §5（行 1-298）。anchor 常量 + _match_screen 在 classifier_anchors;
消歧 signature + 密度 helper 在 classifier_signatures。坑台账 A 类(1-11)规避。
"""
from __future__ import annotations

from PIL import Image

from starsavior_trainer.classifier_anchors import (
    _match_screen,
    _read_anchor_regions,
    classify_by_filename,
)
from starsavior_trainer.classifier_signatures import (
    _has_blessing_choice_visual_signature,
    _region_content_density,
    classify_journey_origin_by_visual,
)
from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import Observation, Screen
from starsavior_trainer.ocr import OcrEngine
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.vision import BlueButtonDetector

logger = get_logger("classifier")

# Small title/marker anchors that identify most screens on their own. OCR'ing
# only these first avoids reading all ~54 anchor regions every frame (the dominant
# per-iteration cost ~5-6s). The full sweep runs only as a fallback.
_FAST_ANCHORS: tuple[str, ...] = (
    "route_select_anchor_title",
    "character_select_anchor_title",
    "blessing_setup_anchor_title",
    "blessing_choice_anchor_archive",
    "journey_start_anchor_title",
    "confirm_dialog_title",
    "event_fast_forward_title",
    "training_hub_anchor_title",
    "training_select_anchor_title",
    "training_select_card_power", "training_select_card_stamina",
    "training_select_card_guts", "training_select_card_wisdom", "training_select_card_speed",
    "event_choice_title",
    "relic_choice_title",
    "commission_select_anchor_title",
    "skill_select_title",
    "post_training_title",
    "dialogue_journey_title",
    "dialogue_intro_skip_button",
    "reward_title",
    "game_menu_anchor_title",
    "game_menu_observe_marker",
    "region_move_anchor_title",
    "region_move_station_title",
)


def classify_by_ocr(
    image: Image.Image,
    profile: RegionProfile,
    ocr_or_reader,
    min_confidence: float = 0.70,
) -> Observation:
    """Classify the current screen by reading OCR anchor regions.

    Two-pass for speed: first OCR only the small title/marker anchors and match;
    only if that yields no confident match do we OCR the full anchor set.
    两遍共用同一 reader(全图 read_lines 缓存),故实际只 OCR 一次。
    """
    reader = ocr_or_reader if isinstance(ocr_or_reader, RegionOcrReader) else RegionOcrReader(profile, ocr_or_reader)
    fast_anchors = _read_anchor_regions(reader, image, names=_FAST_ANCHORS)
    best_screen, best_confidence = _match_screen(fast_anchors)
    if best_confidence >= min_confidence:
        return Observation(screen=best_screen, confidence=best_confidence)

    anchors = _read_anchor_regions(reader, image)
    if not anchors:
        return Observation(screen=Screen.UNKNOWN, confidence=0.0)
    best_screen, best_confidence = _match_screen(anchors)
    if best_confidence < min_confidence:
        return Observation(screen=Screen.UNKNOWN, confidence=best_confidence)
    return Observation(screen=best_screen, confidence=best_confidence)


# ---------------------------------------------------------------------------
# Blue-button-based classification (no OCR)
# ---------------------------------------------------------------------------

UNIQUE_BLUE_BUTTONS: dict[str, Screen] = {
    "confirm_dialog_confirm_button": Screen.CONFIRM_DIALOG,
    "event_fast_forward_confirm_button": Screen.EVENT_FAST_FORWARD_SETTING,
    "relic_choice_confirm_button": Screen.RELIC_CHOICE,
    "battle_accept_button": Screen.BATTLE,
    "training_hub_action_training": Screen.TRAINING_HUB,
    "region_move_button": Screen.REGION_MOVE,
    "blessing_choice_confirm_button": Screen.BLESSING_CHOICE,
    "journey_start_button": Screen.JOURNEY_START,
}

_BOTTOM_RIGHT_BUTTONS: list[tuple[str, Screen]] = [
    ("start_button", Screen.INITIAL),
    ("character_select_button", Screen.CHARACTER_SELECT),
    ("blessing_confirm_button", Screen.BLESSING_SETUP),
    ("training_select_confirm_button", Screen.TRAINING_SELECT),
]

_SECONDARY_CHECK_REGIONS: dict[Screen, list[str]] = {
    Screen.TRAINING_SELECT: [
        "training_select_card_power",
        "training_select_card_stamina",
        "training_select_card_guts",
    ],
    Screen.CHARACTER_SELECT: [
        "character_option_1",
        "character_option_2",
        "character_option_3",
    ],
    Screen.BLESSING_SETUP: [
        "blessing_slot_1",
        "blessing_slot_2",
    ],
}


def classify_by_blue_button(
    image: Image.Image,
    profile: RegionProfile,
    min_confidence: float = 0.60,
) -> Observation:
    """Classify by detecting blue buttons at known positions (no OCR)."""
    detector = BlueButtonDetector()

    for region_name, screen in UNIQUE_BLUE_BUTTONS.items():
        rect = profile.regions.get(region_name)
        if rect is None:
            continue
        try:
            signal = detector.detect(crop_region(image, rect))
            if signal.name == "active_blue" and signal.confidence >= min_confidence:
                return Observation(screen=screen, confidence=signal.confidence)
        except Exception as e:
            logger.debug(f"[classify_by_blue_button] blue detect failed on {region_name}: {e}")
            continue

    br_result = _classify_bottom_right_group(image, profile, detector, min_confidence)
    if br_result is not None:
        return br_result

    return Observation(screen=Screen.UNKNOWN, confidence=0.0)


def _classify_bottom_right_group(
    image: Image.Image,
    profile: RegionProfile,
    detector: BlueButtonDetector,
    min_confidence: float,
) -> Observation | None:
    """Disambiguate the bottom-right blue-button group using secondary region checks."""
    active_screens: list[Screen] = []
    for region_name, screen in _BOTTOM_RIGHT_BUTTONS:
        rect = profile.regions.get(region_name)
        if rect is None:
            continue
        try:
            signal = detector.detect(crop_region(image, rect))
            if signal.name == "active_blue":
                active_screens.append(screen)
        except Exception as e:
            logger.debug(f"[_classify_bottom_right_group] blue detect failed on {region_name}: {e}")
            continue

    if not active_screens:
        return None

    scores: dict[Screen, float] = {}
    for screen in active_screens:
        secondary_regions = _SECONDARY_CHECK_REGIONS.get(screen, [])
        if not secondary_regions:
            scores[screen] = 0.3
            continue
        densities = []
        for name in secondary_regions:
            rect = profile.regions.get(name)
            if rect is not None:
                densities.append(_region_content_density(crop_region(image, rect)))
        scores[screen] = max(densities) if densities else 0.3

    best_screen = max(scores, key=lambda s: scores[s])
    return Observation(screen=best_screen, confidence=min(scores[best_screen], 1.0))


def classify_hybrid(
    image: Image.Image,
    profile: RegionProfile,
    ocr,
    blue_min_confidence: float = 0.60,
    ocr_min_confidence: float = 0.70,
) -> Observation:
    """Classify with OCR first, fallback to blue-button detection (实跑默认).

    ocr 可传 OcrEngine 或 RegionOcrReader(后者让 classify 与 payload parse 共享
    一次全图 read_lines, 一帧只 OCR 一次)。
    """
    reader = ocr if isinstance(ocr, RegionOcrReader) else RegionOcrReader(profile, ocr)
    engine = reader.ocr
    ocr_result = classify_by_ocr(image, profile, reader, ocr_min_confidence)

    # Journey DIALOGUE shares "旅程事件" title with EVENT_CHOICE (坑 #2): if no real
    # option rows, it's a skippable dialogue.
    if ocr_result.screen == Screen.EVENT_CHOICE and not _has_real_event_options(image, profile, engine):
        return Observation(screen=Screen.DIALOGUE, confidence=max(ocr_result.confidence, 0.90))
    # BLESSING_CHOICE shares "旅程起点" with journey-origin group (坑 #11): visual sig
    # disambiguates, gated on ambiguity so it doesn't misfire on INITIAL etc.
    _BLESSING_AMBIGUOUS = (
        Screen.UNKNOWN,
        Screen.CHARACTER_SELECT,
        Screen.BLESSING_SETUP,
        Screen.JOURNEY_START,
        Screen.BLESSING_CHOICE,
    )
    if ocr_result.screen in _BLESSING_AMBIGUOUS and _has_blessing_choice_visual_signature(image, profile):
        return Observation(screen=Screen.BLESSING_CHOICE, confidence=max(ocr_result.confidence, 0.95))
    if ocr_result.screen != Screen.UNKNOWN:
        if ocr_result.screen in (Screen.CHARACTER_SELECT, Screen.BLESSING_SETUP):
            visual_screen = classify_journey_origin_by_visual(image, profile)
            resolved = visual_screen if visual_screen is not None else ocr_result.screen
            # character_select & journey_start share "旅程起点" title (坑 #1): tell apart
            # by the bottom button ("选择" vs "旅程起点").
            if resolved == Screen.CHARACTER_SELECT and _looks_like_journey_start(image, profile, engine):
                return Observation(screen=Screen.JOURNEY_START, confidence=max(ocr_result.confidence, 0.90))
            return Observation(screen=resolved, confidence=max(ocr_result.confidence, 0.90))
        return ocr_result

    blue_result = classify_by_blue_button(image, profile, blue_min_confidence)
    if blue_result.screen != Screen.UNKNOWN:
        return blue_result

    return ocr_result


def _has_real_event_options(image: Image.Image, profile: RegionProfile, ocr: OcrEngine) -> bool:
    """True if the screen has actual selectable event-choice option rows (坑 #2).

    Options are bottom-aligned; option_3/4 filled on every real event while
    option_1 is usually empty — scan options 2-4 (skipping dead option_1).
    """
    for index in range(2, 5):
        rect = profile.regions.get(f"event_choice_option_{index}")
        if rect is None:
            continue
        try:
            text = ocr.read_text(crop_region(image, rect)).text.strip()
        except Exception as e:
            logger.debug(f"[_has_real_event_options] OCR failed on option {index}: {e}")
            continue
        if len(text) >= 2:
            return True
    return False


def _looks_like_journey_start(image: Image.Image, profile: RegionProfile, ocr: OcrEngine) -> bool:
    """Distinguish journey_start from character_select (shared 旅程起点 title, 坑 #1).

    character_select's button reads 选择; journey_start's reads 旅程起点.
    """
    rect = profile.regions.get("journey_start_button")
    if rect is None:
        return False
    text = ocr.read_text(crop_region(image, rect)).text
    if "选择" in text:
        return False
    return ("旅程" in text) or ("起点" in text) or ("自动" in text)
