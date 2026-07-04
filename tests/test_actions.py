import unittest

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens.commission import parse_commission_select
from starsavior_trainer.screens.event import parse_event_choice
from starsavior_trainer.screens.rest import parse_rest_submenu


def _rest_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "rest_submenu_option_1": Rect(900, 660, 240, 90),
            "rest_submenu_option_2": Rect(900, 780, 240, 90),
            "rest_submenu_option_3": Rect(900, 520, 240, 90),
            "rest_submenu_confirm_button": Rect(1200, 1000, 200, 60),
        },
    )


class RestParserTest(unittest.TestCase):
    def test_parse_rest_submenu_detects_meditation_by_label(self) -> None:
        texts = [
            RegionText("rest_submenu_coin_count", "80", 0.9),
            RegionText("rest_submenu_option_3_label", "冥想室", 0.8),
        ]

        payload = parse_rest_submenu(texts, _rest_profile())

        self.assertIsNotNone(payload)
        self.assertTrue(payload.has_meditation_room)
        self.assertEqual(payload.coins, 80)

    def test_parse_rest_submenu_returns_none_without_options(self) -> None:
        self.assertIsNone(parse_rest_submenu([], RegionProfile("p", (2560, 1440), {})))


def _event_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "event_choice_option_1": Rect(900, 480, 420, 70),
            "event_choice_option_2": Rect(900, 570, 420, 70),
        },
    )


class EventParserTest(unittest.TestCase):
    def test_parse_event_choice_builds_options(self) -> None:
        texts = [
            RegionText("event_choice_title", "旅程事件", 0.9),
            RegionText("event_choice_option_1_text", "速度 +12", 0.8),
            RegionText("event_choice_option_2_text", "体力回复", 0.8),
        ]

        options = parse_event_choice(texts, _event_profile())

        self.assertIsNotNone(options)
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0].text, "速度 +12")


def _commission_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "commission_select_option_1": Rect(760, 640, 320, 90),
            "commission_select_accept_button": Rect(1200, 1000, 200, 60),
        },
    )


class CommissionParserTest(unittest.TestCase):
    def test_parse_commission_reads_character_rank_from_screen(self) -> None:
        # 坑 #39: character_rank 直接从委托界面读, 不依赖先经过训练大厅
        texts = [
            RegionText("commission_select_option_1_name", "短期巡逻", 0.8),
            RegionText("commission_select_character_rank", "RANK 21", 0.8),
        ]

        payload = parse_commission_select(texts, _commission_profile(), image=None)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.character_rank, 21)


def _shop_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "shop_item_1": Rect(1380, 420, 160, 60),
            "shop_item_2": Rect(1380, 520, 160, 60),
            "shop_buy_button": Rect(1500, 1000, 200, 60),
        },
    )


class ShopParserTest(unittest.TestCase):
    def test_parse_shop_builds_items_and_reads_effect(self) -> None:
        from starsavior_trainer.screens.shop import parse_shop

        texts = [
            RegionText("shop_item_1_name", "体力药", 0.8),
            RegionText("shop_item_1_price", "75", 0.8),
            RegionText("shop_detail_effect", "回复体力", 0.8),
        ]

        payload = parse_shop(texts, _shop_profile(), image=None)

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.items), 2)
        self.assertEqual(payload.items[0].price, 75)
        self.assertEqual(payload.selected_effect, "回复体力")


def _region_move_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "region_move_destination_1": Rect(1800, 400, 300, 80),
            "region_move_go_button": Rect(1200, 1000, 200, 60),
        },
    )


class RegionMoveParserTest(unittest.TestCase):
    def test_returns_destination_when_no_go_text(self) -> None:
        from starsavior_trainer.screens.region_move import parse_region_move

        texts = [
            RegionText("region_move_anchor_title", "地区移动", 0.9),
            RegionText("region_move_station_title", "列车月台", 0.9),
        ]

        rect = parse_region_move(texts, _region_move_profile())

        self.assertEqual(rect, _region_move_profile().regions["region_move_destination_1"])

    def test_returns_go_button_when_go_present(self) -> None:
        from starsavior_trainer.screens.region_move import parse_region_move

        texts = [
            RegionText("region_move_anchor_title", "地区移动", 0.9),
            RegionText("region_move_station_title", "列车月台", 0.9),
            RegionText("region_move_go_button", "前往", 0.9),
        ]

        rect = parse_region_move(texts, _region_move_profile())

        self.assertEqual(rect, _region_move_profile().regions["region_move_go_button"])


def _battle_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "battle_skip_battle_button": Rect(1200, 800, 200, 60),
        },
    )


class BattleParserTest(unittest.TestCase):
    def test_parse_battle_skip_battle_button(self) -> None:
        from starsavior_trainer.screens.battle import parse_battle

        texts = [RegionText("battle_skip_battle_button", "跳过战斗", 0.9)]

        payload = parse_battle(texts, _battle_profile(), image=None)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.skip_button, _battle_profile().regions["battle_skip_battle_button"])
        self.assertFalse(payload.confirm_active)


if __name__ == "__main__":
    unittest.main()
