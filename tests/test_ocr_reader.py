import unittest

from PIL import Image

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr import NoopOcrEngine
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.regions import RegionProfile


def _profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (100, 100),
        {
            "anchor_title": Rect(0, 0, 10, 10),
            "big_background": Rect(0, 0, 100, 100),  # 10000 像素，大区域
            "name_hero": Rect(20, 20, 10, 10),
        },
    )


class OcrReaderTest(unittest.TestCase):
    def test_read_all_returns_every_region(self) -> None:
        reader = RegionOcrReader(_profile(), NoopOcrEngine())

        results = reader.read_all(Image.new("RGB", (100, 100)))

        self.assertEqual({r.name for r in results}, {"anchor_title", "big_background", "name_hero"})

    def test_read_names_filters_to_requested(self) -> None:
        reader = RegionOcrReader(_profile(), NoopOcrEngine())

        results = reader.read_names(Image.new("RGB", (100, 100)), ["anchor_title"])

        self.assertEqual([r.name for r in results], ["anchor_title"])

    def test_max_area_filters_large_regions(self) -> None:
        reader = RegionOcrReader(_profile(), NoopOcrEngine())

        # big_background=10000 > 500 → 过滤掉；其余小区域保留。
        results = reader.read_all(Image.new("RGB", (100, 100)), max_area=500)

        names = {r.name for r in results}
        self.assertNotIn("big_background", names)
        self.assertIn("anchor_title", names)

    def test_read_ocr_regions_keeps_only_hinted_names(self) -> None:
        reader = RegionOcrReader(_profile(), NoopOcrEngine())

        results = reader.read_ocr_regions(Image.new("RGB", (100, 100)))

        # anchor_title(含 anchor)、name_hero(含 name) 是 OCR 区域；big_background 不是。
        names = {r.name for r in results}
        self.assertIn("anchor_title", names)
        self.assertIn("name_hero", names)
        self.assertNotIn("big_background", names)


if __name__ == "__main__":
    unittest.main()
