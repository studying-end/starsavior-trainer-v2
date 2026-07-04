"""祝福画面 parser — 祝福装备 setup + 祝福卡 choice。

重构自 screen_reader.py §5（行 460-619 + 1521-1547）。祝福卡 choice 用详情面板 OCR
交叉验证选中卡 + 视觉亮边兜底; 子祝福数从详情面板槽位填充检测。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.models import BlessingChoice, BlessingOption, BlessingSetup, BlessingSlot
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text, parse_attribute_value
from starsavior_trainer.vision import (
    card_highlight_score,
    detail_sub_blessing_slot_filled,
    is_blessing_slot_filled,
    is_blue_region,
)


def parse_blessing_setup(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> BlessingSetup | None:
    """Build blessing setup payload from slot/button regions."""
    texts = {item.name: item.text for item in region_texts}
    confirm_button = profile.regions.get("blessing_confirm_button")
    auto_equip_button = profile.regions.get("blessing_auto_equip_button")
    if confirm_button is None or auto_equip_button is None:
        return None

    title = texts.get("blessing_setup_anchor_title", "")
    if not contains_any_text(title, ("旅程起点", "journey")) and not (
        profile.regions.get("blessing_slot_1") and profile.regions.get("blessing_slot_2")
    ):
        return None

    can_confirm = is_blue_region(confirm_button, image)
    slots: list[BlessingSlot] = []
    for index in (1, 2):
        rect = profile.regions.get(f"blessing_slot_{index}")
        if rect is not None:
            slots.append(BlessingSlot(index=index, occupied=is_blessing_slot_filled(rect, image), target=rect))

    if not slots:
        return None
    return BlessingSetup(
        slots=slots,
        auto_equip_button=auto_equip_button,
        confirm_button=confirm_button,
        can_confirm=can_confirm,
    )


def parse_blessing_choice(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> BlessingChoice | None:
    """Read visible blessing cards and their main attribute values.

    Uses the right-side detail panel OCR to cross-validate which card is
    currently selected, falling back to visual border-detection.
    """
    texts = {item.name: item.text for item in region_texts}
    title = texts.get("blessing_choice_anchor_archive", "")
    if not contains_any_text(title, ("星辰档案", "archive")) and not any(
        name.startswith("blessing_card_") for name in texts
    ):
        return None

    # ── detail-panel OCR: read the selected blessing's attribute+value ──
    detail_parsed = _parse_detail_panel_selection(texts)
    detail_attribute, detail_value = detail_parsed if detail_parsed else (None, None)

    # ── visual selected-card detection (fallback) ──
    visual_selected_index = _selected_blessing_card_index(profile, image)

    # ── read sub-blessing count from detail panel ──
    selected_sub_blessing_count = _count_detail_sub_blessings(profile, image)

    # ── build options from card-grid OCR ──
    options: list[BlessingOption] = []
    ocr_selected_index: int | None = None

    for index in range(1, 21):
        card_key = f"blessing_card_{index:02d}"
        target = profile.regions.get(card_key)
        if target is None:
            continue
        parsed = parse_attribute_value(texts.get(f"{card_key}_attribute", ""))
        if parsed is None:
            continue
        attribute, value = parsed

        # Cross-check: does this card match the detail panel?
        if ocr_selected_index is None and detail_attribute == attribute and detail_value == value:
            ocr_selected_index = index

        options.append(
            BlessingOption(
                name=f"{attribute}_blessing_{value}_{index:02d}",
                attribute=attribute,
                value=value,
                target=target,
                sub_blessing_count=0,  # patched below after selection is resolved
            )
        )

    # ── OCR recovery: if detail panel found a selection but no card OCR matched,
    #     rebuild the selected card entry from detail-panel data + visual index. ──
    if (
        not options
        and detail_parsed is not None
        and visual_selected_index is not None
        and profile.regions.get(f"blessing_card_{visual_selected_index:02d}") is not None
    ):
        attribute, value = detail_parsed
        card_key = f"blessing_card_{visual_selected_index:02d}"
        options.append(
            BlessingOption(
                name=f"{attribute}_blessing_{value}_{visual_selected_index:02d}",
                attribute=attribute,
                value=value,
                target=profile.regions[card_key],
                sub_blessing_count=selected_sub_blessing_count,
            )
        )
        ocr_selected_index = visual_selected_index

    if not options:
        return None

    # ── resolve selected index: OCR detail panel > visual highlight > None ──
    selected_card_index = ocr_selected_index or visual_selected_index

    # Patch sub_blessing_count only when OCR confirms which card the detail panel is showing.
    # Visual-only selection (no OCR detail match) leaves sub_blessing_count=0; the
    # BlessingChoiceInspector handles explicit per-card inspection in the live loop.
    if ocr_selected_index is not None:
        for i, option in enumerate(options):
            if option.name.endswith(f"_{ocr_selected_index:02d}"):
                options[i] = BlessingOption(
                    name=option.name,
                    attribute=option.attribute,
                    value=option.value,
                    target=option.target,
                    sub_blessing_count=selected_sub_blessing_count,
                )
                break

    return BlessingChoice(
        options=options,
        confirm_button=profile.regions.get("blessing_choice_confirm_button"),
        selected_name=next(
            (option.name for option in options if option.name.endswith(f"_{selected_card_index:02d}")), None
        )
        if selected_card_index is not None
        else None,
        detail_sub_blessing_count=selected_sub_blessing_count,
    )


def _parse_detail_panel_selection(texts: dict[str, str]) -> tuple[str, int] | None:
    """Parse the currently selected blessing attribute+value from the right-side detail panel OCR.

    Checks multiple region names to accommodate different profile naming conventions
    (e.g. ``blessing_choice_detail_type`` vs ``blessing_choice_detail_attribute``).
    """
    for region_name in (
        "blessing_choice_detail_type",
        "blessing_choice_detail_attribute",
    ):
        raw = texts.get(region_name, "")
        if raw.strip():
            parsed = parse_attribute_value(raw)
            if parsed is not None:
                return parsed
    return None


def _selected_blessing_card_index(profile: RegionProfile, image: Image.Image | None) -> int | None:
    if image is None:
        return None
    scores: list[tuple[float, int]] = []
    for index in range(1, 21):
        rect = profile.regions.get(f"blessing_card_{index:02d}")
        if rect is not None:
            scores.append((card_highlight_score(rect, image), index))
    if not scores:
        return None
    scores.sort(reverse=True)
    best_score, best_index = scores[0]
    next_score = scores[1][0] if len(scores) > 1 else 0.0
    if best_score >= 0.09 and best_score >= next_score + 0.02:
        return best_index
    return None


def _count_detail_sub_blessings(profile: RegionProfile, image: Image.Image | None) -> int:
    if image is None:
        return 0
    count = 0
    for index in range(1, 4):
        rect = profile.regions.get(f"blessing_choice_detail_sub_{index}")
        if rect is not None and detail_sub_blessing_slot_filled(rect, image):
            count += 1
    return count
