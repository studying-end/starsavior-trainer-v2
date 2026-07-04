import unittest

from starsavior_trainer.models import (
    CharacterOption,
    CharacterSelect,
    GameState,
    Observation,
    Rect,
    Screen,
    TrainingChoice,
)
from starsavior_trainer.policy.engine import TrainerPolicy


def _character_selection() -> CharacterSelect:
    return CharacterSelect(
        options=[
            CharacterOption("贝尔", "A", 4, "focus", False, Rect(1620, 200, 366, 96)),
            CharacterOption("夏尔", "B", 4, "power", True, Rect(1620, 318, 366, 96)),
        ],
        confirm_button=Rect(1629, 1046, 357, 58),
        selected_name="夏尔",
    )


class CharacterSelectDecisionTest(unittest.TestCase):
    def test_confirms_when_desired_character_visible_and_selected(self) -> None:
        policy = TrainerPolicy()
        state = GameState(desired_character="夏尔")
        action = policy.decide_character_select(_character_selection(), state)
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, _character_selection().confirm_button)

    def test_pauses_when_desired_not_present_and_cannot_scroll(self) -> None:
        policy = TrainerPolicy()
        state = GameState(desired_character="不存在的角色")
        selection = CharacterSelect(
            options=[CharacterOption("贝尔", "A", 4, "focus", False, Rect(0, 0, 10, 10))],
            confirm_button=Rect(0, 0, 10, 10),
            can_scroll=False,
        )
        action = policy.decide_character_select(selection, state)
        self.assertEqual(action.kind, "pause")


class TrainingDecisionTest(unittest.TestCase):
    def test_selects_highest_score_card(self) -> None:
        policy = TrainerPolicy()
        choices = [
            TrainingChoice("power", 20, "none", 10, Rect(100, 100, 50, 50)),  # score 5
            TrainingChoice("speed", 30, "none", 5, Rect(200, 100, 50, 50)),   # fail 5→penalty 0; 30+0=30
        ]
        action = policy.decide_training(choices, GameState(build_profile="balanced"))
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, choices[1].target)  # speed 分数更高

    def test_all_fail_rates_too_high_returns_to_hub(self) -> None:
        policy = TrainerPolicy()
        choices = [
            TrainingChoice("power", 20, "none", 50, Rect(100, 100, 50, 50), back_button=Rect(50, 50, 30, 30)),
        ]
        action = policy.decide_training(choices, GameState(build_profile="balanced"))
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, choices[0].back_button)
        self.assertTrue(policy._needs_rest)

    def test_blue_mode_picks_best_ring_when_all_fail_rates_none(self) -> None:
        # blue 模式（无 OCR）: 全 fail_rate=None → engine.training_score 一律 -inf。
        # decide_training 应走 ring+bias 降级排序选 ring 最高的，不 pause/不死锁休息。
        policy = TrainerPolicy()
        choices = [
            TrainingChoice("power", 0, "none", None, Rect(100, 100, 50, 50)),
            TrainingChoice("speed", 0, "rainbow", None, Rect(200, 100, 50, 50)),
        ]
        action = policy.decide_training(choices, GameState(build_profile="balanced"))
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, choices[1].target)  # rainbow(40) > none(0)
        self.assertIn("blue mode", action.reason)
        self.assertFalse(policy._needs_rest)  # 不触发死锁休息

    def test_blue_mode_build_bias_breaks_ring_tie(self) -> None:
        # 两卡同 ring(none) → 按 build 属性偏好打破平局（power_focus → power）。
        policy = TrainerPolicy()
        choices = [
            TrainingChoice("power", 0, "none", None, Rect(100, 100, 50, 50)),
            TrainingChoice("speed", 0, "none", None, Rect(200, 100, 50, 50)),
        ]
        action = policy.decide_training(choices, GameState(build_profile="power_focus"))
        self.assertEqual(action.target, choices[0].target)  # power bias 18 打破平局

    def test_blue_mode_two_step_confirm_when_selected(self) -> None:
        # blue 模式两步流程: 已选中(selected) + 有 confirm_button → 点 confirm。
        policy = TrainerPolicy()
        confirm = Rect(500, 500, 60, 60)
        choices = [
            TrainingChoice("power", 0, "rainbow", None, Rect(100, 100, 50, 50), selected=True, confirm_button=confirm),
        ]
        action = policy.decide_training(choices, GameState(build_profile="balanced"))
        self.assertEqual(action.target, confirm)
        self.assertIn("confirm", action.reason)

    def test_partial_none_fail_rates_not_treated_as_blue(self) -> None:
        # 回归: 只要有一张卡 fail_rate 非 None（OCR 模式）就不走 blue 分支。
        policy = TrainerPolicy()
        choices = [
            TrainingChoice("power", 20, "none", 10, Rect(100, 100, 50, 50)),  # fail 10 非 None
            TrainingChoice("speed", 30, "none", None, Rect(200, 100, 50, 50)),
        ]
        action = policy.decide_training(choices, GameState(build_profile="balanced"))
        self.assertNotIn("blue mode", action.reason)


class SimpleDecisionTest(unittest.TestCase):
    def test_decide_dialogue_repeats_skip(self) -> None:
        from starsavior_trainer.models import DialogueScene
        policy = TrainerPolicy()
        dialogue = DialogueScene(skip_button=Rect(1900, 40, 100, 50), variant="intro")
        action = policy.decide_dialogue(dialogue)
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.repeat, 3)

    def test_decide_rest_picks_meditation_when_affordable(self) -> None:
        from starsavior_trainer.models import RestSubmenu
        policy = TrainerPolicy()
        rest = RestSubmenu(
            coins=80,
            has_meditation_room=True,
            meditation_room=Rect(900, 520, 240, 90),
            rough_sleep=Rect(900, 660, 240, 90),
            confirm_button=Rect(1200, 1000, 200, 60),
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, rest.meditation_room)

    def test_decide_rest_mood_not_best_picks_lodging(self) -> None:
        # §22.3: 心情≠BEST → 住处（回心情），即使耐力够。
        from starsavior_trainer.models import RestSubmenu
        policy = TrainerPolicy()
        policy._cached_mood = "NORMAL"
        policy._cached_endurance = 0.8
        rest = RestSubmenu(
            coins=100, has_meditation_room=True,
            meditation_room=Rect(1, 1, 1, 1), rough_sleep=Rect(2, 2, 1, 1), lodging=Rect(3, 3, 1, 1),
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.lodging)

    def test_decide_rest_best_low_endurance_rich_picks_meditation(self) -> None:
        # §22.3: 心情BEST + 耐力<40% + 有钱 → 冥想室。
        from starsavior_trainer.models import RestSubmenu
        policy = TrainerPolicy()
        policy._cached_mood = "BEST"
        policy._cached_endurance = 0.3
        rest = RestSubmenu(
            coins=100, has_meditation_room=True,
            meditation_room=Rect(1, 1, 1, 1), rough_sleep=Rect(2, 2, 1, 1),
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.meditation_room)

    def test_decide_rest_best_low_endurance_poor_picks_rough_sleep(self) -> None:
        # §22.3: 心情BEST + 耐力<40% + 没钱 → 露宿。
        from starsavior_trainer.models import RestSubmenu
        policy = TrainerPolicy()
        policy._cached_mood = "BEST"
        policy._cached_endurance = 0.3
        rest = RestSubmenu(
            coins=10, has_meditation_room=True,
            meditation_room=Rect(1, 1, 1, 1), rough_sleep=Rect(2, 2, 1, 1),
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.rough_sleep)

    def test_decide_rest_best_high_endurance_picks_rough_sleep(self) -> None:
        # §22.3: 心情BEST + 耐力≥40% → 露宿（免费默认）。
        from starsavior_trainer.models import RestSubmenu
        policy = TrainerPolicy()
        policy._cached_mood = "BEST"
        policy._cached_endurance = 0.8
        rest = RestSubmenu(
            coins=100, has_meditation_room=True,
            meditation_room=Rect(1, 1, 1, 1), rough_sleep=Rect(2, 2, 1, 1),
        )
        action = policy.decide_rest(rest)
        self.assertEqual(action.target, rest.rough_sleep)


if __name__ == "__main__":
    unittest.main()
