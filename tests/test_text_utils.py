import unittest

from starsavior_trainer.text_utils import (
    _ocr_int_token_to_int,
    contains_any_text,
    extract_character_name,
    normalize_ocr_text,
    parse_attribute_value,
    parse_first_int,
    parse_percent,
    parse_rank_number,
)


class TextUtilsTest(unittest.TestCase):
    def test_normalize_fullwidth_punctuation(self) -> None:
        self.assertEqual(normalize_ocr_text("％"), "%")
        self.assertEqual(normalize_ocr_text("　，"), ",")  # 全角空格→空格、全角逗号→,、再 strip
        self.assertEqual(normalize_ocr_text("  AbC  "), "abc")

    def test_contains_any_text_matches_substring(self) -> None:
        self.assertTrue(contains_any_text("力量训练", ["力量"]))
        self.assertFalse(contains_any_text("体力训练", ["力量"]))

    def test_ocr_int_token_translates_ocr_chars(self) -> None:
        self.assertEqual(_ocr_int_token_to_int("o1l"), 11)  # o→0 l→1 → "011"
        self.assertEqual(_ocr_int_token_to_int("olis"), 115)  # → "0115"
        self.assertEqual(_ocr_int_token_to_int("1,200"), 1200)  # 逗号去掉

    def test_parse_first_int_tolerates_ocr_chars(self) -> None:
        self.assertEqual(parse_first_int("speed l2"), 12)  # l→1
        self.assertEqual(parse_first_int("no number here"), None)

    def test_parse_rank_number_keeps_leading_one_vs_first_int(self) -> None:
        # 坑 #25: RANK17 数字贴着字母 RANK。parse_first_int 的负向守卫丢前导 1 读成 7；
        # parse_rank_number 不守卫相邻字母，正确读 17。
        self.assertEqual(parse_rank_number("RANK17"), 17)
        self.assertEqual(parse_first_int("RANK17"), 7)

    def test_parse_percent(self) -> None:
        self.assertEqual(parse_percent("12%"), 12)
        self.assertEqual(parse_percent("失败率 3o%"), 30)  # o→0

    def test_extract_character_name_rightmost_cjk_run(self) -> None:
        self.assertEqual(extract_character_name("双9 康 克莱儿"), "克莱儿")

    def test_parse_attribute_value(self) -> None:
        self.assertEqual(parse_attribute_value("力量 +12"), ("power", 12))
        self.assertEqual(parse_attribute_value("no number"), None)


if __name__ == "__main__":
    unittest.main()
