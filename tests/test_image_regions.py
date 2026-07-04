import unittest

from PIL import Image

from starsavior_trainer.image_regions import crop_region, draw_region_overlay
from starsavior_trainer.models import Rect
from starsavior_trainer.regions import RegionProfile


class ImageRegionsTest(unittest.TestCase):
    def test_crop_region_returns_subimage(self) -> None:
        image = Image.new("RGB", (100, 100), (255, 0, 0))

        cropped = crop_region(image, Rect(10, 20, 30, 40))

        self.assertEqual(cropped.size, (30, 40))

    def test_draw_region_overlay_does_not_mutate_original(self) -> None:
        profile = RegionProfile("p", (100, 100), {"a": Rect(5, 5, 10, 10)})
        image = Image.new("RGB", (100, 100), (0, 0, 0))

        overlay = draw_region_overlay(image, profile)

        self.assertIsNot(overlay, image)
        self.assertEqual(overlay.size, (100, 100))
        # original image untouched (overlay is a copy)
        self.assertEqual(image.getpixel((6, 6)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
