import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.simple import (
    parse_confirm_dialog,
    parse_dialogue_scene,
    parse_journey_start,
    parse_skill_select,
)


def _journey_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "journey_start_button": Rect(1542, 1078, 430, 60),
            "journey_start_arcana_slot_1": Rect(1124, 392, 130, 292),
            "journey_start_arcana_slot_2": Rect(1276, 430, 130, 292),
        },
    )


class SimpleParserTest(unittest.TestCase):
    def test_parse_journey_start_collects_arcana_slots(self) -> None:
        payload = parse_journey_start([], _journey_profile())

        self.assertIsNotNone(payload)
        self.assertEqual(payload.start_button, _journey_profile().regions["journey_start_button"])
        self.assertEqual(len(payload.arcana_slots), 2)

    def test_parse_journey_start_returns_none_without_button(self) -> None:
        self.assertIsNone(parse_journey_start([], RegionProfile("p", (2560, 1440), {})))

    def test_parse_confirm_dialog_reads_title_message(self) -> None:
        profile = RegionProfile(
            "p", (2560, 1440),
            {"confirm_dialog_confirm_button": Rect(1033, 753, 286, 60)},
        )
        texts = [
            RegionText("confirm_dialog_title", "确认", 0.9),
            RegionText("confirm_dialog_message", "开始旅程", 0.9),
        ]

        payload = parse_confirm_dialog(texts, profile)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.title, "确认")
        self.assertEqual(payload.message, "开始旅程")

    def test_parse_dialogue_scene_journey_hud(self) -> None:
        profile = RegionProfile(
            "p", (2560, 1440),
            {
                "dialogue_journey_skip_button": Rect(1484, 43, 62, 52),
                "dialogue_journey_text_area": Rect(100, 100, 800, 400),
            },
        )
        texts = [
            RegionText("dialogue_journey_event_label", "旅程事件", 0.9),
            RegionText("dialogue_journey_text_area", "某事件正文", 0.9),
        ]

        payload = parse_dialogue_scene(texts, profile)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.variant, "journey_hud")
        self.assertEqual(payload.skip_button, profile.regions["dialogue_journey_skip_button"])

    def test_parse_skill_select_builds_options(self) -> None:
        profile = RegionProfile(
            "p", (2560, 1440),
            {
                "skill_select_option_1_button": Rect(800, 400, 300, 80),
                "skill_select_option_2_button": Rect(800, 500, 300, 80),
            },
        )
        texts = [
            RegionText("skill_select_option_1_name", "攻击强化", 0.8),
            RegionText("skill_select_option_1_cost", "需要潜质 5", 0.8),
            RegionText("skill_select_option_2_name", "防御强化", 0.8),
        ]

        options = parse_skill_select(texts, profile)

        self.assertIsNotNone(options)
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0].name, "攻击强化")
        self.assertEqual(options[0].cost, 5)


if __name__ == "__main__":
    unittest.main()
