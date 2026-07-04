"""简单画面 parser — 推进/选择类: 旅程起点/确认框/事件快进/对话/训练后/方向/技能。

重构自 screen_reader.py §5（行 622-739 + 1350-1498）。这些画面结构简单(少量区域→payload)。
PostTrainingResult 在本文件定义(旧 screen_reader 内定义, 非通用模型, 不入 models.py)。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image

from starsavior_trainer.models import (
    ConfirmDialog,
    DialogueScene,
    EventFastForwardSetting,
    EventOption,
    JourneyStart,
    Rect,
    SkillOption,
)
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import (
    _or_none,
    contains_any_text,
    parse_first_int,
    parse_last_int,
)
from starsavior_trainer.vision import is_blue_region


def parse_journey_start(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> JourneyStart | None:
    texts = {item.name: item.text for item in region_texts}
    start_button = profile.regions.get("journey_start_button")
    if start_button is None:
        return None
    arcana_slots = [
        rect
        for index in range(1, 6)
        if (rect := profile.regions.get(f"journey_start_arcana_slot_{index}")) is not None
    ]
    return JourneyStart(
        start_button=start_button,
        auto_journey_button=profile.regions.get("journey_start_auto_journey_button"),
        arcana_slots=arcana_slots,
    )


def parse_confirm_dialog(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> ConfirmDialog | None:
    texts = {item.name: item.text for item in region_texts}
    confirm_button = profile.regions.get("confirm_dialog_confirm_button")
    if confirm_button is None:
        return None
    title = _or_none(texts.get("confirm_dialog_title")) or "confirm_dialog"
    message = _or_none(texts.get("confirm_dialog_message")) or ""
    has_dialog_regions = any(name.startswith("confirm_dialog") for name in texts)
    if title == "confirm_dialog" and not message and not has_dialog_regions:
        return None
    return ConfirmDialog(
        title=title,
        message=message,
        confirm_button=confirm_button,
        cancel_button=profile.regions.get("confirm_dialog_cancel_button"),
    )


def parse_event_fast_forward_setting(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> EventFastForwardSetting | None:
    texts = {item.name: item.text for item in region_texts}
    no_option = profile.regions.get("event_fast_forward_no_option")
    watched_option = profile.regions.get("event_fast_forward_watched_option")
    all_option = profile.regions.get("event_fast_forward_all_option")
    confirm_button = profile.regions.get("event_fast_forward_confirm_button")
    if no_option is None or watched_option is None or all_option is None or confirm_button is None:
        return None

    title = texts.get("event_fast_forward_title", "")
    if title and not contains_any_text(title, ("事件快转设定", "fast")):
        return None

    selected_mode = None
    if image is not None:
        checkbox_modes = (
            ("event_fast_forward_no_checkbox", "no_fast_forward"),
            ("event_fast_forward_watched_checkbox", "watched_only"),
            ("event_fast_forward_all_checkbox", "all_events"),
        )
        for region_name, mode in checkbox_modes:
            rect = profile.regions.get(region_name)
            if rect is not None and is_blue_region(rect, image):
                selected_mode = mode
                break

    return EventFastForwardSetting(
        no_fast_forward_option=no_option,
        watched_only_option=watched_option,
        all_events_option=all_option,
        confirm_button=confirm_button,
        selected_mode=selected_mode,
    )


def parse_dialogue_scene(region_texts: Iterable[RegionText], profile: RegionProfile) -> DialogueScene | None:
    """Build a dialogue payload from OCR anchors and skip-button candidates."""

    texts = {item.name: item.text for item in region_texts}

    # 阿尔克那事件: 属性提升的结果展示, 右上 skip 按键对它无效(实机点了画面不动→死循环),
    # 必须点屏幕中心推进(用户告知)。event_label/title 含"阿尔克那"时把推进点设为屏幕中心。
    # (这类无选项的事件会被 classify_hybrid 当成可 skip 的 dialogue, 故在此拦下。)
    arcana_label = texts.get("dialogue_journey_event_label", "") + texts.get("dialogue_journey_title", "")
    center = profile.regions.get("screen_center_button")
    if center is not None and contains_any_text(arcana_label, ("阿尔克那", "尔克那", "克那")):
        return DialogueScene(skip_button=center, variant="arcana_center")

    intro_skip = profile.regions.get("dialogue_intro_skip_button")
    if intro_skip is not None and (
        contains_any_text(texts.get("dialogue_intro_skip_button", ""), ("skip", "跳过"))
        or contains_any_text(texts.get("dialogue_intro_location_text", ""), ("观测机构", "noa"))
    ):
        return DialogueScene(
            skip_button=intro_skip,
            variant="intro_story",
            text_area=profile.regions.get("dialogue_intro_text_area"),
        )

    journey_skip = profile.regions.get("dialogue_journey_skip_button")
    if journey_skip is not None and _has_journey_dialogue_anchor(texts):
        return DialogueScene(
            skip_button=journey_skip,
            variant="journey_hud",
            text_area=profile.regions.get("dialogue_journey_text_area"),
        )

    for name, rect in profile.regions.items():
        if name.startswith("dialogue_") and name.endswith("_skip_button"):
            if contains_any_text(texts.get(name, ""), ("skip", "跳过")):
                return DialogueScene(skip_button=rect, variant=name.removeprefix("dialogue_").removesuffix("_skip_button"))

    return None


@dataclass(frozen=True)
class PostTrainingResult:
    result_text: str | None = None
    stat_gain_value: int | None = None
    event_title: str | None = None
    skip_button: Rect | None = None


def parse_post_training(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> PostTrainingResult | None:
    """Read post-training result screen."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_post_training_anchor(texts, profile):
        return None

    result_text = (
        _or_none(texts.get("post_training_result_text"))
        or _or_none(texts.get("post_training_success_text"))
        or _or_none(texts.get("post_training_title"))
    )
    stat_gain = parse_first_int(texts.get("post_training_stat_gain_value", "")) or parse_first_int(
        texts.get("post_training_success_text", "")
    )
    event_title = _or_none(texts.get("post_training_event_title"))

    return PostTrainingResult(
        result_text=result_text,
        stat_gain_value=stat_gain,
        event_title=event_title,
        skip_button=profile.regions.get("post_training_continue_area") or profile.regions.get("post_training_skip_button"),
    )


def _has_post_training_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    result = texts.get("post_training_result_text", "")
    title = texts.get("post_training_title", "")
    success = texts.get("post_training_success_text", "")
    event = texts.get("post_training_event_title", "")
    gain = texts.get("post_training_stat_gain_value", "")
    combined = result + title + success + event + gain
    return contains_any_text(
        combined,
        ("提升", "事件", "训练成功", "训练", "+", "event"),
    ) or parse_first_int(gain) is not None


def parse_training_direction(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> list[EventOption] | None:
    """Read the fixed training-direction event options."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_training_direction_anchor(texts):
        return None

    options: list[EventOption] = []
    for idx in range(1, 4):
        target = profile.regions.get(f"training_direction_option_{idx}")
        if target is None:
            continue
        option_text = texts.get(f"training_direction_option_{idx}_text", "")
        if option_text.strip():
            options.append(EventOption(text=option_text.strip(), target=target))

    if not options:
        return None
    return options


def _has_training_direction_anchor(texts: dict[str, str]) -> bool:
    title = texts.get("training_direction_title", "")
    return contains_any_text(title, ("训练的方向性", "direction"))


def parse_skill_select(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> list[SkillOption] | None:
    """Read skill selection options from the screen."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_skill_select_anchor(texts, profile):
        return None

    options: list[SkillOption] = []
    for idx in range(1, 6):
        target = profile.regions.get(f"skill_select_option_{idx}_button") or profile.regions.get(f"skill_select_option_{idx}")
        if target is None:
            continue
        name = texts.get(f"skill_select_option_{idx}_name", "").strip()
        if not name:
            continue
        effect = texts.get(f"skill_select_option_{idx}_effect", "").strip() or None
        cost = parse_last_int(texts.get(f"skill_select_option_{idx}_cost", ""))
        if cost is None:
            cost = parse_last_int(texts.get(f"skill_select_option_{idx}_button", ""))
        options.append(SkillOption(name=name, effect=effect, cost=cost, target=target))

    if not options:
        return None
    return options


def _has_skill_select_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    title = texts.get("skill_select_title", "")
    names = " ".join(texts.get(f"skill_select_option_{i}_name", "") for i in range(1, 6))
    return bool(names.strip()) or contains_any_text(title, ("潜质", "技能", "skill"))


def _has_journey_dialogue_anchor(texts: dict[str, str]) -> bool:
    anchor_names = (
        "dialogue_journey_event_label",
        "dialogue_journey_title",
        "dialogue_journey_distance",
        "dialogue_journey_text_area",
    )
    anchor_text = " ".join(texts.get(name, "") for name in anchor_names)
    if texts.get("dialogue_journey_text_area", "").strip() and contains_any_text(
        texts.get("dialogue_journey_event_label", "") + texts.get("dialogue_journey_title", ""),
        ("事件",),
    ):
        return True
    return contains_any_text(
        anchor_text,
        (
            "旅程事件",
            "参加",
            "距离目标",
            "获得",
        ),
    )
