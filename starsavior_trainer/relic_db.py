"""奖励模板库（relic template database）—— 名字 + 效果文本 + 解析出的属性标签。

类似 events.json 的角色事件库：纯文本数据，不存图像。运行时碰到奖励画面：
1. OCR 出 3 张卡的 name + description
2. 用 name 查模板库拿"已知 attributes"（首次见不到就自动入库）
3. 按角色类型（刺客/术师/弓手/突击者/辅助/坦克）的属性优先级组选最高属性那张卡

== 角色类型 → 优先级组 ==
characters.json 6 类（刺客/术师/游侠/突击者/辅助/坦克）按用户规则分两组：
- ATTACK 组（输出系，按速度>暴击率>暴击伤害>攻击力 优先）：刺客/术师/游侠/突击者
- DEFENSE 组（生存系，按速度>生命力>防御力 优先）：辅助/坦克

== attributes 解析 ==
效果文本（如「首次战斗开始时，自身的最大生命力增加4%」）按关键词解析出标签：
- speed（速度/速 / spd）
- crit_rate（暴击率/暴击概率）
- crit_dmg（暴击伤害/爆伤）
- attack（攻击力/攻击/atk）
- hp（生命力/生命/HP）
- defense（防御力/防御/def）
- none（无属性/未知）

匹配顺序很重要：先匹配「暴击率」再「暴击伤害」（避免「暴击率」被「暴击」前缀吞掉）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ── 属性标签 + 关键词 ─────────────────────────────────────────────────────
# 顺序敏感：先长后短，先具体后通用，避免前缀误匹配。
_ATTRIBUTE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("crit_rate", ("暴击率", "暴击概率", "critical rate", "crit rate", "crit_rate")),
    ("crit_dmg", ("暴击伤害", "爆伤", "critical damage", "crit damage", "crit_dmg")),
    ("speed", ("速度", "速+", "spd", "speed")),
    ("attack", ("攻击力", "攻击+", "atk", "attack")),
    ("hp", ("生命力", "生命+", "最大生命", "生命值", "hp", "hit point")),
    ("defense", ("防御力", "防御+", "def", "defense", "defence")),
]

# ── 角色类型 → 优先级组 ──────────────────────────────────────────────────
# characters.json 6 类名 → 2 个优先级组。用户规则：
# - 刺客/术师/弓手（游侠）/突击者（战士）= 输出系 = ATTACK 组
# - 辅助/坦克 = 生存系 = DEFENSE 组
ATTACK_GROUP = "attack"
DEFENSE_GROUP = "defense"

_CHARACTER_CLASS_TO_GROUP: dict[str, str] = {
    "刺客": ATTACK_GROUP,
    "术师": ATTACK_GROUP,
    "游侠": ATTACK_GROUP,    # = 弓手
    "突击者": ATTACK_GROUP,  # = 战士（与刺客同组，输出系）
    "辅助": DEFENSE_GROUP,
    "坦克": DEFENSE_GROUP,
}

# 各组的属性优先级（前者更优先）
_PRIORITY_BY_GROUP: dict[str, tuple[str, ...]] = {
    ATTACK_GROUP: ("speed", "crit_rate", "crit_dmg", "attack"),
    DEFENSE_GROUP: ("speed", "hp", "defense"),
}


@dataclass(frozen=True)
class RelicEntry:
    """模板库一条记录：奖励名 + 效果文本 + 解析出的属性标签。"""
    name: str
    effect_text: str
    attributes: tuple[str, ...] = ()


def load_relics(path: Path | str) -> list[RelicEntry]:
    """加载模板库 JSON → list[RelicEntry]。文件不存在或空时返回空 list。"""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    relics = data.get("relics", []) if isinstance(data, dict) else []
    return [
        RelicEntry(
            name=str(r.get("name", "")).strip(),
            effect_text=str(r.get("effect_text", "")).strip(),
            attributes=tuple(r.get("attributes", ()) or ()),
        )
        for r in relics
        if isinstance(r, dict) and r.get("name")
    ]


def find_relic(relics: list[RelicEntry], name: str) -> RelicEntry | None:
    """按名字精确查找（清洗后）。找不到返回 None（用于判断是否需要自动入库）。"""
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    for entry in relics:
        if entry.name == cleaned:
            return entry
    return None


def extract_attributes(effect_text: str) -> tuple[str, ...]:
    """从效果文本解析出属性标签。多次出现同一属性去重保留首次。
    无任何关键词命中 → 空元组（视为「无属性」/unknown）。

    OCR 偶尔在中文词中插入空格（如「生 命力」），匹配前去除所有空白
    兜底（避免关键词被空格切断漏匹配）。
    """
    text = (effect_text or "").replace(" ", "").replace("\t", "").replace("\n", "")
    found: list[str] = []
    for attr, keywords in _ATTRIBUTE_KEYWORDS:
        for kw in keywords:
            if kw in text and attr not in found:
                found.append(attr)
                break
    return tuple(found)


def save_relic(path: Path | str, name: str, effect_text: str, attributes: tuple[str, ...] | None = None) -> None:
    """自动入库：追加一条记录到模板库 JSON。attributes 为 None 时自动解析。"""
    p = Path(path)
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return
    attrs = attributes if attributes is not None else extract_attributes(effect_text)

    # 读现有
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"schema": "starsavior.relics.v1", "relics": []}
    else:
        data = {"schema": "starsavior.relics.v1", "relics": []}

    if not isinstance(data, dict):
        data = {"schema": "starsavior.relics.v1", "relics": []}
    relics = data.setdefault("relics", [])
    if not isinstance(relics, list):
        relics = []
        data["relics"] = relics

    # 已存在（按名字）→ 更新 effect_text/attributes；否则追加。
    for r in relics:
        if isinstance(r, dict) and r.get("name") == cleaned_name:
            r["effect_text"] = effect_text.strip()
            r["attributes"] = list(attrs)
            break
    else:
        relics.append({
            "name": cleaned_name,
            "effect_text": effect_text.strip(),
            "attributes": list(attrs),
        })

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def class_to_priority_group(character_class: str | None) -> str:
    """角色类型（characters.json 6 类名）→ 优先级组（attack/defense）。
    未知/None → 默认 ATTACK（输出系优先，与原 decide_relic 一致）。"""
    if character_class and character_class in _CHARACTER_CLASS_TO_GROUP:
        return _CHARACTER_CLASS_TO_GROUP[character_class]
    return ATTACK_GROUP


def priority_for_group(group: str) -> tuple[str, ...]:
    """优先级组 → 属性优先级元组。未知组返回 ATTACK 的。"""
    return _PRIORITY_BY_GROUP.get(group, _PRIORITY_BY_GROUP[ATTACK_GROUP])


def score_relic_by_priority(attributes: tuple[str, ...], group: str) -> int:
    """按角色优先级组给奖励打分：命中最高优先级属性 → 最高分。
    优先级顺序：第 1 位 = 100 分，第 2 位 = 90 分，依此类推（-10 递减）。
    无属性命中 → 0 分（最低）。多个属性取最高优先级的那个。"""
    priority = priority_for_group(group)
    for index, attr in enumerate(priority):
        if attr in attributes:
            return 100 - index * 10
    return 0
