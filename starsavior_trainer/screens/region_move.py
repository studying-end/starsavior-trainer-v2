"""区域移动 parser — 列车月台。

重构自 screen_reader.py §5（行 1236-1271）。两步流: 选目的地 → 点前往。坑 #5:
列车月台被误判 RELIC_CHOICE, 靠 地区移动+列车月台 双锚点消歧。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text


def parse_region_move(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> Rect | None:
    """Detect the region-move screen and return the rect to click next.

    The real 列车月台 (train-station) region-move is a two-step flow: a destination
    list (e.g. 阿卡农) on the right; clicking a destination shows its detail card and
    a 前往 (go) button at the bottom-right; 前往 travels there. So:
      - 前往 present  → return the 前往 button (a destination is selected → travel).
      - otherwise     → return the first destination row (select it first).
    Falls back to the older single 移动-button screen for backward compatibility.
    """
    texts = {item.name: item.text for item in region_texts}

    # 列车月台 region-move (anchors: 地区移动 + 列车月台).
    anchor = texts.get("region_move_anchor_title", "")
    station = texts.get("region_move_station_title", "")
    if contains_any_text(anchor, ("地区移动", "区移动", "地区")) and contains_any_text(
        station, ("列车月台", "车月台", "月台")
    ):
        if contains_any_text(texts.get("region_move_go_button", ""), ("前往", "出发", "前住")):
            go = profile.regions.get("region_move_go_button")
            if go is not None:
                return go
        dest = profile.regions.get("region_move_destination_1")
        if dest is not None:
            return dest
        return None

    # Backward-compat: older single 移动-button region-move screen.
    move_rect = profile.regions.get("region_move_button")
    if move_rect is not None and contains_any_text(texts.get("region_move_button_text", ""), ("移动", "move")):
        return move_rect

    return None
