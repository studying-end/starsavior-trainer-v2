import json
import tempfile
import unittest

from starsavior_trainer.manifest import load_manifest
from starsavior_trainer.models import Rect
from starsavior_trainer.regions import (
    RegionProfile,
    load_region_profile,
    scale_region_profile,
)


def _write_json(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return f.name


class RegionsTest(unittest.TestCase):
    def test_rect_center(self) -> None:
        self.assertEqual(Rect(10, 20, 30, 40).center, (25, 40))

    def test_scale_region_profile_scales_rectangles_to_image_size(self) -> None:
        profile = RegionProfile("base", (2560, 1440), {"button": Rect(1280, 720, 256, 144)})

        scaled = scale_region_profile(profile, (1280, 720))

        self.assertEqual(scaled.resolution, (1280, 720))
        self.assertEqual(scaled.regions["button"], Rect(640, 360, 128, 72))

    def test_scale_region_profile_returns_original_for_same_size(self) -> None:
        profile = RegionProfile("base", (2560, 1440), {"button": Rect(1280, 720, 256, 144)})

        self.assertIs(scale_region_profile(profile, (2560, 1440)), profile)

    def test_load_region_profile_parses_json(self) -> None:
        path = _write_json(
            {"name": "test", "resolution": [2560, 1440], "regions": {"btn": [10, 20, 100, 50]}}
        )

        profile = load_region_profile(path)

        self.assertEqual(profile.name, "test")
        self.assertEqual(profile.resolution, (2560, 1440))
        self.assertEqual(profile.regions["btn"], Rect(10, 20, 100, 50))

    def test_load_region_profile_rejects_bad_rect(self) -> None:
        path = _write_json(
            {"resolution": [2560, 1440], "regions": {"btn": [10, 20]}}
        )

        with self.assertRaises(ValueError):
            load_region_profile(path)

    def test_load_manifest_parses_state_and_frames(self) -> None:
        path = _write_json(
            {
                "state": {"current_rank": "B", "coins": 50},
                "frames": [
                    {"screen": "training_hub", "confidence": 0.9, "image": "f1.png"},
                    {"screen": "unknown"},
                ],
            }
        )

        state, observations = load_manifest(path)

        self.assertEqual(state.current_rank, "B")
        self.assertEqual(state.coins, 50)
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0].screen.value, "training_hub")
        self.assertEqual(observations[0].source, "f1.png")
        self.assertEqual(observations[1].screen.value, "unknown")


if __name__ == "__main__":
    unittest.main()
