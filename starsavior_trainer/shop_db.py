"""商品模板库（shop item database）—— 名字 + 效果 + 价格 + 分类 + 优先度。

类似 relic_db.py：纯文本数据不存图像。运行时碰到交易画面：
1. 检视器逐行点开商品读 effect
2. 用 name 查模板库拿"已知 classes/priority"（首次见不到就自动入库 priority=99）
3. 按角色类型筛选 class_matches 的商品 + priority ≤ MAX_BUY_PRIORITY 的
4. 按 priority 升序选第一个未买的买（可买多件，每次限 1 件需两步确认）
5. 全部不符合角色类型或 priority 太低 → 退出（用户场景：界面只剩坦克/辅助商品，
   但训练角色是游侠 → 停止购买）

== Schema（config/shop_items.json）==
{
  "schema": "starsavior.shop.v1",
  "items": [
    {
      "name": "力量药剂",
      "effect": "训练后力量+3",
      "price": 100,
      "classes": ["刺客", "术师", "游侠", "突击者"],  // 按角色类型分；空=适合所有角色
      "priority": 0  // 0-5 数字越小越优先；99=自动入库默认(用户手填前不买)
    }
  ]
}

== 分类规则（用户需求）==
- 商品分类可多选（一件商品可同时是游侠+刺客+坦克）
- classes 空数组 [] = 适合所有角色（任何角色类型都匹配）
- characters.json 6 类：刺客/术师/游侠/突击者/辅助/坦克

== priority 规则 ==
- 0=最优先, 1, 2, 3, 4, 5=最低（≤5 才会买）
- 6-98=低优先级不买（用户标记"暂不买"但区别于永不买）
- 99=永不买（绝对不买；自动入库默认也是 99，用户手填前不买）
- 用户手填后下次见到就按填的 priority 决策
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# 低于等于此 priority 的商品才会买（0=最优先，5=最低）
MAX_BUY_PRIORITY = 5
# 永不买标记: 99 = 绝对不买（用户明确标记永不买；也是自动入库默认值，用户手填前不买）
NEVER_BUY_PRIORITY = 99
# 自动入库时填的默认 priority（= 永不买，用户手填前不会买）
DEFAULT_AUTO_PRIORITY = NEVER_BUY_PRIORITY


@dataclass(frozen=True)
class ShopItemEntry:
    """模板库一条记录：商品名 + 效果 + 价格 + 分类 + 优先度。"""
    name: str
    effect: str = ""
    price: int = 0
    classes: tuple[str, ...] = ()  # 空元组 = 适合所有角色
    priority: int = DEFAULT_AUTO_PRIORITY


def load_shop(path: Path | str) -> list[ShopItemEntry]:
    """加载模板库 JSON → list[ShopItemEntry]。文件不存在或空时返回空 list。"""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = data.get("items", []) if isinstance(data, dict) else []
    return [
        ShopItemEntry(
            name=str(it.get("name", "")).strip(),
            effect=str(it.get("effect", "")).strip(),
            price=int(it.get("price", 0) or 0),
            classes=tuple(str(c).strip() for c in (it.get("classes", ()) or ()) if str(c).strip()),
            # 注意：不能用 `or`，否则 priority=0 会被当 falsy 替换成 99
            priority=(int(it["priority"]) if it.get("priority") is not None else DEFAULT_AUTO_PRIORITY),
        )
        for it in items
        if isinstance(it, dict) and it.get("name")
    ]


def find_shop(items: list[ShopItemEntry], name: str) -> ShopItemEntry | None:
    """按名字精确查找。找不到返回 None（用于判断是否需要自动入库）。"""
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    for entry in items:
        if entry.name == cleaned:
            return entry
    return None


def save_shop(
    path: Path | str,
    name: str,
    effect: str = "",
    price: int = 0,
    classes: tuple[str, ...] | None = None,
    priority: int | None = None,
) -> None:
    """自动入库：追加一条记录到模板库 JSON。priority 为 None 时用 DEFAULT_AUTO_PRIORITY(99)。

    已存在的同名记录 → 更新 effect/price/classes（保留 priority 不动，避免覆盖用户手填值）。
    新记录 → priority 默认 99（用户手填前不会买）。
    """
    p = Path(path)
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return
    cls_list = list(classes) if classes is not None else []
    pri = priority if priority is not None else DEFAULT_AUTO_PRIORITY

    # 读现有
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"schema": "starsavior.shop.v1", "items": []}
    else:
        data = {"schema": "starsavior.shop.v1", "items": []}

    if not isinstance(data, dict):
        data = {"schema": "starsavior.shop.v1", "items": []}
    items = data.setdefault("items", [])
    if not isinstance(items, list):
        items = []
        data["items"] = items

    # 已存在 → 更新 effect/price/classes（保留 priority 不动，避免覆盖用户手填值）
    for it in items:
        if isinstance(it, dict) and it.get("name") == cleaned_name:
            it["effect"] = effect.strip()
            it["price"] = int(price or 0)
            it["classes"] = cls_list
            # priority: 用户手填过的（≤5）保留不动；自动入库默认（99）也保留不动
            break
    else:
        items.append({
            "name": cleaned_name,
            "effect": effect.strip(),
            "price": int(price or 0),
            "classes": cls_list,
            "priority": pri,
        })

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def class_matches(item_classes: tuple[str, ...], character_class: str | None) -> bool:
    """商品分类是否匹配角色类型。

    - item_classes 空 → True（适合所有角色）
    - character_class 在 item_classes → True
    - 否则 False

    character_class 为 None/空时：item_classes 空 → True（适合所有角色），
    否则 False（无角色类型无法匹配具体分类）。
    """
    if not item_classes:
        return True  # 空分类 = 适合所有角色
    if not character_class:
        return False  # 角色类型未知时不能匹配具体分类
    return character_class in item_classes


def should_buy(
    item: ShopItemEntry,
    character_class: str | None,
    bought_effects: set[str] | None = None,
) -> bool:
    """商品是否值得买：
    1. class_matches(item.classes, character_class) → True
    2. item.priority <= MAX_BUY_PRIORITY (5) → 排除 99（未手填）
    3. effect 不在 bought_effects（已买过的不再买）
    """
    if not class_matches(item.classes, character_class):
        return False
    if item.priority > MAX_BUY_PRIORITY:
        return False
    if bought_effects and item.effect and item.effect in bought_effects:
        return False
    return True


def filter_buyable(
    items: list[ShopItemEntry],
    character_class: str | None,
    bought_effects: set[str] | None = None,
) -> list[ShopItemEntry]:
    """筛选可买的商品（按 priority 升序）。返回新 list，不改原。"""
    buyable = [it for it in items if should_buy(it, character_class, bought_effects)]
    # priority 升序（小=优先）；同 priority 保持原顺序（稳定排序）
    return sorted(buyable, key=lambda it: it.priority)
