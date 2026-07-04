"""旅程事件选择 parser。

重构自 screen_reader.py §5（行 1086-1118）。事件判定要求多选项都有内容(坑 #2:
EVENT_CHOICE 与 DIALOGUE 共享"旅程事件"标题, 扫 option_2-4 有真实文本才算)。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import EventOption
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text


def parse_event_choice(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> list[EventOption] | None:
    """Read event choice options from the screen."""
    texts = {item.name: item.text for item in region_texts}

    if not _has_event_choice_anchor(texts, profile):
        return None

    event_title = texts.get("event_choice_title", "").strip()
    options: list[EventOption] = []
    for idx in range(1, 5):
        target = profile.regions.get(f"event_choice_option_{idx}")
        if target is None:
            continue
        option_text = texts.get(f"event_choice_option_{idx}_text", "") or texts.get(f"event_choice_option_{idx}", "")
        if option_text.strip():
            options.append(EventOption(text=option_text.strip(), target=target, event_title=event_title))

    if not options:
        return None
    return options


def _has_event_choice_anchor(texts: dict[str, str], profile: RegionProfile) -> bool:
    title = texts.get("event_choice_title", "")
    option1 = texts.get("event_choice_option_1_text", "")
    if contains_any_text(title, ("旅程事件", "事件", "event")):
        return True
    if option1.strip() and profile.regions.get("event_choice_option_1") is not None:
        return True
    return False
