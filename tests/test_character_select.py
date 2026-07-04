import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.character_select import (
    _match_character_variants,
    _normalize_variant,
    parse_character_select,
)


def _profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "character_select_button": Rect(1629, 1046, 357, 58),
            "character_select_anchor_title": Rect(0, 0, 100, 30),
            "character_selected_name": Rect(100, 100, 200, 40),
            "character_option_1": Rect(1620, 202, 366, 96),
            "character_option_2": Rect(1620, 318, 366, 96),
        },
    )


class CharacterSelectParserTest(unittest.TestCase):
    def test_normalize_variant_tolerates_ocr_noise(self) -> None:
        self.assertEqual(_normalize_variant("ANOTHER"), "ANOTHER")
        self.assertEqual(_normalize_variant("an0ther"), "ANOTHER")  # 0↔O 混淆
        self.assertEqual(_normalize_variant("COSMIC"), "COSMIC")
        self.assertEqual(_normalize_variant("普通"), "")

    def test_match_character_variants_attaches_to_row_above(self) -> None:
        # 名字行 y=100；形态 token 在 y=130（正下方 30，落在 [15,70] 内）→ ANOTHER。
        variants = _match_character_variants(
            [("贝尔", 100)], [("an0ther", 130)]
        )
        self.assertEqual(variants, ["ANOTHER"])

    def test_match_character_variants_empty_when_no_token_below(self) -> None:
        variants = _match_character_variants([("贝尔", 100)], [])
        self.assertEqual(variants, [""])

    def test_parse_character_select_builds_options(self) -> None:
        texts = [
            RegionText("character_select_anchor_title", "旅程起点", 0.9),
            RegionText("character_selected_name", "克莱儿", 0.9),
            RegionText("character_option_1", "双9 康 贝尔", 0.8),
            RegionText("character_option_2", "A2 夏尔", 0.8),
        ]

        payload = parse_character_select(texts, _profile())

        self.assertIsNotNone(payload)
        names = [o.name for o in payload.options]
        self.assertIn("贝尔", names)
        self.assertIn("夏尔", names)
        self.assertEqual(payload.selected_name, "克莱儿")

    def test_parse_character_select_returns_none_without_confirm_button(self) -> None:
        profile = RegionProfile("p", (2560, 1440), {"character_select_anchor_title": Rect(0, 0, 10, 10)})

        self.assertIsNone(parse_character_select(
            [RegionText("character_select_anchor_title", "旅程起点", 0.9)], profile
        ))


if __name__ == "__main__":
    unittest.main()
