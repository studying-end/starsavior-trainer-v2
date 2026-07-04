import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.blessing import parse_blessing_choice, parse_blessing_setup


def _profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "blessing_confirm_button": Rect(1684, 1044, 290, 60),
            "blessing_auto_equip_button": Rect(1688, 976, 210, 52),
            "blessing_setup_anchor_title": Rect(0, 0, 100, 30),
            "blessing_slot_1": Rect(768, 584, 196, 196),
            "blessing_slot_2": Rect(1647, 337, 196, 196),
            "blessing_choice_anchor_archive": Rect(0, 0, 100, 30),
            "blessing_card_01": Rect(650, 420, 300, 100),
        },
    )


class BlessingParserTest(unittest.TestCase):
    def test_parse_blessing_setup_builds_two_slots(self) -> None:
        texts = [RegionText("blessing_setup_anchor_title", "旅程起点", 0.9)]

        payload = parse_blessing_setup(texts, _profile(), image=None)

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.slots), 2)
        self.assertFalse(payload.can_confirm)  # image=None → confirm 按钮非蓝

    def test_parse_blessing_setup_returns_none_without_buttons(self) -> None:
        self.assertIsNone(parse_blessing_setup([], RegionProfile("p", (2560, 1440), {})))

    def test_parse_blessing_choice_reads_card_attribute(self) -> None:
        texts = [
            RegionText("blessing_choice_anchor_archive", "星辰档案", 0.9),
            RegionText("blessing_card_01_attribute", "力量 30", 0.8),
        ]

        payload = parse_blessing_choice(texts, _profile(), image=None)

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.options), 1)
        self.assertEqual(payload.options[0].attribute, "power")
        self.assertEqual(payload.options[0].value, 30)


if __name__ == "__main__":
    unittest.main()
