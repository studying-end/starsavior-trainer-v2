"""战斗画面 parser — 评鉴战 entry + 跳过二次确认。

重构自 screen_reader.py §5（行 1279-1341）。基础评鉴战确认框靠 跳过战斗+评鉴战 标题
消歧(坑 #6: 不被误判 EVENT_FAST_FORWARD); 跳过二次确认靠 取消 按钮区分。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.models import BattleScene
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text
from starsavior_trainer.vision import BlueButtonDetector


def parse_battle(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> BattleScene | None:
    """Detect battle screens and return the next battle action."""
    texts = {item.name: item.text for item in region_texts}

    # 跳过战斗 二次确认框: 点「跳过战斗」后弹出"将一并跳过评鉴战前的故事…确定要跳过评鉴
    # 战斗吗?"(取消 / 蓝色「跳过战斗」)。必须点框内蓝色「跳过战斗」确认 —— 底层按钮被遮住,
    # 再点它只会死循环。靠「取消」按钮区分(基础评鉴战确认界面那一侧是「开始委托」, 无取消)。
    skip_confirm_button = profile.regions.get("battle_skip_confirm_button")
    if (
        skip_confirm_button is not None
        and contains_any_text(texts.get("battle_skip_confirm_cancel", ""), ("取消",))
        and contains_any_text(texts.get("battle_skip_confirm_button", ""), ("跳过", "战斗"))
    ):
        return BattleScene(skip_button=skip_confirm_button, confirm_button=None, confirm_active=False)

    # 基础评鉴战 entry confirm (是否要进行评鉴战?): always pick 跳过战斗 — skip the
    # battle and take the result instantly (开始委托 actually fights). confirm_active
    # stays False so decide_battle clicks this skip button, not a confirm button.
    skip_battle_button = profile.regions.get("battle_skip_battle_button")
    if skip_battle_button is not None and (
        contains_any_text(texts.get("battle_skip_battle_button", ""), ("跳过战斗", "跳过"))
        or contains_any_text(texts.get("battle_confirm_title", ""), ("评鉴战", "鉴战"))
    ):
        return BattleScene(skip_button=skip_battle_button, confirm_button=None, confirm_active=False)

    action_button = profile.regions.get("battle_entry_button") or profile.regions.get("battle_skip_button")
    if action_button is None:
        return None

    skip_text = texts.get("battle_skip_button_text", "")
    title_text = texts.get("battle_title", "")
    has_skip = contains_any_text(skip_text, ("跳过战斗", "跳过", "skip"))
    has_battle = contains_any_text(title_text, ("评鉴战", "战斗", "battle"))

    confirm_button = profile.regions.get("battle_accept_button") or profile.regions.get("battle_confirm_button")
    confirm_active = False
    if confirm_button is not None and image is not None:
        signal = BlueButtonDetector().detect(crop_region(image, confirm_button))
        confirm_active = signal.name == "active_blue"

    if not has_skip and not has_battle:
        if confirm_active:
            return BattleScene(
                skip_button=action_button,
                confirm_button=confirm_button,
                confirm_active=True,
            )
        if image is not None:
            signal = BlueButtonDetector().detect(crop_region(image, action_button))
            if signal.name != "active_blue":
                return None
        else:
            return None

    return BattleScene(
        skip_button=action_button,
        confirm_button=confirm_button,
        confirm_active=confirm_active,
    )
