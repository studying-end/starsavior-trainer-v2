"""画面 payload 读取 — OCR 模式（走 HANDLERS 注册表）+ blue 模式（纯颜色，无 OCR）。

迁自旧 cli/live_loop.py（525-866）。OCR 模式 dispatch 走 screens.HANDLERS（架构契约：
payload 读取统一走注册表）；blue 模式用本地 builder 表（_BLUE_PARSERS），仅靠颜色检测
构造 payload。CHARACTER_SELECT 因滚动半行偏移，固定行 OCR 失效，改用 bbox 定位。
"""
from __future__ import annotations

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import (
    CommissionChoice,
    CommissionOption,
    DialogueScene,
    EventOption,
    Rect,
    RelicChoice,
    RelicOption,
    RestSubmenu,
    Screen,
    TrainingChoice,
    TrainingHubStatus,
)
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens import HANDLERS
from starsavior_trainer.screens.battle import parse_battle
from starsavior_trainer.screens.character_select import parse_character_select_bbox
from starsavior_trainer.vision import (
    BlueButtonDetector,
    RingColorDetector,
    detect_red_text,
    detect_yellow_text,
)

logger = get_logger("blue_parsers")


# ---------------------------------------------------------------------------
# OCR-mode screen reading (existing logic)
# ---------------------------------------------------------------------------


def _read_screen_payload_ocr(
    screen: Screen,
    image,
    profile: RegionProfile,
    reader: RegionOcrReader,
    verbose: bool,
) -> object | None:
    # Dispatch through the screen registry: each handler declares which region
    # prefixes to OCR and how to parse them, replacing the old per-screen if/elif.
    # Character select scrolls by dragging to arbitrary (half-row) offsets, so
    # fixed-row OCR fails. Locate names by OCR bounding box instead.
    if screen == Screen.CHARACTER_SELECT:
        payload = parse_character_select_bbox(image, profile, reader.ocr)
        if verbose and payload is not None:
            print(f"  bbox names: {[o.name for o in payload.options if o.name != payload.selected_name]}")
        return payload

    handler = HANDLERS.get(screen)
    if handler is None or handler.ocr_prefixes is None:
        return None

    region_texts = reader.read_prefixes(image, handler.ocr_prefixes, max_area=160000)
    if verbose:
        for rt in region_texts:
            print(f"  ocr {rt.name}: '{rt.text}' ({rt.confidence:.2f})")

    return handler.parse(region_texts, profile, image)


# ---------------------------------------------------------------------------
# Blue-mode screen reading (color-only, no OCR)
# ---------------------------------------------------------------------------


def _read_screen_payload_blue(
    screen: Screen,
    image,
    profile: RegionProfile,
    detector: BlueButtonDetector,
    verbose: bool,
) -> object | None:
    """Build screen payloads using only color detection — no OCR.

    For simple screens the policy just clicks a known button — no payload needed.
    For complex screens we use color-based heuristics (ring detection, red text, etc).
    """
    # Dispatch through a local builder table instead of a per-screen if/elif.
    # (Blue builders live in this module; they stay local for now and move into
    # the screen handlers during the deferred physical migration — see REFACTOR.md.)
    builder = _BLUE_PARSERS.get(screen)
    if builder is None:
        # Simple screens: INITIAL, CHARACTER_SELECT, BLESSING_SETUP, BLESSING_CHOICE,
        # JOURNEY_START, CONFIRM_DIALOG, EVENT_FAST_FORWARD_SETTING, REGION_MOVE —
        # policy clicks a hardcoded button; no payload needed.
        return None
    return builder(image, profile, detector, verbose)


def _shop_blue(image, profile, detector, verbose):
    # Shop needs item names/prices — skip without OCR.
    if verbose:
        print("  shop: skipping (no OCR, can't read items)")
    return None


def _training_hub_blue(image, profile: RegionProfile) -> TrainingHubStatus:
    """Minimal TrainingHubStatus — policy clicks the training button."""
    has_commission_alert = False
    has_shop_alert = False
    alert_rect = profile.regions.get("training_hub_commission_alert")
    if alert_rect is not None:
        try:
            has_commission_alert = detect_red_text(crop_region(image, alert_rect))
        except Exception as e:
            logger.debug(f"[_training_hub_blue] commission alert detect failed: {e}")
            pass

    shop_alert_rect = profile.regions.get("training_hub_shop_alert")
    if shop_alert_rect is not None:
        try:
            has_shop_alert = detect_yellow_text(crop_region(image, shop_alert_rect))
        except Exception as e:
            logger.debug(f"[_training_hub_blue] shop alert detect failed: {e}")
            pass

    return TrainingHubStatus(
        training_button=profile.regions.get("training_hub_action_training"),
        commission_button=profile.regions.get("training_hub_action_commission"),
        rest_button=profile.regions.get("training_hub_action_rest"),
        skill_button=profile.regions.get("training_hub_nav_potential"),
        shop_button=profile.regions.get("training_hub_action_shop"),
        has_commission_alert=has_commission_alert,
        has_shop_alert=has_shop_alert,
    )


def _training_select_blue(image, profile: RegionProfile, verbose: bool) -> list[TrainingChoice] | None:
    """Read training options using only ring color detection (no OCR for stat_gain/fail_rate).

    Without OCR we can't read stat_gain or fail_rate — set them to 0 (safe defaults).
    Ring color detection still works and influences scoring.
    """
    TRAINING_CARD_ATTRIBUTES = ("power", "stamina", "guts", "wisdom", "speed")
    choices: list[TrainingChoice] = []
    ring_detector = RingColorDetector()
    confirm_button = profile.regions.get("training_select_confirm_button")
    back_button = profile.regions.get("top_back_button")

    for attr in TRAINING_CARD_ATTRIBUTES:
        card_rect = profile.regions.get(f"training_select_card_{attr}")
        if card_rect is None:
            continue

        ring = "none"
        ring_rect = profile.regions.get("training_select_ring_detect")
        if ring_rect is not None:
            try:
                ring_signal = ring_detector.detect(crop_region(image, ring_rect))
                ring = ring_signal.name
            except Exception as e:
                logger.debug(f"[_training_select_blue] ring detect failed for {attr}: {e}")
                pass

        choices.append(
            TrainingChoice(
                name=attr,
                stat_gain=0,
                ring=ring,
                fail_rate=None,  # blue mode reads no 失败率 → unknown, not 0%
                target=card_rect,
                confirm_button=confirm_button,
                back_button=back_button,
            )
        )

    if verbose:
        for c in choices:
            print(f"  training {c.name}: ring={c.ring}")

    return choices if choices else None


def _rest_submenu_blue(
    image,
    profile: RegionProfile,
    detector: BlueButtonDetector,
    verbose: bool,
) -> RestSubmenu | None:
    """Build rest submenu payload using blue button detection for option selection.

    Without OCR for coin count, we check if the meditation option (option 3)
    has an active blue button. If yes → has_meditation_room=True and coins assumed high.
    Otherwise fall back to option 2.
    """
    meditation_rect = profile.regions.get("rest_submenu_option_3")
    rough_sleep_rect = profile.regions.get("rest_submenu_option_1")
    free_sleep_rect = profile.regions.get("rest_submenu_option_1")

    # Check if meditation room button is active (blue/enabled)
    has_meditation = False
    if meditation_rect is not None:
        try:
            signal = detector.detect(crop_region(image, meditation_rect))
            has_meditation = signal.name == "active_blue"
        except Exception as e:
            logger.debug(f"[_rest_submenu_blue] meditation detect failed: {e}")
            has_meditation = True  # Assume available if we can't detect

    # Without OCR, assume coins are sufficient for the best available option.
    coins = 100 if has_meditation else 40

    if verbose:
        print(f"  rest: meditation={'available' if has_meditation else 'unavailable'} coins={coins}")

    return RestSubmenu(
        coins=coins,
        has_meditation_room=has_meditation,
        meditation_room=meditation_rect or rough_sleep_rect or Rect(0, 0, 1, 1),
        rough_sleep=rough_sleep_rect or free_sleep_rect or Rect(0, 0, 1, 1),
        lodging=profile.regions.get("rest_submenu_option_2"),
        confirm_button=profile.regions.get("rest_submenu_confirm_button"),
    )


def _commission_select_blue(
    image,
    profile: RegionProfile,
    verbose: bool,
) -> CommissionChoice | None:
    """Read commission options using red-text color detection only."""
    options: list[CommissionOption] = []
    for idx in range(1, 6):
        target = profile.regions.get(f"commission_select_option_{idx}")
        if target is None:
            continue

        has_red = False
        red_rect = profile.regions.get(f"commission_select_option_{idx}_red_text")
        if red_rect is not None:
            try:
                has_red = detect_red_text(crop_region(image, red_rect))
            except Exception as e:
                logger.debug(f"[_commission_select_blue] red detect failed for option {idx}: {e}")
                pass

        options.append(
            CommissionOption(
                name=f"commission_{idx}",
                rank="?",
                has_red_text=has_red,
                target=target,
            )
        )

    if verbose:
        for o in options:
            print(f"  commission {o.name}: red_text={o.has_red_text}")

    if not options:
        return None
    accept_btn = profile.regions.get("commission_select_accept_button")
    return CommissionChoice(options=options, accept_button=accept_btn)


def _relic_choice_blue(
    profile: RegionProfile,
    detector: BlueButtonDetector,
    image,
) -> RelicChoice | None:
    """Build a minimal relic choice — without OCR, pick the middle card."""
    options: list[RelicOption] = []
    for idx in range(1, 4):
        target = profile.regions.get(f"relic_choice_card_{idx}")
        if target is None:
            continue
        options.append(RelicOption(name=f"relic_{idx}", score=idx, target=target))

    if not options:
        return None

    confirm_rect = profile.regions.get("relic_choice_confirm_button")
    confirm_active = False
    if confirm_rect is not None and image is not None:
        try:
            signal = detector.detect(crop_region(image, confirm_rect))
            confirm_active = signal.name == "active_blue"
        except Exception as e:
            logger.debug(f"[_relic_choice_blue] confirm detect failed: {e}")
            pass

    # If confirm is active, a relic was already selected.
    selected_name = "relic_2" if confirm_active else None

    return RelicChoice(
        options=options,
        confirm_button=confirm_rect,
        selected_name=selected_name,
    )


def _event_choice_blue(
    image,
    profile: RegionProfile,
    verbose: bool,
) -> list | None:
    """Build minimal event choice options — pick option 1 as default."""
    options: list[EventOption] = []
    for idx in range(1, 5):
        target = profile.regions.get(f"event_choice_option_{idx}")
        if target is None:
            continue
        options.append(EventOption(text=f"option_{idx}", target=target))

    if verbose:
        print(f"  event_choice: {len(options)} options available")

    return options if options else None


def _dialogue_blue(profile: RegionProfile):
    """Return a minimal dialogue scene using the journey skip button."""
    skip_rect = profile.regions.get("dialogue_journey_skip_button")
    if skip_rect is None:
        skip_rect = profile.regions.get("dialogue_intro_skip_button")
    if skip_rect is not None:
        return DialogueScene(skip_button=skip_rect, variant="journey_hud")
    return None


# Blue-mode payload builders by screen. Adapter lambdas give them a uniform
# (image, profile, detector, verbose) signature. Screens not listed need no
# payload in blue mode (policy clicks a fixed button).
_BLUE_PARSERS = {
    Screen.TRAINING_HUB: lambda image, profile, detector, verbose: _training_hub_blue(image, profile),
    Screen.TRAINING_SELECT: lambda image, profile, detector, verbose: _training_select_blue(image, profile, verbose),
    Screen.REST_SUBMENU: lambda image, profile, detector, verbose: _rest_submenu_blue(image, profile, detector, verbose),
    Screen.COMMISSION_SELECT: lambda image, profile, detector, verbose: _commission_select_blue(image, profile, verbose),
    Screen.RELIC_CHOICE: lambda image, profile, detector, verbose: _relic_choice_blue(profile, detector, image),
    Screen.SHOP: _shop_blue,
    Screen.EVENT_CHOICE: lambda image, profile, detector, verbose: _event_choice_blue(image, profile, verbose),
    Screen.DIALOGUE: lambda image, profile, detector, verbose: _dialogue_blue(profile),
    Screen.BATTLE: lambda image, profile, detector, verbose: parse_battle([], profile, image),
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _screen_to_prefix(screen: Screen) -> str | None:
    # NOTE: 迁自旧 live_loop.py，当前无调用方（死代码）。按迁移规范保留，待后续清理。
    mapping = {
        Screen.DIALOGUE: "dialogue",
        Screen.CHARACTER_SELECT: "character",
        Screen.BLESSING_SETUP: "blessing",
        Screen.BLESSING_CHOICE: "blessing",
        Screen.JOURNEY_START: "journey_start",
        Screen.CONFIRM_DIALOG: "confirm_dialog",
        Screen.EVENT_FAST_FORWARD_SETTING: "event_fast_forward",
        Screen.TRAINING_HUB: "training_hub",
        Screen.TRAINING_SELECT: "training_select",
        Screen.REST_SUBMENU: "rest_submenu",
        Screen.EVENT_CHOICE: "event_choice",
        Screen.COMMISSION_SELECT: "commission_select",
        Screen.SHOP: "shop_item",
        Screen.BATTLE: "battle",
        Screen.SKILL_SELECT: "skill_select",
        Screen.POST_TRAINING: "post_training",
        Screen.REGION_MOVE: "region_move",
        Screen.RELIC_CHOICE: "relic_choice",
    }
    return mapping.get(screen)
