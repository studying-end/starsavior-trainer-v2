import unittest

from starsavior_trainer.inspectors.blessing_inspector import BlessingChoiceInspector
from starsavior_trainer.inspectors.commission_inspector import CommissionInspector
from starsavior_trainer.inspectors.shop_inspector import ShopInspector
from starsavior_trainer.inspectors.training_inspector import TrainingInspector, decide_early_training
from starsavior_trainer.models import (
    BlessingChoice,
    BlessingOption,
    CommissionChoice,
    CommissionOption,
    GameState,
    Rect,
    ShopItem,
    ShopScene,
    TrainingChoice,
)


class TrainingInspectorTest(unittest.TestCase):
    def test_inspects_first_unseen_candidate(self) -> None:
        insp = TrainingInspector()
        choices = [
            TrainingChoice("power", 0, "none", None, Rect(100, 100, 50, 50)),
            TrainingChoice("stamina", 0, "none", None, Rect(200, 100, 50, 50)),
        ]

        action = insp.decide(choices)

        self.assertIsNotNone(action)
        self.assertEqual(action.target, choices[0].target)  # inspect power first

    def test_bails_to_rest_when_fail_rate_too_high(self) -> None:
        # 坑 #24: 任一失败率≥阈值立即放弃其余去休息
        insp = TrainingInspector()
        insp.pending = "power"  # 模拟上帧点了 power
        choices = [
            TrainingChoice("power", 20, "none", 50, Rect(100, 100, 50, 50), selected=True),  # fail 50>=30
            TrainingChoice("stamina", 0, "none", None, Rect(200, 100, 50, 50)),
        ]

        action = insp.decide(choices)

        self.assertIsNone(action)  # 放弃, 回落 policy 去 rest


class DecideEarlyTrainingTest(unittest.TestCase):
    def test_picks_most_heads(self) -> None:
        # 当前帧 (0,0,2,1,0) → 韧性 guts(2 头最多)
        self.assertEqual(decide_early_training({"power": 0, "stamina": 0, "guts": 2, "wisdom": 1, "speed": 0}), "guts")

    def test_rests_when_all_le_one(self) -> None:
        # 全<=1 → None(去住处休息回心情)
        self.assertIsNone(decide_early_training({"power": 1, "stamina": 1, "guts": 1, "wisdom": 0, "speed": 0}))
        self.assertIsNone(decide_early_training({"power": 0, "stamina": 0, "guts": 0, "wisdom": 0, "speed": 0}))

    def test_tiebreak_order(self) -> None:
        # 平局按 力量>体力>韧性>专注>保护
        self.assertEqual(decide_early_training({"power": 2, "stamina": 2, "guts": 0, "wisdom": 0, "speed": 0}), "power")
        self.assertEqual(decide_early_training({"power": 0, "stamina": 0, "guts": 3, "wisdom": 3, "speed": 0}), "guts")


class CommissionInspectorTest(unittest.TestCase):
    def test_character_rank_read_from_choice_decoupled(self) -> None:
        # 坑 #39: character_rank 直接从委托界面读, 不依赖先经训练大厅
        insp = CommissionInspector()
        choice = CommissionChoice(
            options=[
                CommissionOption("低阶", "I", False, Rect(0, 0, 10, 10)),
                CommissionOption("高阶", "III", False, Rect(20, 0, 10, 10)),
            ],
            character_rank=21,
        )

        action = insp.decide(choice)

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "click")  # inspect first unseen commission


class ShopInspectorTest(unittest.TestCase):
    def test_inspects_each_item_by_clicking(self) -> None:
        insp = ShopInspector()
        scene = ShopScene(
            items=(
                ShopItem("a", 0, Rect(0, 0, 10, 10)),
                ShopItem("b", 0, Rect(20, 0, 10, 10)),
            ),
        )

        action = insp.decide(scene, policy=None)

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "click")  # inspect item #1


class BlessingInspectorTest(unittest.TestCase):
    def test_inspects_equal_value_candidates(self) -> None:
        insp = BlessingChoiceInspector(blessing_attribute_by_profile={"balanced": "power"})
        choice = BlessingChoice(
            options=[
                BlessingOption("p_30_a", "power", 30, Rect(100, 100, 50, 50)),
                BlessingOption("p_30_b", "power", 30, Rect(200, 100, 50, 50)),
            ],
        )

        action = insp.decide(choice, GameState(build_profile="balanced"))

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "click")  # inspect first equal-value card


class RestForMoodTest(unittest.TestCase):
    def test_rest_for_mood_picks_lodging_over_meditation(self) -> None:
        # 早期游戏回心情: 选住处(30) 而非冥想室(60)
        from starsavior_trainer.models import RestSubmenu
        from starsavior_trainer.policy.engine import TrainerPolicy

        policy = TrainerPolicy()
        policy._rest_for_mood = True
        rest = RestSubmenu(
            coins=100, has_meditation_room=True,
            meditation_room=Rect(0, 0, 1, 1), rough_sleep=Rect(1, 0, 1, 1),
            lodging=Rect(2, 0, 1, 1), confirm_button=None,
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.lodging)  # 住处, 不是冥想室
        self.assertFalse(policy._rest_for_mood)  # 标志已清

    def test_rest_for_mood_falls_back_when_poor(self) -> None:
        # 钱不够住处(30) → 露宿
        from starsavior_trainer.models import RestSubmenu
        from starsavior_trainer.policy.engine import TrainerPolicy

        policy = TrainerPolicy()
        policy._rest_for_mood = True
        rest = RestSubmenu(
            coins=10, has_meditation_room=False,
            meditation_room=None, rough_sleep=Rect(1, 0, 1, 1),
            lodging=Rect(2, 0, 1, 1), confirm_button=None,
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.rough_sleep)


if __name__ == "__main__":
    unittest.main()
