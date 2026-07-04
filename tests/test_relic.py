import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.relic import (
    _has_relic_choice_anchor,
    _relic_attribute_from_name,
    parse_relic_choice,
    parse_relic_name,
)


class RelicParserTest(unittest.TestCase):
    def test_parse_relic_name_matches_distinctive_word(self) -> None:
        # 坑 #28: 高亮卡名 OCR 乱码, 只匹配独特词"布谷鸟"
        self.assertEqual(parse_relic_name("烦人的布谷鸟时钟"), "annoying_cuckoo_clock")
        self.assertEqual(parse_relic_name("布谷鸟"), "annoying_cuckoo_clock")
        self.assertEqual(parse_relic_name("软绵绵的玩偶朋友"), "soft_toy_friend")

    def test_parse_relic_name_keeps_unknown_cleaned(self) -> None:
        self.assertEqual(parse_relic_name("某未知遗物"), "某未知遗物")
        self.assertIsNone(parse_relic_name(""))

    def test_relic_attribute_from_part_name(self) -> None:
        self.assertEqual(_relic_attribute_from_name("力量手套"), "attack")
        self.assertEqual(_relic_attribute_from_name("疾风鞋子"), "speed")
        self.assertIsNone(_relic_attribute_from_name("无名物品"))

    def test_has_relic_choice_anchor(self) -> None:
        self.assertTrue(_has_relic_choice_anchor({"relic_choice_title": "选择奖励"}))
        self.assertFalse(_has_relic_choice_anchor({"relic_choice_title": "别的标题"}))

    def test_parse_relic_choice_builds_options(self) -> None:
        profile = RegionProfile(
            "p",
            (2560, 1440),
            {
                "relic_choice_card_1": Rect(390, 263, 384, 604),
                "relic_choice_card_2": Rect(832, 263, 384, 604),
                "relic_choice_confirm_button": Rect(863, 927, 322, 66),
            },
        )
        texts = [
            RegionText("relic_choice_title", "选择奖励", 0.9),
            RegionText("relic_choice_card_1_name", "烦人的布谷鸟时钟", 0.8),
            RegionText("relic_choice_card_1_score", "12", 0.8),
            RegionText("relic_choice_card_2_name", "软绵绵的玩偶朋友", 0.8),
            RegionText("relic_choice_card_2_score", "12", 0.8),
        ]

        payload = parse_relic_choice(texts, profile, image=None)

        self.assertIsNotNone(payload)
        names = [o.name for o in payload.options]
        self.assertIn("annoying_cuckoo_clock", names)
        self.assertIn("soft_toy_friend", names)
        # 仅 2 张卡(缺 balanced_scale)→ 非首轮 → fixed_name=None
        self.assertIsNone(payload.fixed_name)


if __name__ == "__main__":
    unittest.main()
