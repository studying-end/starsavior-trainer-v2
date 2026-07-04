import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.training import (
    _match_training_name,
    _parse_fail_rate,
    parse_training_select,
)


class TrainingParserTest(unittest.TestCase):
    def test_match_training_name(self) -> None:
        self.assertEqual(_match_training_name("力量训练"), "power")
        self.assertEqual(_match_training_name("速度"), "speed")
        self.assertIsNone(_match_training_name("未知词"))

    def test_parse_fail_rate_requires_percent_sign(self) -> None:
        # 坑 #24: 装饰数字不当失败率, 必须有 %；未显示返回 None（不是 0）
        self.assertEqual(_parse_fail_rate("30%"), 30)
        self.assertEqual(_parse_fail_rate("3o%"), 30)  # o→0 容错
        self.assertIsNone(_parse_fail_rate("30"))  # 无 % → None
        self.assertIsNone(_parse_fail_rate(""))

    def test_parse_training_select_marks_selected_by_fail_rate(self) -> None:
        # 坑 #24: 只有显示 fail_rate 的卡 selected; 未显示 fail_rate=None(绝不当 0% 赌博)
        profile = RegionProfile(
            "p",
            (2560, 1440),
            {
                "training_select_confirm_button": Rect(800, 1000, 200, 60),
                "training_select_card_power": Rect(200, 720, 220, 120),
                "training_select_card_speed": Rect(480, 720, 220, 120),
                "top_back_button": Rect(50, 50, 60, 60),
            },
        )
        texts = [
            RegionText("training_select_card_power_name", "力量训练", 0.8),
            RegionText("training_select_card_power_fail_rate", "12%", 0.8),
            RegionText("training_select_stat_gain_power", "+24", 0.8),
            RegionText("training_select_card_speed_name", "速度训练", 0.8),
            RegionText("training_select_stat_gain_speed", "+10", 0.8),
        ]

        choices = parse_training_select(texts, profile, image=None)

        self.assertIsNotNone(choices)
        power = next(c for c in choices if c.name == "power")
        self.assertTrue(power.selected)
        self.assertEqual(power.fail_rate, 12)
        self.assertEqual(power.stat_gain, 24)
        speed = next(c for c in choices if c.name == "speed")
        self.assertFalse(speed.selected)
        self.assertIsNone(speed.fail_rate)  # 坑 #24: None 不是 0


if __name__ == "__main__":
    unittest.main()
