"""Tests for cli.blue_parsers — OCR-mode dispatch (HANDLERS) + blue-mode builders.

OCR 模式走 screens.HANDLERS；blue 模式走本地 _BLUE_PARSERS 表（纯颜色无 OCR）。
"""
import unittest
from PIL import Image

from starsavior_trainer.cli.blue_parsers import (
    _BLUE_PARSERS,
    _read_screen_payload_blue,
    _read_screen_payload_ocr,
)
from starsavior_trainer.models import Rect, Screen, TrainingHubStatus
from starsavior_trainer.ocr import NoopOcrEngine
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.vision import BlueButtonDetector


def _profile(regions: dict[str, Rect]) -> RegionProfile:
    return RegionProfile(name="test", resolution=(200, 200), regions=regions)


def _hub_profile() -> RegionProfile:
    return _profile(
        {
            "training_hub_action_training": Rect(10, 10, 20, 20),
            "training_hub_action_commission": Rect(40, 10, 20, 20),
            "training_hub_action_rest": Rect(70, 10, 20, 20),
            "training_hub_nav_potential": Rect(100, 10, 20, 20),
            "training_hub_action_shop": Rect(130, 10, 20, 20),
            # alert rects intentionally absent → has_*_alert stays False (no crop)
        }
    )


class BlueParsersRegistryTest(unittest.TestCase):
    def test_registry_covers_expected_screens(self) -> None:
        # 9 builders: the complex screens needing a color-only payload.
        self.assertEqual(len(_BLUE_PARSERS), 9)
        for screen in (
            Screen.TRAINING_HUB,
            Screen.TRAINING_SELECT,
            Screen.REST_SUBMENU,
            Screen.COMMISSION_SELECT,
            Screen.RELIC_CHOICE,
            Screen.SHOP,
            Screen.EVENT_CHOICE,
            Screen.DIALOGUE,
            Screen.BATTLE,
        ):
            self.assertIn(screen, _BLUE_PARSERS, screen)


class ReadPayloadBlueTest(unittest.TestCase):
    def test_simple_screen_needs_no_payload(self) -> None:
        # INITIAL isn't in _BLUE_PARSERS → policy clicks a fixed button, no payload.
        image = Image.new("RGB", (200, 200))
        self.assertIsNone(
            _read_screen_payload_blue(Screen.INITIAL, image, _hub_profile(), BlueButtonDetector(), False)
        )

    def test_shop_skips_without_ocr(self) -> None:
        # Shop needs item names/prices → can't read without OCR → None.
        image = Image.new("RGB", (200, 200))
        self.assertIsNone(
            _read_screen_payload_blue(Screen.SHOP, image, _hub_profile(), BlueButtonDetector(), False)
        )

    def test_training_hub_builds_status_from_regions(self) -> None:
        # No alert rects in profile → both alerts False; buttons lifted from regions.
        image = Image.new("RGB", (200, 200))
        payload = _read_screen_payload_blue(
            Screen.TRAINING_HUB, image, _hub_profile(), BlueButtonDetector(), False
        )

        self.assertIsInstance(payload, TrainingHubStatus)
        assert payload is not None  # for type checkers
        self.assertEqual(payload.training_button, Rect(10, 10, 20, 20))
        self.assertEqual(payload.shop_button, Rect(130, 10, 20, 20))
        self.assertFalse(payload.has_commission_alert)
        self.assertFalse(payload.has_shop_alert)


class ReadPayloadOcrTest(unittest.TestCase):
    def test_screen_with_no_ocr_prefixes_returns_none(self) -> None:
        # INITIAL's handler declares ocr_prefixes=None → no OCR payload needed.
        image = Image.new("RGB", (200, 200))
        reader = RegionOcrReader(_hub_profile(), NoopOcrEngine())
        self.assertIsNone(_read_screen_payload_ocr(Screen.INITIAL, image, _hub_profile(), reader, False))


if __name__ == "__main__":
    unittest.main()
