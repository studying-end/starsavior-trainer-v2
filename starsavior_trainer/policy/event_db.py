"""事件库 — DEFAULT_EVENT_KEYWORDS + events.json 加载 + 字符级模糊匹配。

重构自 policy.py §5（行 38-150）。OCR 乱码用字符级模糊(阈值 0.6)匹配事件。
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_EVENT_KEYWORDS = {
    "coin_cost": (
        "coin",
        "coins",
        "付钱",
        "金币",
        "购买",
        "花钱",
    ),
    "fatigue_cost": (
        "fatigue",
        "疲劳",
        "疲劳值",
        "消耗疲劳",
        "用力量拔",
        "用力量扳",
        "拔出来",
        "扳出来",
    ),
    "recover": (
        "stamina",
        "recover",
        "体力",
        "恢复",
        "回复",
    ),
    "mood": (
        "mood",
        "心情",
        "干劲",
    ),
    "attribute": (
        "speed",
        "stamina",
        "power",
        "guts",
        "wisdom",
        "速度",
        "耐力",
        "力量",
        "韧性",
        "智力",
        "属性",
    ),
}

# Generic rule profiles to fall back on when no build-profile rule matches.
# Order = preference. Conditional rules (low_stamina, gamble, need_*, …) are
# skipped — we don't guess on situational conditions and defer to the keyword
# heuristic instead.
_EVENT_DEFAULT_PROFILES = ("default", "default_safe", "safe_mode")

_EVENTS_PATH = Path(__file__).resolve().parents[2] / "config" / "events.json"
_EVENT_DB_CACHE: list[dict] | None = None


def _load_event_db() -> list[dict]:
    """Load and cache config/events.json (list of event dicts). Empty on error."""
    global _EVENT_DB_CACHE
    if _EVENT_DB_CACHE is None:
        try:
            data = json.loads(_EVENTS_PATH.read_text(encoding="utf-8"))
            _EVENT_DB_CACHE = list(data.get("events", []))
        except (OSError, json.JSONDecodeError):
            _EVENT_DB_CACHE = []
    return _EVENT_DB_CACHE


def _match_event(ocr_title: str, events: list[dict]) -> dict | None:
    """Fuzzy-match an OCR'd event title to a database event.

    OCR mangles characters (训→川 etc.), so score each event title/alias by the
    fraction of its characters present in the OCR text and take the best above a
    threshold.
    """
    norm = "".join(ch for ch in ocr_title if "一" <= ch <= "鿿")
    if len(norm) < 2:
        return None
    best: dict | None = None
    best_score = 0.0
    for event in events:
        names = [event.get("title", "")] + list(event.get("aliases") or [])
        for name in names:
            key = "".join(ch for ch in str(name) if "一" <= ch <= "鿿")
            if len(key) < 2:
                continue
            score = sum(1 for ch in key if ch in norm) / len(key)
            if score > best_score:
                best_score = score
                best = event
    return best if best_score >= 0.6 else None


def _event_recommended_index(event: dict, build_profile: str) -> int | None:
    """Return the 1-based option index recommended for this build, or None.

    Prefers an exact build-profile rule, then a generic default rule. Returns
    None for events that only carry situational/conditional rules.
    """
    rules = event.get("default_rules") or []
    for rule in rules:
        if rule.get("profile") == build_profile:
            return rule.get("choose_option")
    for fallback in _EVENT_DEFAULT_PROFILES:
        for rule in rules:
            if rule.get("profile") == fallback:
                return rule.get("choose_option")
    return None
