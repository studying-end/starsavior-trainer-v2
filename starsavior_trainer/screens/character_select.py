"""角色选择画面 parser — 滚动列表 + bbox 定位 + 同名多形态匹配。

重构自 screen_reader.py §5（行 256-457）。同名角色有多形态(普通/ANOTHER/COSMIC),
列表拖拽停在半行偏移时固定区域 OCR 只读到切片间隙, 故提供 bbox 定位版兜底。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.models import CharacterOption, CharacterSelect, Rect
from starsavior_trainer.ocr import OcrEngine
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import _or_none, contains_any_text, extract_character_name


def parse_character_select(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> CharacterSelect | None:
    """Build a character-select payload including the right-panel character list.

    Parses up to 7 character slots (character_option_1 … character_option_7)
    from the right-side scrollable list.  Character names are extracted from
    noisy OCR output via extract_character_name().  The currently highlighted
    character is identified from the left-panel OCR (character_selected_name).
    """
    texts = {item.name: item.text for item in region_texts}
    confirm_button = profile.regions.get("character_select_button")
    if confirm_button is None:
        return None

    title = texts.get("character_select_anchor_title", "")
    selected_name = _or_none(texts.get("character_selected_name"))
    if not selected_name and not contains_any_text(title, ("旅程起点", "journey")):
        return None

    # Build option list from the right-panel character slots
    options: list[CharacterOption] = []
    for i in range(1, 8):
        slot_name = f"character_option_{i}"
        rect = profile.regions.get(slot_name)
        if rect is None:
            continue
        raw_text = texts.get(slot_name, "")
        name = extract_character_name(raw_text) if raw_text else None
        if name is None:
            continue
        options.append(
            CharacterOption(
                name=name,
                rank=None,
                stars=None,
                specialty=None,
                selected=(name == selected_name),
                target=rect,
            )
        )

    # Always include the selected character from the left panel so the policy
    # can confirm even when the list OCR misses the highlighted entry.
    selected_target = profile.regions.get("character_selected_name") or confirm_button
    selected_option = CharacterOption(
        name=selected_name or "selected_character",
        rank=_or_none(texts.get("character_selected_rarity_area")),
        stars=None,
        specialty=_or_none(texts.get("character_selected_specialty")),
        selected=True,
        target=selected_target,
    )
    if not any(opt.name == selected_option.name for opt in options):
        options.insert(0, selected_option)

    # Determine whether the list can still be scrolled: we assume yes unless
    # fewer than 7 slots had recognisable names (list end reached).
    can_scroll = sum(1 for opt in options if opt.target != selected_target) >= 7

    return CharacterSelect(
        options=options,
        confirm_button=confirm_button,
        selected_name=selected_option.name,
        can_scroll=can_scroll,
    )


def parse_character_select_bbox(
    image: Image.Image,
    profile: RegionProfile,
    ocr: OcrEngine,
) -> CharacterSelect | None:
    """Build the character-select payload by locating names via OCR bounding
    boxes instead of fixed row regions.

    The list scrolls by dragging and stops at arbitrary (half-row) offsets, so
    the fixed character_option_N regions read only the sliced gaps between rows.
    Here we OCR the whole list column once and use each detected block's box to
    drop a clickable target on the actual name, wherever it landed.
    """
    confirm_button = profile.regions.get("character_select_button")
    if confirm_button is None:
        return None

    # Selected character (left panel).
    sel_rect = profile.regions.get("character_selected_name")
    selected_name = None
    if sel_rect is not None:
        sel_text = ocr.read_text(crop_region(image, sel_rect))
        if sel_text.text and sel_text.confidence > 0.4:
            selected_name = extract_character_name(sel_text.text) or _or_none(sel_text.text)

    # List area = envelope of the 7 fixed option slots (covers the whole column).
    first = profile.regions.get("character_option_1")
    last = profile.regions.get("character_option_7")
    if first is None or last is None:
        return None
    lx, ly = first.x, first.y
    lw = first.width
    lh = (last.y + last.height) - first.y
    list_region = Rect(lx, ly, lw, lh)

    # Two passes over the OCR lines: collect name rows + their click targets, and
    # collect form-marker tokens (ANOTHER/COSMIC text under each row's class icon).
    lines = ocr.read_lines(crop_region(image, list_region))
    name_rows: list[tuple[str, int, Rect]] = []  # (name, y_top, target)
    variant_tokens: list[tuple[str, int]] = []  # (raw_text, y_top)
    for line in lines:
        x1, y1, x2, y2 = line.box
        name = extract_character_name(line.text)
        if name and len(name) >= 2:  # len<2 drops single-char noise (e.g. '双' from a level badge)
            cx = lx + (x1 + x2) // 2
            cy = ly + (y1 + y2) // 2
            target = Rect(max(cx - 90, 0), max(cy - 28, 0), 180, 56)
            name_rows.append((name, y1, target))
        elif _normalize_variant(line.text):
            variant_tokens.append((line.text, y1))

    # Associate each form-marker to the name row directly above it.
    variants = _match_character_variants([(n, y) for n, y, _t in name_rows], variant_tokens)

    # Dedup by (name, variant): same-named characters now have multiple forms
    # (普通 / ANOTHER / COSMIC) — keeping only `name` collapsed two 卡蜜 into one.
    options: list[CharacterOption] = []
    seen: set[tuple[str, str]] = set()
    for (name, _y, target), variant in zip(name_rows, variants):
        key = (name, variant)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            CharacterOption(
                name=name, rank=None, stars=None, specialty=None,
                selected=(name == selected_name and not variant), target=target, variant=variant,
            )
        )

    # Always include the left-panel selected character as a fallback target.
    selected_target = sel_rect or confirm_button
    selected_option = CharacterOption(
        name=selected_name or "selected_character", rank=None, stars=None,
        specialty=None, selected=True, target=selected_target,
    )
    if not any(opt.name == selected_option.name for opt in options):
        options.insert(0, selected_option)

    # Dragging can always move the list further, so as long as we recognised at
    # least one list name we keep scrolling; the policy's end-detection + cap
    # decide when to stop.
    can_scroll = sum(1 for opt in options if opt.target != selected_target) >= 1

    return CharacterSelect(
        options=options,
        confirm_button=confirm_button,
        selected_name=selected_option.name,
        can_scroll=can_scroll,
    )


# 同名角色多形态: 每行职业图标下方的形态文字 (普通=无, 第二形态=ANOTHER, 系列=COSMIC)。
_VARIANT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ANOTHER", ("ANOTHER", "ANOTHE", "NOTHER")),
    ("COSMIC", ("COSMIC", "COSMI", "OSMIC")),
)


def _normalize_variant(text: str) -> str:
    """OCR 文本规范化成形态标记 ANOTHER/COSMIC; 认不出返回 ''(普通形态)。
    容错: 大小写/空格无关, 0↔O 混淆, 以及缺首/尾字母的残读。"""
    up = "".join(text.upper().split()).replace("0", "O")
    for canon, keys in _VARIANT_KEYWORDS:
        if any(k in up for k in keys):
            return canon
    return ""


def _match_character_variants(
    names: list[tuple[str, int]],
    variant_tokens: list[tuple[str, int]],
    *,
    gap_min: int = 15,
    gap_max: int = 70,
) -> list[str]:
    """把形态文字关联到正上方的名字行。

    names: [(name, y_top), ...] (名字行顶 y); variant_tokens: [(raw_text, y_top), ...]
    (无法识别成角色名、但可能是形态文字的 token)。返回与 names 同序的形态标记列表 —
    名字行正下方 [gap_min, gap_max] 像素内若有可识别的形态文字则取之, 否则 ''(普通)。
    """
    out: list[str] = []
    for _name, ny in names:
        found = ""
        for raw, vy in variant_tokens:
            if gap_min <= vy - ny <= gap_max:
                canon = _normalize_variant(raw)
                if canon:
                    found = canon
                    break
        out.append(found)
    return out
