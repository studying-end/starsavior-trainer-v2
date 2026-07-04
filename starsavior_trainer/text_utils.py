"""OCR 文字/数字解析工具 — 通用 + 游戏特定容错。

数字按场景写专门解析函数(坑台账 E 类 24-29)：
- parse_rank_number: 'RANK17' 不丢前导 1(不守卫相邻字母)；parse_first_int 会丢成 7。
- parse_first_int: 容错 o/l/i/s 当数字(OCR 把数字读成这些)。
- _ocr_int_token_to_int: o→0/l→1/i→1/s→5 核心容错。
重构自 screen_reader.py §5（行 164-248 + 1555-1557）。
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from starsavior_trainer.text_constants import ATTRIBUTE_ALIASES, OCR_REGION_NAME_HINTS


def normalize_ocr_text(text: str) -> str:
    return (
        text.casefold()
        .replace("　", " ")
        .replace("％", "%")
        .replace("，", ",")
        .strip()
    )


def contains_any_text(text: str, candidates: Iterable[str]) -> bool:
    normalized = normalize_ocr_text(text)
    return any(normalize_ocr_text(candidate) in normalized for candidate in candidates)


def looks_like_ocr_region(name: str) -> bool:
    return any(hint in name for hint in OCR_REGION_NAME_HINTS)


def extract_character_name(text: str) -> str | None:
    """Extract a character name from noisy OCR output.

    Each character-list entry is OCR'd as a single string that includes rank
    badge digits/symbols and icon glyphs before the actual name.  The name is
    always the rightmost run of 2+ CJK characters (e.g. '双9 康 克莱儿' → '克莱儿').
    Falls back to a single-character run if nothing longer is found.
    """
    # CJK Unified Ideographs (一-鿿) + Extension A (㐀-䶿)
    cjk_runs = re.findall("[一-鿿㐀-䶿]+", text)
    meaningful = [run for run in cjk_runs if len(run) >= 2]
    if meaningful:
        return meaningful[-1]
    if cjk_runs:
        return cjk_runs[-1]
    return None


def parse_first_int(text: str) -> int | None:
    normalized = normalize_ocr_text(text)
    match = re.search(r"(?<![a-z])([0-9olis][0-9olis,]*)(?![a-z])", normalized)
    if match is None:
        return None
    return _ocr_int_token_to_int(match.group(1))


def parse_rank_number(text: str) -> int | None:
    """Extract the level number from a 'RANK 21' / 'RANK17' / 'RANK 17 一级' label.

    parse_first_int refuses a digit glued to a letter (its ``(?<![a-z])`` guard),
    so 'RANK17' would lose the leading '1' and read as 7. Rank labels legitimately
    glue the number to 'RANK', so here we take the first OCR-digit run regardless
    of an adjacent letter.
    """
    normalized = normalize_ocr_text(text)
    match = re.search(r"[0-9olis][0-9olis,]*", normalized)
    if match is None:
        return None
    return _ocr_int_token_to_int(match.group(0))


def parse_last_int(text: str) -> int | None:
    normalized = normalize_ocr_text(text)
    matches = re.findall(r"(?<![a-z])([0-9olis][0-9olis,]*)(?![a-z])", normalized)
    if not matches:
        return None
    return _ocr_int_token_to_int(matches[-1])


def parse_percent(text: str) -> int | None:
    normalized = normalize_ocr_text(text)
    match = re.search(r"(?<![a-z])([0-9olis][0-9olis,]*)\s*%", normalized)
    if match is None:
        return parse_first_int(normalized)
    return _ocr_int_token_to_int(match.group(1))


def parse_attribute_value(text: str) -> tuple[str, int] | None:
    value = parse_first_int(text)
    if value is None:
        return None
    normalized = normalize_ocr_text(text)
    for attribute, aliases in ATTRIBUTE_ALIASES.items():
        if contains_any_text(normalized, aliases):
            return attribute, value
    return None


def _ocr_int_token_to_int(token: str) -> int:
    cleaned = token.translate(str.maketrans({"o": "0", "l": "1", "i": "1", "s": "5"}))
    return int(cleaned.replace(",", ""))


def _or_none(text: str | None) -> str | None:
    t = (text or "").strip()
    return t if t else None
