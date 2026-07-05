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


# ---------------------------------------------------------------------------
# §22.14 自动入库: find_event_exact(精确判重) + save_event(写 default_rules) + 清缓存
# ---------------------------------------------------------------------------


def _clear_cache() -> None:
    """清 _EVENT_DB_CACHE, 下次 _load_event_db 重读文件(save_event 后调用)。"""
    global _EVENT_DB_CACHE
    _EVENT_DB_CACHE = None


def find_event_exact(events: list[dict], title: str) -> dict | None:
    """按 title 精确查找(判"是否已入库", 不用模糊匹配)。找不到返回 None。"""
    cleaned = (title or "").strip()
    if not cleaned:
        return None
    for event in events:
        if event.get("title") == cleaned:
            return event
    return None


def save_event(
    title: str,
    options_text: list[str] | None = None,
    choose_option: int = 1,
    path: Path | str | None = None,
) -> None:
    """§22.14 自动入库新事件: 写 default_rules choose_option(默认1) → 决策走 db_choice 选第1个。

    已存在(精确名)→ 不覆盖(保留用户手填规则)。新事件 → 写 default_rules + 清缓存。
    options_text 是各选项的 OCR 文本(仅供查阅, 决策不用)。
    """
    p = Path(path) if path is not None else _EVENTS_PATH
    cleaned_title = (title or "").strip()
    if not cleaned_title:
        return

    # 读现有
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"schema": "starsavior.events.v1", "source": "auto", "events": []}
    if not isinstance(data, dict):
        data = {"schema": "starsavior.events.v1", "source": "auto", "events": []}
    events = data.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        data["events"] = events

    # 已存在(精确名)→ 不覆盖
    for event in events:
        if isinstance(event, dict) and event.get("title") == cleaned_title:
            return

    # 新事件入库
    options = []
    for idx, text in enumerate(options_text or [], start=1):
        options.append({"index": idx, "text": text})
    events.append({
        "id": cleaned_title,
        "title": cleaned_title,
        "options": options,
        "default_rules": [
            {"profile": "default", "choose_option": choose_option, "reason": "自动入库默认第1个选项"}
        ],
        "status": "auto_inserted",
    })
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _clear_cache()
