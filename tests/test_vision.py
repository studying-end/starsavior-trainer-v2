import unittest

from PIL import Image

from starsavior_trainer.vision import (
    BlueButtonDetector,
    RingColorDetector,
    count_heads,
    detect_flash_training,
    estimate_endurance_ratio,
    _is_bond_maxed,
)
from starsavior_trainer.models import Rect


class VisionTest(unittest.TestCase):
    def test_ring_color_detector_finds_blue_region(self) -> None:
        image = Image.new("RGB", (50, 50), (20, 110, 240))

        signal = RingColorDetector().detect(image)

        self.assertEqual(signal.name, "blue")
        self.assertGreater(signal.confidence, 0.5)

    def test_count_heads_returns_zero_when_no_template_matches(self) -> None:
        # 空白图无头像模板能匹配 -> 0 (作数人头计数走 config/assets/N.png 新库模板匹配，N 为纯数字)
        blank = Image.new("RGB", (300, 300), (30, 30, 30))
        self.assertEqual(count_heads(blank, Rect(0, 0, 300, 300)), 0)

    def test_blue_button_detector_finds_enabled_button(self) -> None:
        image = Image.new("RGB", (100, 40), (45, 140, 225))

        signal = BlueButtonDetector().detect(image)

        self.assertEqual(signal.name, "active_blue")
        self.assertGreater(signal.confidence, 0.5)

    def test_estimate_endurance_ratio_partial_fill(self) -> None:
        # 100x10: 左 60 列绿色填充(训练资源耐力条) + 右 40 列暗绿底色 → ~0.6。
        img = Image.new("RGB", (100, 10))
        px = img.load()
        for y in range(10):
            for x in range(60):
                px[x, y] = (40, 150, 100)  # 填充绿（g 占优）
            for x in range(60, 100):
                px[x, y] = (62, 66, 50)  # 暗绿底色（饱和度低，不算填充）
        ratio = estimate_endurance_ratio(img, Rect(0, 0, 100, 10))
        self.assertAlmostEqual(ratio, 0.60, delta=0.03)

    def test_estimate_endurance_ratio_empty_bar_returns_zero(self) -> None:
        # 全底色无绿色填充 → 0.0（耐力空 or 非该画面）。
        img = Image.new("RGB", (100, 10), (62, 66, 50))
        self.assertEqual(estimate_endurance_ratio(img, Rect(0, 0, 100, 10)), 0.0)

    def test_estimate_endurance_ratio_full_bar_near_one(self) -> None:
        img = Image.new("RGB", (100, 10), (40, 150, 100))  # 全填充
        self.assertGreater(estimate_endurance_ratio(img, Rect(0, 0, 100, 10)), 0.95)

    def test_is_bond_maxed_yellow_bar_returns_true(self) -> None:
        # §22.5: 人头(100x100)下方进度条黄色(BGR 0,215,255) → 羁绊达标 True。
        import numpy as np
        img = np.zeros((150, 110, 3), dtype=np.uint8)
        img[105:120, 5:105] = (0, 215, 255)
        self.assertTrue(_is_bond_maxed(img, (0, 0), 100, 100))

    def test_is_bond_maxed_non_yellow_bar_returns_false(self) -> None:
        # 蓝/灰色进度条 → 未达标 False。
        import numpy as np
        img = np.zeros((150, 110, 3), dtype=np.uint8)
        img[105:120, 5:105] = (200, 100, 50)  # 蓝色
        self.assertFalse(_is_bond_maxed(img, (0, 0), 100, 100))

    def test_detect_flash_training_golden_button(self) -> None:
        # §22.6: 金黄按钮 RGB(180,160,90) R-B=90 → 闪光 True。
        import numpy as np
        arr = np.full((40, 100, 3), [180, 160, 90], dtype=np.uint8)
        self.assertTrue(detect_flash_training(Image.fromarray(arr, "RGB"), Rect(0, 0, 100, 40)))

    def test_detect_flash_training_gray_button_returns_false(self) -> None:
        # 灰白按钮 RGB(200,200,200) R-B=0 → 非闪光。
        import numpy as np
        arr = np.full((40, 100, 3), [200, 200, 200], dtype=np.uint8)
        self.assertFalse(detect_flash_training(Image.fromarray(arr, "RGB"), Rect(0, 0, 100, 40)))

    def test_blue_button_detector_ignores_grey_button(self) -> None:
        image = Image.new("RGB", (100, 40), (70, 70, 70))

        signal = BlueButtonDetector().detect(image)

        self.assertEqual(signal.name, "inactive")


if __name__ == "__main__":
    unittest.main()
