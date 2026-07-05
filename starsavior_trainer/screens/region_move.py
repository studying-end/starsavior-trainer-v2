"""区域移动 parser — 列车月台。

重构自 screen_reader.py §5（行 1236-1271）。两步流: 选目的地 → 点前往。坑 #5:
列车月台被误判 RELIC_CHOICE, 靠 地区移动+列车月台 双锚点消歧。

§22.11 多目的地: 返回 RegionMoveStatus(含目的地列表), 决策层按角色类型选目的地
(弗洛拉=术士/游侠/突击者, 卡莱德=坦克/辅助)。第一次(阿卡农)只有1个目的地 fallback。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Rect, RegionDestination, RegionMoveStatus
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text, normalize_ocr_text


def _read_destination_name(texts: dict[str, str], idx: int) -> str:
    """读第 idx 个目的地的 OCR 名(如"弗洛拉"/"卡莱德"/"阿卡农")。"""
    raw = texts.get(f"region_move_destination_{idx}_name", "")
    return normalize_ocr_text(raw).strip()


def parse_region_move(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> RegionMoveStatus | None:
    """解析地区移动画面 → RegionMoveStatus(destinations + go_button + is_region_move)。

    返回 None = 不是 region_move 画面(锚点全未命中, 非兼容旧屏)。
    返回 RegionMoveStatus(is_region_move 可能 False) = 兼容旧屏或回合兜底用。
    - is_region_move=True: 锚点命中(地区移动+列车月台), destinations/go_button 已填。
    - is_region_move=False: 仅旧"移动"按钮屏兼容路径, destinations 空。
    """
    texts = {item.name: item.text for item in region_texts}

    # 列车月台 region-move (anchors: 地区移动 + 列车月台).
    anchor = texts.get("region_move_anchor_title", "")
    station = texts.get("region_move_station_title", "")
    if contains_any_text(anchor, ("地区移动", "区移动", "地区")) and contains_any_text(
        station, ("列车月台", "车月台", "月台")
    ):
        # 收集所有 destination_N (N=1,2,...) 直到 region 缺失或 name 空。
        destinations: list[RegionDestination] = []
        idx = 1
        while True:
            rect = profile.regions.get(f"region_move_destination_{idx}")
            if rect is None:
                break
            name = _read_destination_name(texts, idx)
            # name 空也收(第一次阿卡农可能没配 name region), 决策靠 fallback 点 destination_1
            destinations.append(RegionDestination(name=name, rect=rect))
            idx += 1
        go_button = None
        if contains_any_text(texts.get("region_move_go_button", ""), ("前往", "出发", "前住")):
            go_button = profile.regions.get("region_move_go_button")
        return RegionMoveStatus(
            destinations=tuple(destinations),
            go_button=go_button,
            is_region_move=True,
        )

    # Backward-compat: older single 移动-button region-move screen.
    move_rect = profile.regions.get("region_move_button")
    if move_rect is not None and contains_any_text(texts.get("region_move_button_text", ""), ("移动", "move")):
        # 旧屏只有一个移动按钮, 作为 go_button 返回(点它直接移动)。
        return RegionMoveStatus(destinations=(), go_button=move_rect, is_region_move=False)

    return None
