"""§22.13 潜质学习贪心决策测试。

覆盖 SkillLearnMixin.rank_skill_learn / next_skill_to_learn:
- 过滤: 未习得 + priority≤5 + 买得起
- 排序: priority 升序 → 同 priority 折扣降序 → 同折扣价格升序
- 买不起/已习得/priority 太低 → 不选
"""
import unittest

from starsavior_trainer.models import Rect, SkillLearnOption
from starsavior_trainer.policy.skill_learn import SkillLearnMixin, original_price_for_kind


class _DummyPolicy(SkillLearnMixin):
    pass


def _opt(name, price, original, priority, status="未习得") -> SkillLearnOption:
    return SkillLearnOption(
        name=name, price=price, original_price=original,
        priority=priority, status=status, target=Rect(1840, 400, 310, 90),
    )


class OriginalPriceTest(unittest.TestCase):
    def test_kind_prices(self) -> None:
        self.assertEqual(original_price_for_kind("感知"), 100)
        self.assertEqual(original_price_for_kind("技巧"), 200)
        self.assertEqual(original_price_for_kind("天赋"), 300)
        self.assertEqual(original_price_for_kind("通用"), 200)
        self.assertEqual(original_price_for_kind("未知"), 200)


class RankSkillLearnTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = _DummyPolicy()

    def test_priority_ascending(self) -> None:
        """priority 小的优先。p0 在 p2 之前。"""
        a = _opt("A", 50, 100, 2)
        b = _opt("B", 50, 100, 0)
        ranked = self.policy.rank_skill_learn([a, b], 100)
        self.assertEqual([o.name for o in ranked], ["B", "A"])

    def test_same_priority_discount_descending(self) -> None:
        """同 priority: 折扣大的优先(原价-现价)。
        A: 原价100 现价50 → 折扣50
        B: 原价100 现价80 → 折扣20
        → A 优先(省点数)。"""
        a = _opt("A", 50, 100, 1)
        b = _opt("B", 80, 100, 1)
        ranked = self.policy.rank_skill_learn([a, b], 100)
        self.assertEqual(ranked[0].name, "A")

    def test_filter_already_learned(self) -> None:
        """已习得的过滤掉。"""
        a = _opt("A", 50, 100, 0, status="已习得")
        b = _opt("B", 50, 100, 1, status="未习得")
        ranked = self.policy.rank_skill_learn([a, b], 100)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].name, "B")

    def test_filter_priority_too_high(self) -> None:
        """priority=99(不学)的过滤掉。"""
        a = _opt("A", 50, 100, 99)
        b = _opt("B", 50, 100, 3)
        ranked = self.policy.rank_skill_learn([a, b], 100)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].name, "B")

    def test_filter_cannot_afford(self) -> None:
        """买不起的(价格 > 点数)过滤掉。"""
        a = _opt("A", 50, 100, 0)
        b = _opt("B", 200, 200, 0)
        ranked = self.policy.rank_skill_learn([a, b], 100)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].name, "A")  # 50 买得起, 200 买不起

    def test_empty_when_all_unaffordable(self) -> None:
        """全部买不起 → 空列表(停止学习)。"""
        a = _opt("A", 200, 200, 0)
        ranked = self.policy.rank_skill_learn([a], 50)
        self.assertEqual(ranked, [])

    def test_no_target_filtered(self) -> None:
        """无 target(习得按钮)的过滤掉。"""
        a = SkillLearnOption(name="A", price=50, original_price=100, priority=0, status="未习得", target=None)
        ranked = self.policy.rank_skill_learn([a], 100)
        self.assertEqual(ranked, [])

    def test_next_returns_first_ranked(self) -> None:
        """next_skill_to_learn 返回排序后第一个。"""
        a = _opt("A", 50, 100, 2)
        b = _opt("B", 50, 100, 0)
        nxt = self.policy.next_skill_to_learn([a, b], 100)
        self.assertEqual(nxt.name, "B")

    def test_next_none_when_no_buyable(self) -> None:
        """无可学 → None。"""
        a = _opt("A", 200, 200, 0)
        self.assertIsNone(self.policy.next_skill_to_learn([a], 50))


if __name__ == "__main__":
    unittest.main()
