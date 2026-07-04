"""休息子菜单 parser。

重构自 screen_reader.py §5（行 1039-1078）。冥想室检测靠选项标签 OCR。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Rect, RestSubmenu
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_constants import REST_OPTION_ALIASES
from starsavior_trainer.text_utils import contains_any_text, parse_first_int


def parse_rest_submenu(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> RestSubmenu | None:
    """Read the rest submenu with coin count and sleep options."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_rest_submenu_anchor(texts, profile):
        return None

    coins = parse_first_int(texts.get("rest_submenu_coin_count", "")) or 0

    meditation_rect = profile.regions.get("rest_submenu_option_3")
    rough_sleep_rect = profile.regions.get("rest_submenu_option_1")
    free_sleep_rect = profile.regions.get("rest_submenu_option_1")

    meditation_label = texts.get("rest_submenu_option_3_label", "")
    meditation_option_text = texts.get("rest_submenu_option_3", "")
    has_any_rest_ocr = any(name.startswith("rest_submenu_") and text.strip() for name, text in texts.items())
    has_meditation = meditation_rect is not None and (
        contains_any_text(meditation_label, REST_OPTION_ALIASES["meditation_room"])
        or contains_any_text(meditation_option_text, REST_OPTION_ALIASES["meditation_room"])
        or not has_any_rest_ocr
    )

    return RestSubmenu(
        coins=coins,
        has_meditation_room=has_meditation,
        meditation_room=meditation_rect or rough_sleep_rect or Rect(0, 0, 1, 1),
        rough_sleep=rough_sleep_rect or free_sleep_rect or Rect(0, 0, 1, 1),
        lodging=profile.regions.get("rest_submenu_option_2"),
        confirm_button=profile.regions.get("rest_submenu_confirm_button"),
    )


def _has_rest_submenu_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    for key in ("rest_submenu_option_1", "rest_submenu_option_2", "rest_submenu_option_3"):
        if profile.regions.get(key) is None:
            return False
    return True
