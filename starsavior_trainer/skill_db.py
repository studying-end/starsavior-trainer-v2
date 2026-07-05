"""潜质（技能）模板库——名 + 效果 + 类型 + 战斗优先级 + 种马优先级。

两套优先级存一个 JSON（battle_priority / breeding_priority），避免重复维护潜质名。
运行前配置跑马类型（战斗马/种马），决策时读对应 priority 字段。

== Schema（config/skills.json）==
{
  "schema": "starsavior.skills.v1",
  "skills": [
    {
      "name": "破坏感知",
      "effect": "暴击伤害增加 5%。",
      "kind": "感知",                  // 感知/技巧/天赋/通用（按名推断，识别原价类型）
      "battle_priority": 99,            // 战斗马优先级（0=最优先，99=不学，用户手填前默认 99）
      "breeding_priority": 99           // 种马马优先级（同上，独立配置）
    }
  ]
}

== 类型原价（用户规则）==
- 感知：lv1-5 = 100/150/200/250/300
- 技巧：lv1-5 = 200（统一）
- 天赋：lv1-5 = 300（统一）
- 其它：200（通用）
打折时价格降低（如破坏感知 35% off → lv1 65），bot 直接 OCR 当前价格即可。

== priority 规则（同 shop_db）==
- 0-5 才学（数字小=优先）
- 99=不学（自动入库默认，用户手填前不学）
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# 低于等于此 priority 的潜质才会学（0=最优先，5=最低）
MAX_LEARN_PRIORITY = 5
# 永不学标记: 99 = 绝对不学（也是自动入库默认值，用户手填前不学）
NEVER_LEARN_PRIORITY = 99
DEFAULT_AUTO_PRIORITY = NEVER_LEARN_PRIORITY

# 潜质类型（按名尾字推断，用于识别原价类型）
KIND_SENSE = "感知"
KIND_TECHNIQUE = "技巧"
KIND_TALENT = "天赋"
KIND_GENERIC = "通用"


def infer_kind(name: str) -> str:
    """按潜质名尾字推断类型：xx感知→感知, xx技巧→技巧, xx天赋→天赋, 其它→通用。"""
    n = (name or "").strip()
    if n.endswith(KIND_SENSE):
        return KIND_SENSE
    if n.endswith(KIND_TECHNIQUE):
        return KIND_TECHNIQUE
    if n.endswith(KIND_TALENT):
        return KIND_TALENT
    return KIND_GENERIC


@dataclass(frozen=True)
class SkillEntry:
    """模板库一条记录：潜质名 + 效果 + 类型 + 战斗/种马优先级。"""
    name: str
    effect: str = ""
    kind: str = KIND_GENERIC
    battle_priority: int = DEFAULT_AUTO_PRIORITY
    breeding_priority: int = DEFAULT_AUTO_PRIORITY


def load_skills(path: Path | str) -> list[SkillEntry]:
    """加载模板库 JSON → list[SkillEntry]。文件不存在或空时返回空 list。"""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    skills = data.get("skills", []) if isinstance(data, dict) else []
    out: list[SkillEntry] = []
    for s in skills:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        out.append(SkillEntry(
            name=str(s.get("name", "")).strip(),
            effect=str(s.get("effect", "")).strip(),
            kind=str(s.get("kind", KIND_GENERIC)).strip() or KIND_GENERIC,
            # 不能用 or（priority=0 会被当 falsy）
            battle_priority=(int(s["battle_priority"]) if s.get("battle_priority") is not None else DEFAULT_AUTO_PRIORITY),
            breeding_priority=(int(s["breeding_priority"]) if s.get("breeding_priority") is not None else DEFAULT_AUTO_PRIORITY),
        ))
    return out


def find_skill(skills: list[SkillEntry], name: str) -> SkillEntry | None:
    """按名字精确查找。找不到返回 None（用于判断是否需要自动入库）。"""
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    for entry in skills:
        if entry.name == cleaned:
            return entry
    return None


def save_skill(
    path: Path | str,
    name: str,
    effect: str = "",
    kind: str | None = None,
    battle_priority: int | None = None,
    breeding_priority: int | None = None,
) -> None:
    """自动入库：追加一条记录到模板库 JSON。

    已存在的同名记录 → 更新 effect/kind（保留 priority 不动，避免覆盖用户手填值）。
    新记录 → priority 默认 99（用户手填前不会学）。priority 显式传值才覆盖。
    """
    p = Path(path)
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return
    inferred_kind = kind if kind else infer_kind(cleaned_name)

    # 读现有
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"schema": "starsavior.skills.v1", "skills": []}
    else:
        data = {"schema": "starsavior.skills.v1", "skills": []}

    if not isinstance(data, dict):
        data = {"schema": "starsavior.skills.v1", "skills": []}
    skills = data.setdefault("skills", [])
    if not isinstance(skills, list):
        skills = []
        data["skills"] = skills

    # 已存在 → 更新 effect/kind（保留 priority 不动，避免覆盖用户手填值）
    for s in skills:
        if isinstance(s, dict) and s.get("name") == cleaned_name:
            s["effect"] = effect.strip()
            s["kind"] = inferred_kind
            if battle_priority is not None:
                s["battle_priority"] = battle_priority
            if breeding_priority is not None:
                s["breeding_priority"] = breeding_priority
            break
    else:
        new_item: dict = {
            "name": cleaned_name,
            "effect": effect.strip(),
            "kind": inferred_kind,
            "battle_priority": battle_priority if battle_priority is not None else DEFAULT_AUTO_PRIORITY,
            "breeding_priority": breeding_priority if breeding_priority is not None else DEFAULT_AUTO_PRIORITY,
        }
        skills.append(new_item)

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
