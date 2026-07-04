"""OCR 文字别名常量 — 游戏特定。

属性/训练名/遗物/休息/商店的 OCR 别名映射，供 text_utils.contains_any_text 与各画面
parser 做容错匹配（OCR 易把"受"读成"文"等，按钮匹配用稳定前缀/独特词，坑台账 E 类）。
重构自 screen_reader.py §5（行 53-109）。
"""
from __future__ import annotations

ATTRIBUTE_ALIASES = {
    "power": ("力量", "power"),
    "stamina": ("体力", "耐力", "stamina", "hp"),
    "guts": ("韧性", "guts", "protection"),
    "wisdom": ("专注", "智力", "focus", "wisdom"),
    "speed": ("速度", "保护", "speed"),
}

RELIC_NAME_ALIASES = {
    "soft_toy_friend": ("软绵绵的玩偶朋友", "玩偶朋友"),
    # 高亮卡(首轮烦人的布谷鸟时钟)OCR 乱码, 只匹配独特词"布谷鸟"否则固定首选失败。
    "annoying_cuckoo_clock": ("烦人的布谷鸟时钟", "布谷鸟时钟", "布谷鸟"),
    "balanced_scale": ("平衡的天秤", "天秤"),
}

TRAINING_NAME_ALIASES = {
    "power": ("力量训练", "力量", "power"),
    "stamina": ("体力训练", "体力", "stamina"),
    "guts": ("韧性训练", "韧性", "guts"),
    "wisdom": ("集中训练", "集中", "专注训练", "专注", "wisdom", "focus"),
    "speed": ("速度训练", "速度", "保护训练", "保护", "speed"),
}

REST_OPTION_ALIASES = {
    "meditation_room": ("冥想室", "meditation"),
    "rough_sleep": ("露宿", "rough", "露营"),
    "free_sleep": ("免费", "free"),
}

SHOP_ALIASES = {
    "advanced_training_book": ("高级训练书", "advanced"),
    "stamina_potion": ("体力药", "stamina potion", "体力"),
    "mood_candy": ("心情糖", "mood candy", "心情"),
}

# 区域名含这些 hint 的视为需要 OCR 的区域(供 RegionOcrReader.read_ocr_regions)。
OCR_REGION_NAME_HINTS = (
    "anchor", "count", "description", "difficulty", "distance", "label",
    "message", "name", "number", "record", "resource", "score", "stat",
    "status", "summary", "text", "title",
)
