"""委托选择 parser。

重构自 screen_reader.py §5（行 1126-1182）。建议综合等级 + 角色综合等级都从本界面直接读
(坑 #39: 解耦 — 不依赖先经过训练大厅读 character_rank)。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.models import CommissionChoice, CommissionOption
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text, parse_rank_number
from starsavior_trainer.vision import detect_red_text


def parse_commission_select(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> CommissionChoice | None:
    """Read commission options, including red-text suitability detection."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_commission_anchor(texts, profile):
        return None

    options: list[CommissionOption] = []
    for idx in range(1, 6):
        target = profile.regions.get(f"commission_select_option_{idx}")
        if target is None:
            continue
        name = texts.get(f"commission_select_option_{idx}_name", "").strip()
        rank = texts.get(f"commission_select_option_{idx}_rank", "").strip()
        if not name:
            continue

        has_red = False
        if image is not None:
            red_rect = profile.regions.get(f"commission_select_option_{idx}_red_text")
            if red_rect is not None:
                has_red = detect_red_text(crop_region(image, red_rect))

        options.append(
            CommissionOption(
                name=name,
                rank=rank,
                has_red_text=has_red,
                target=target,
            )
        )

    if not options:
        return None
    accept_btn = profile.regions.get("commission_select_accept_button")
    back_btn = profile.regions.get("top_back_button")
    # 建议综合等级只在中央详情区显示当前选中委托的值 (如 "RANK 17"); 角色综合等级在
    # 左上 ("RANK 21")。两者都是数字, 供检视器逐个点开读建议等级、选≤角色等级的最高阶。
    suggested_rank = parse_rank_number(texts.get("commission_select_suggested_rank", ""))
    character_rank = parse_rank_number(texts.get("commission_select_character_rank", ""))
    return CommissionChoice(
        options=options,
        accept_button=accept_btn,
        back_button=back_btn,
        selected_suggested_rank=suggested_rank,
        character_rank=character_rank,
    )


def _has_commission_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    title = texts.get("commission_select_anchor_title", "")
    names = " ".join(texts.get(f"commission_select_option_{i}_name", "") for i in range(1, 6))
    return bool(names.strip()) or contains_any_text(title, ("委托", "commission"))
