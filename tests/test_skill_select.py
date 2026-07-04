"""Tests for SKILL_SELECT decision (坑 #35) — 学最优技能而非点✕退出。

_decide_skill_select 直接测试：test_screens_registry 的 setUp/tearDown 会 clear 全局
HANDLERS，故不依赖注册表状态，直接调被测函数。skill_score 验「已习得跳过 + 关键词评分」。
"""
import unittest

from starsavior_trainer.models import GameState, Observation, Rect, Screen, SkillOption
from starsavior_trainer.policy.engine import TrainerPolicy
from starsavior_trainer.screens import _decide_skill_select


class SkillSelectDecisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = TrainerPolicy()
        # power_focus keywords: 攻击/力量/attack/power
        self.state = GameState(build_profile="power_focus")
        self.close = self.policy.config.skill_select_close_button

    def _obs(self, payload) -> Observation:
        return Observation(screen=Screen.SKILL_SELECT, confidence=1.0, payload=payload)

    def test_learns_best_skill_not_exit(self) -> None:
        # 有可学技能：按 profile 选最优（攻击匹配 power_focus），不点✕退出。
        best = SkillOption(name="攻击强化", effect="攻击力提升", cost=20, target=Rect(100, 100, 50, 50))
        weak = SkillOption(name="杂项", effect="无", cost=10, target=Rect(200, 200, 50, 50))

        action = _decide_skill_select(self._obs([best, weak]), self.state, self.policy)

        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, best.target)  # 选最优，非 close

    def test_all_learned_falls_back_to_exit(self) -> None:
        # 全部已习得（skill_score -inf）→ decide_skill 返 pause → 转✕退出，不卡死。
        learned = SkillOption(name="攻击强化", effect="已习得", cost=20, target=Rect(100, 100, 50, 50))

        action = _decide_skill_select(self._obs([learned]), self.state, self.policy)

        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, self.close)

    def test_no_payload_exits(self) -> None:
        # payload 非 SkillOption 列表 → 直接✕退出。
        action = _decide_skill_select(self._obs(None), self.state, self.policy)

        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, self.close)


class SkillScoreTest(unittest.TestCase):
    def test_learned_skill_scores_neg_inf(self) -> None:
        policy = TrainerPolicy()
        state = GameState(build_profile="balanced")
        learned = SkillOption(name="攻击", effect="已习得", target=Rect(0, 0, 10, 10))
        self.assertEqual(policy.skill_score(learned, state), float("-inf"))

    def test_keyword_match_beats_no_match(self) -> None:
        policy = TrainerPolicy()
        state = GameState(build_profile="power_focus")
        matched = SkillOption(name="攻击强化", target=Rect(0, 0, 10, 10))
        unmatched = SkillOption(name="杂项", target=Rect(0, 0, 10, 10))
        self.assertGreater(policy.skill_score(matched, state), policy.skill_score(unmatched, state))


if __name__ == "__main__":
    unittest.main()
