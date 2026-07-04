"""遗物选择画面 parser — 3 卡选择 + 部位→属性映射 + 首轮固定首选。

重构自 screen_reader.py §5（行 742-830 + 1501-1518）。首轮"选择奖励"含布谷鸟时钟等
3 张固定卡 → 固定首选布谷鸟(高亮卡名 OCR 乱码, 只匹配独特词"布谷鸟")。部位名尾部
映射战斗属性供组合圣遗物按 build 优先级选。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.models import RelicChoice, RelicOption
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.relic_db import extract_attributes
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_constants import RELIC_NAME_ALIASES
from starsavior_trainer.text_utils import contains_any_text, parse_first_int
from starsavior_trainer.vision import is_blue_region


def parse_relic_choice(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> RelicChoice | None:
    texts = {item.name: item.text for item in region_texts}
    if not _has_relic_choice_anchor(texts):
        return None

    options: list[RelicOption] = []
    for index in range(1, 4):
        key = f"relic_choice_card_{index}"
        target = profile.regions.get(key)
        if target is None:
            continue
        name = parse_relic_name(texts.get(f"{key}_name", ""))
        score = parse_first_int(texts.get(f"{key}_score", ""))
        card_text = texts.get(key, "")
        # 效果文本(从 relic_choice_card_N_description 区域 OCR 读)。新规则:
        # decide_relic 按效果文本里的属性关键词 + 角色类型优先级组选卡, 不再用 score。
        effect_text = (texts.get(f"{key}_description", "") or "").strip()
        attributes = extract_attributes(effect_text)
        if name is not None or score is not None or effect_text:
            options.append(RelicOption(
                name=name or f"unknown_relic_{index}",
                score=score,
                target=target,
                attribute=_relic_attribute_from_name(name),
                is_team="队员全体" in card_text,  # 队员全体 = 组合圣遗物
                effect_text=effect_text,
                attributes=attributes,
            ))

    if not options:
        # 3-card parse found nothing → this "选择奖励" is the inventory-GRID variant
        # (pick a relic from 持有道具, not a 3-card row). Select the first/topmost
        # (NEW/selected) item and confirm via 选择完成, reusing the two-step _pending_relic.
        grid_cell = profile.regions.get("relic_choice_grid_cell_1")
        confirm = profile.regions.get("relic_choice_confirm_button")
        if grid_cell is not None and confirm is not None:
            return RelicChoice(
                options=[RelicOption(name="held_item_1", score=0, target=grid_cell)],
                confirm_button=confirm,
            )
        return None

    fixed_name = "annoying_cuckoo_clock" if _is_initial_relic_choice(texts, options) else None
    selected_name = fixed_name if fixed_name and _is_confirm_button_active(profile, image) else None

    return RelicChoice(
        options=options,
        confirm_button=profile.regions.get("relic_choice_confirm_button"),
        fixed_name=fixed_name,
        selected_name=selected_name,
    )


def parse_relic_name(text: str) -> str | None:
    for name, aliases in RELIC_NAME_ALIASES.items():
        if contains_any_text(text, aliases):
            return name
    # Unknown relic: keep the raw OCR name (cleaned) instead of returning None.
    # This stops non-first-round relics from being labelled "unknown_relic_N" and,
    # crucially, keeps the highlighted/selected card (whose name OCRs slightly
    # garbled) from being dropped from the options list.
    cleaned = (text or "").strip()
    return cleaned or None


# 部位名(圣遗物名字尾部)→ 战斗属性. 跨系列固定.
_RELIC_PART_ATTRIBUTE = {
    "手套": "attack",
    "帽子": "crit_rate",
    "项链": "crit_dmg",
    "项炼": "crit_dmg",
    "裤子": "defense",
    "铠甲": "hp",
    "胸甲": "hp",
    "眼镜": "hit",
    "鞋子": "speed",
    "披风": "resist",
}


def _relic_attribute_from_name(name: str | None) -> str | None:
    """按部位名(名字尾部)映射出战斗属性; 认不出返回 None."""
    if not name:
        return None
    for part, attr in _RELIC_PART_ATTRIBUTE.items():
        if part in name:
            return attr
    return None


def _has_relic_choice_anchor(texts: dict[str, str]) -> bool:
    if contains_any_text(texts.get("relic_choice_title", ""), ("选择奖励",)):
        return True
    return any(parse_relic_name(texts.get(f"relic_choice_card_{index}_name", "")) for index in range(1, 4))


def _is_initial_relic_choice(texts: dict[str, str], options: list[RelicOption]) -> bool:
    if not contains_any_text(texts.get("relic_choice_title", ""), ("选择奖励",)):
        return False
    names = {option.name for option in options}
    return {"soft_toy_friend", "annoying_cuckoo_clock", "balanced_scale"}.issubset(names)


def _is_confirm_button_active(profile: RegionProfile, image: Image.Image | None) -> bool:
    rect = profile.regions.get("relic_choice_confirm_button")
    if image is None or rect is None:
        return False
    return is_blue_region(rect, image)
