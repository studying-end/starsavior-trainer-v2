import unittest

from starsavior_trainer.models import (
    BlessingChoice,
    BlessingOption,
    CommissionChoice,
    CommissionOption,
    EventOption,
    GameState,
    Rect,
    RelicChoice,
    RelicOption,
    ShopItem,
    SkillOption,
)
from starsavior_trainer.policy.engine import TrainerPolicy


class BlessingDecisionTest(unittest.TestCase):
    def test_picks_highest_value_then_confirms_next_call(self) -> None:
        policy = TrainerPolicy()
        choice = BlessingChoice(
            options=[
                BlessingOption("p_30", "power", 30, Rect(650, 420, 100, 100)),
                BlessingOption("p_50", "power", 50, Rect(990, 420, 100, 100)),
            ],
            confirm_button=Rect(1684, 1044, 290, 60),
        )
        # 第一次：选最高值(50)
        a1 = policy.decide_blessing_choice(choice, GameState(build_profile="power_focus"))
        self.assertEqual(a1.target, choice.options[1].target)
        # 第二次：_pending_blessing 已设 → 确认
        a2 = policy.decide_blessing_choice(choice, GameState(build_profile="power_focus"))
        self.assertEqual(a2.target, choice.confirm_button)


class EventDecisionTest(unittest.TestCase):
    def test_keyword_heuristic_avoids_fatigue(self) -> None:
        policy = TrainerPolicy()
        options = [
            EventOption("消耗疲劳大量", Rect(900, 480, 200, 50)),
            EventOption("恢复体力", Rect(900, 570, 200, 50)),
        ]
        action = policy.decide_event(options, GameState(build_profile="balanced"))
        self.assertEqual(action.target, options[1].target)  # 避疲劳, 选恢复


class RelicDecisionTest(unittest.TestCase):
    def test_relic_choice_locks_first_pick_then_confirms(self) -> None:
        policy = TrainerPolicy()
        choice = RelicChoice(
            options=[
                RelicOption("relic_a", 12, Rect(390, 263, 384, 604)),
                RelicOption("relic_b", 15, Rect(832, 263, 384, 604)),
            ],
            confirm_button=Rect(863, 927, 322, 66),
        )
        a1 = policy.decide_relic_choice(choice)
        self.assertEqual(a1.target, choice.options[1].target)  # 分高
        self.assertEqual(policy._pending_relic, choice.options[1].target)


class CommissionDecisionTest(unittest.TestCase):
    def test_picks_red_text_suitable(self) -> None:
        policy = TrainerPolicy()
        choice = CommissionChoice(
            options=[
                CommissionOption("低阶", "I", True, Rect(760, 640, 320, 90)),  # red
                CommissionOption("高阶", "III", False, Rect(1120, 640, 320, 90)),
            ],
            accept_button=Rect(1200, 1000, 200, 60),
        )
        action = policy.decide_commission(choice, GameState(character_rank=21))
        self.assertEqual(action.target, choice.options[0].target)  # red 优先

    def test_picks_highest_doable_within_rank_plus_buffer(self) -> None:
        """rank 22 + 委托 17/19/24，buffer=3 → 上限 25 → 24≤25 选最高=24。
        用户实机场景：rank 22 时最高能打 rank 25，故 rank 24（超自己 2 级）应被选中。
        原逻辑 ≤ character_rank 漏掉 rank 24（24 > 22）→ 选 19，与用户预期不符。"""
        policy = TrainerPolicy()
        opt_low = CommissionOption("低阶", "RANK 17", False, Rect(760, 640, 320, 90))
        opt_mid = CommissionOption("中阶", "RANK 19", False, Rect(940, 640, 320, 90))
        opt_high = CommissionOption("高阶", "RANK 24", False, Rect(1120, 640, 320, 90))
        choice = CommissionChoice(
            options=[opt_low, opt_mid, opt_high],
            accept_button=Rect(1200, 1000, 200, 60),
        )
        # 第一次：选最高可做 rank 24 → 设 _pending_commission = opt_high.target
        action = policy.decide_commission(choice, GameState(character_rank=22))
        self.assertEqual(action.target, opt_high.target)
        self.assertEqual(policy._pending_commission, opt_high.target)
        # 第二次：_pending_commission 命中 → 点 accept_button 确认
        action2 = policy.decide_commission(choice, GameState(character_rank=22))
        self.assertEqual(action2.target, choice.accept_button)
        self.assertIsNone(policy._pending_commission)

    def test_falls_back_to_second_highest_when_all_exceed_limit(self) -> None:
        """全部委托建议等级都超 limit（character_rank+3）→ 退一阶取次高 rank。
        例：rank 22, 三委托 26/28/30 全 > 25 → 退一阶取次高 = 28。"""
        policy = TrainerPolicy()
        opt_a = CommissionOption("低阶", "RANK 26", False, Rect(760, 640, 320, 90))
        opt_b = CommissionOption("中阶", "RANK 28", False, Rect(940, 640, 320, 90))
        opt_c = CommissionOption("高阶", "RANK 30", False, Rect(1120, 640, 320, 90))
        choice = CommissionChoice(
            options=[opt_a, opt_b, opt_c],
            accept_button=Rect(1200, 1000, 200, 60),
        )
        action = policy.decide_commission(choice, GameState(character_rank=22))
        # 退一阶：rank 30 最高太硬，取次高 rank 28
        self.assertEqual(action.target, opt_b.target)


class ShopSkillDecisionTest(unittest.TestCase):
    def test_shop_buys_by_effect_keyword(self) -> None:
        policy = TrainerPolicy()
        items = [
            ShopItem("装饰", 40, Rect(1380, 420, 160, 60), effect=""),
            ShopItem("药水", 75, Rect(1380, 520, 160, 60), effect="回复体力 50"),
        ]
        action = policy.decide_shop(items)
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, items[1].target)

    def test_skill_score_already_learned_is_untrainable(self) -> None:
        policy = TrainerPolicy()
        opt = SkillOption("攻击强化", effect="已习得", cost=5, target=Rect(800, 400, 100, 50))
        self.assertEqual(policy.skill_score(opt, GameState(build_profile="balanced")), float("-inf"))


if __name__ == "__main__":
    unittest.main()
