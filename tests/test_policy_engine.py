import unittest

from starsavior_trainer.models import GameState, Observation, Rect, Screen, TrainingChoice
from starsavior_trainer.policy.config import PolicyConfig
from starsavior_trainer.policy.event_db import _event_recommended_index, _match_event
from starsavior_trainer.policy.engine import TrainerPolicy


class PolicyConfigTest(unittest.TestCase):
    def test_defaults(self) -> None:
        c = PolicyConfig()
        self.assertEqual(c.min_screen_confidence, 0.65)  # §22.19 0.75→0.65
        self.assertEqual(c.max_training_fail_rate, 30)
        self.assertEqual(c.ring_bonus["rainbow"], 40)
        self.assertEqual(c.early_ring_multiplier, 2.5)


class EventDbTest(unittest.TestCase):
    def test_match_event_fuzzy(self) -> None:
        events = [{"title": "迷路的猫", "aliases": ["迷路猫"]}]
        self.assertIsNotNone(_match_event("迷路的猫", events))
        self.assertIsNone(_match_event("完全不同", events))

    def test_event_recommended_index_profile_then_default(self) -> None:
        event = {
            "default_rules": [
                {"profile": "power_focus", "choose_option": 2},
                {"profile": "default", "choose_option": 1},
            ]
        }
        self.assertEqual(_event_recommended_index(event, "power_focus"), 2)
        self.assertEqual(_event_recommended_index(event, "balanced"), 1)


class TrainerPolicyTest(unittest.TestCase):
    def test_training_score_fail_rate_none_is_untrainable(self) -> None:
        # 坑 #24: fail_rate None(未选中卡) → -inf, 绝不赌博
        policy = TrainerPolicy()
        choice = TrainingChoice("power", 30, "none", None, Rect(0, 0, 10, 10))
        self.assertEqual(policy.training_score(choice), float("-inf"))

    def test_training_score_over_threshold_untrainable(self) -> None:
        policy = TrainerPolicy()
        choice = TrainingChoice("power", 30, "none", 50, Rect(0, 0, 10, 10))  # 50 > 30
        self.assertEqual(policy.training_score(choice), float("-inf"))

    def test_training_score_normal_balanced(self) -> None:
        policy = TrainerPolicy()
        # fail=10→penalty 15, stat_gain=20, ring=none→0, bias balanced={}, no round
        choice = TrainingChoice("power", 20, "none", 10, Rect(0, 0, 10, 10))
        state = GameState(build_profile="balanced")
        self.assertEqual(policy.training_score(choice, state), 5)

    def test_fail_rate_threshold_dynamic_by_gain(self) -> None:
        # §22.4: 失败率上限随 gain 线性放宽 — max_fail = min(99, 10 + 0.5×gain)
        policy = TrainerPolicy()
        r = Rect(0, 0, 10, 10)
        # gain=20 → max 20%: fail 20 可训, 21 → -inf（普通训练保守上限）
        self.assertNotEqual(policy.training_score(TrainingChoice("power", 20, "none", 20, r)), float("-inf"))
        self.assertEqual(policy.training_score(TrainingChoice("power", 20, "none", 21, r)), float("-inf"))
        # gain=50 → max 35%; gain=60 → max 40%（用户数据点）
        self.assertNotEqual(policy.training_score(TrainingChoice("power", 50, "none", 35, r)), float("-inf"))
        self.assertEqual(policy.training_score(TrainingChoice("power", 50, "none", 36, r)), float("-inf"))
        self.assertNotEqual(policy.training_score(TrainingChoice("power", 60, "none", 40, r)), float("-inf"))
        # gain=100 → max 60%
        self.assertEqual(policy.training_score(TrainingChoice("power", 100, "none", 61, r)), float("-inf"))
        # gain=200 → max 99% (cap, 高 gain 几乎必赌)
        self.assertNotEqual(policy.training_score(TrainingChoice("power", 200, "none", 99, r)), float("-inf"))

    def test_decide_low_confidence_pauses(self) -> None:
        policy = TrainerPolicy()
        obs = Observation(Screen.TRAINING_HUB, 0.5)  # < 0.65
        self.assertEqual(policy.decide(GameState(), obs).kind, "pause")

    def test_decide_unknown_screen_pauses_when_no_handler(self) -> None:
        # HANDLERS 尚未注册(T13) → handler None → pause
        policy = TrainerPolicy()
        obs = Observation(Screen.UNKNOWN, 0.9)
        self.assertEqual(policy.decide(GameState(), obs).kind, "pause")

    def test_leaving_screen_clears_pending_state(self) -> None:
        # _pending_X 状态机: 离开该 screen 时清状态(防跨画面残留)
        policy = TrainerPolicy()
        policy._pending_relic = Rect(0, 0, 10, 10)
        policy.decide(GameState(), Observation(Screen.UNKNOWN, 0.9))
        self.assertIsNone(policy._pending_relic)


if __name__ == "__main__":
    unittest.main()
