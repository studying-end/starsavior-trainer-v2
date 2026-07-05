"""潜质学习决策 Mixin — 贪心算法按优先级+折扣买，买到买不起为止（§22.13）。

战斗模型(本次): 按 battle_priority 升序 + 同优先级按折扣(原价-现价)降序, 从高到低买,
当前点数 ≥ 价格才买, 钱不够跳过下一个, 全部买不起 → 停止。种马模型(第二步)用 breeding_priority。

== 原价规则(用户)==
- 感知: lv1=100（本次只学 lv1, 单一价格）
- 技巧: 200
- 天赋: 300
- 通用: 200
折扣 = 原价 - 现价(现价来自 OCR"习得"后数字)。同优先级折扣大的优先(省点数)。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import SkillLearnOption

# 类型原价（lv1，本次只学 lv1）
_KIND_ORIGINAL_PRICE = {
    "感知": 100,
    "技巧": 200,
    "天赋": 300,
    "通用": 200,
}


def original_price_for_kind(kind: str) -> int:
    """按类型返回原价（算折扣用）。未知类型按通用 200。"""
    return _KIND_ORIGINAL_PRICE.get(kind, 200)


class SkillLearnMixin:
    def rank_skill_learn(
        self,
        skills: Iterable[SkillLearnOption],
        potential_points: int,
    ) -> list[SkillLearnOption]:
        """贪心排序可学的潜质(§22.13)。

        过滤: status in (未习得, 升级) + priority ≤ 5 + 当前价 ≤ potential_points(买得起)。
        感知类可升 5 级(升级状态也学), 其它类只学 1 次(习得后满级不出现升级按钮)。
        排序: priority 升序 → 同 priority 按折扣(原价-现价)降序 → 同折扣按价格升序(省点数)。
        返回排序后的可学列表(空=全部买不起/无可学 → 停止学习)。
        """
        buyable = [
            s for s in skills
            if s.status in ("未习得", "升级")
            and s.priority <= 5
            and s.price is not None
            and s.price <= potential_points
            and s.target is not None
        ]
        # 排序: priority 升序 → 折扣(原价-现价)降序 → 价格升序
        # 折扣降序 = 折扣大的优先 = key 用 price-original(升序, 因为大折扣→小值)
        return sorted(
            buyable,
            key=lambda s: (
                s.priority,
                (s.price or 0) - (s.original_price or 0),  # 折扣大优先(折扣=orig-price, 降序=-升序的 price-orig)
                s.price or 0,
            ),
        )

    def next_skill_to_learn(
        self,
        skills: Iterable[SkillLearnOption],
        potential_points: int,
    ) -> SkillLearnOption | None:
        """贪心选下一个要学的潜质。None = 无可学(买不起/全已学/无匹配 priority)。"""
        ranked = self.rank_skill_learn(skills, potential_points)
        return ranked[0] if ranked else None
