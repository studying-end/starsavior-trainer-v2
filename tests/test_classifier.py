"""画面分类器消歧测试 — 单屏状态机架构核心的回归保护。

迁移自旧项目 d:/chengfeng/tests/test_classifier.py。这些测试全是 _match_screen
的 payload 消歧用例，对应历史坑台账 A 类(1-11)中那些"X 画面被误判成 Y"的 bug:
每个用例喂一组真实 OCR 抖动过的 anchor 文本，断言分类到正确 Screen。

注: 旧文件另有 5 个视觉测试(test_visual_journey_origin_detects_* /
test_hybrid_visual_override_*)依赖 4 张真实截图(character_select_003 /
blessing_setup_empty_001 / blessing_setup_ready_001 / blessing_choice_002),
新旧项目均未入库 → 暂无法迁, 归 T18 subtask 2(真实 OCR/截图评估)范畴。
"""
import unittest

from PIL import Image

from starsavior_trainer.classifier import _has_real_event_options
from starsavior_trainer.classifier_anchors import _match_screen
from starsavior_trainer.classifier_signatures import (
    _has_game_menu_signature,
    _has_training_select_signature,
)
from starsavior_trainer.models import Screen
from starsavior_trainer.ocr import OcrResult
from starsavior_trainer.regions import load_region_profile


class ClassifierTest(unittest.TestCase):
    def test_initial_route_page_accepts_starsavior_title_with_start_button(self) -> None:
        screen, confidence = _match_screen(
            {
                "route_select_anchor_title": "StarSavior",
                "start_button": "开始",
            }
        )

        self.assertEqual(screen, Screen.INITIAL)
        self.assertGreaterEqual(confidence, 0.70)

    def test_reward_title_classifies_as_reward(self) -> None:
        screen, confidence = _match_screen({"reward_title": "获得奖励"})

        self.assertEqual(screen, Screen.REWARD)
        self.assertGreaterEqual(confidence, 0.70)

    def test_game_menu_popup_classifies_as_game_menu(self) -> None:
        # The accidental in-game 菜单 popup. Its top-left 菜单 title + centre 观测
        # menu items uniquely identify it, so the bot can click ✕ to close instead
        # of falling to "unknown → click centre" (which would hit 重新观测/观测结束
        # in the centre and restart or end the run).
        screen, confidence = _match_screen(
            {
                "game_menu_anchor_title": "菜单",
                "game_menu_observe_marker": "观测结束 重新观测",
            }
        )

        self.assertEqual(screen, Screen.GAME_MENU)
        self.assertGreaterEqual(confidence, 0.70)

    def test_game_menu_signature_needs_both_title_and_observe_marker(self) -> None:
        # Just the word 菜单 (other screens may show it) must NOT trigger the menu
        # screen — the 观测 menu-item marker is required so we don't false-positive.
        self.assertTrue(
            _has_game_menu_signature(
                {"game_menu_anchor_title": "菜单", "game_menu_observe_marker": "重新观测"}
            )
        )
        self.assertFalse(_has_game_menu_signature({"game_menu_anchor_title": "菜单"}))
        self.assertFalse(_has_game_menu_signature({}))

    def test_reward_signature_wins_over_character_select_旅程起点_overlap(self) -> None:
        # The 获得奖励 popup lands over the journey map, whose top-left can still
        # OCR as 旅程起点 (the character_select anchor text). Without the reward
        # signature this scored as character_select and stalled the scroll loop.
        screen, confidence = _match_screen(
            {
                "reward_title": "获得奖励",
                "character_select_anchor_title": "旅程起点",
            }
        )

        self.assertEqual(screen, Screen.REWARD)
        self.assertGreaterEqual(confidence, 0.70)

    def test_battle_anchor_wins_over_training_hub_participation_text(self) -> None:
        screen, confidence = _match_screen(
            {
                "training_hub_anchor_title": "参加评鉴战",
                "battle_title": "参加评鉴战",
                "battle_entry_button": "评鉴战 一般",
            }
        )

        self.assertEqual(screen, Screen.BATTLE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_battle_entry_and_accept_classify_as_battle(self) -> None:
        screen, confidence = _match_screen(
            {
                "battle_title": "参加评鉴战",
                "battle_entry_button": "评鉴战 一般",
                "battle_accept_button": "接受",
            }
        )

        self.assertEqual(screen, Screen.BATTLE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_commission_battle_confirm_classifies_as_battle(self) -> None:
        # 委托战斗确认界面("XX讨伐委托" + 跳过战斗/开始委托)和评鉴战确认同布局, 也该判 BATTLE
        # → 点跳过战斗。之前 title 只认"评鉴战"→ 委托被误判 event_fast_forward 死循环。
        screen, confidence = _match_screen(
            {
                "battle_skip_battle_button": "跳过战斗",
                "battle_confirm_title": "史莱姆讨伐委托",
            }
        )

        self.assertEqual(screen, Screen.BATTLE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_rating_battle_confirm_classifies_as_battle(self) -> None:
        # 基础评鉴战 entry confirm: a centred dialog whose battle regions (top-corner)
        # read empty, so classify_by_ocr is UNKNOWN and the blue-button fallback
        # misreads the 跳过战斗 blue button as event_fast_forward. The 跳过战斗 button +
        # 评鉴战 title give it a proper BATTLE signature instead.
        screen, confidence = _match_screen(
            {
                "battle_skip_battle_button": "跳过战斗",
                "battle_confirm_title": "基础评鉴战",
            }
        )

        self.assertEqual(screen, Screen.BATTLE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_training_hub_uses_action_buttons_not_generic_participation(self) -> None:
        screen, confidence = _match_screen(
            {
                "training_hub_anchor_title": "评鉴战",
                "training_hub_distance": "距离目标 6",
                "training_hub_action_training": "训练",
                "training_hub_action_commission": "委托",
                "training_hub_action_rest": "休息",
            }
        )

        self.assertEqual(screen, Screen.TRAINING_HUB)
        self.assertGreaterEqual(confidence, 0.70)

    def test_training_hub_recognizes_trade_and_shop_alert(self) -> None:
        screen, confidence = _match_screen(
            {
                "training_hub_action_shop": "交易",
                "training_hub_shop_alert": "全新商品到货！",
                "training_hub_nav_potential": "潜质",
            }
        )

        self.assertEqual(screen, Screen.TRAINING_HUB)
        self.assertGreaterEqual(confidence, 0.70)

    def test_training_select_full_card_text_wins_over_hub_overlap(self) -> None:
        screen, confidence = _match_screen(
            {
                "training_hub_action_training": "体力训练 Lv.1",
                "training_hub_action_rest": "保护训练 Lv.1",
                "training_select_card_power": "力量训练 Lv.1 失败率0%",
                "training_select_card_stamina": "体力训练 Lv.1",
            }
        )

        self.assertEqual(screen, Screen.TRAINING_SELECT)
        self.assertGreaterEqual(confidence, 0.70)

    def test_trading_shop_with_training_book_not_misclassified_as_training(self) -> None:
        # The D-DAY trading shop sells a "保护训练的秘笈" item whose name contains
        # 保护训练 — only ONE training-card region reads a training name. A real
        # training screen has all five (力量/体力/韧性/集中/保护训练). Requiring ≥2
        # stops the shop being mis-read as TRAINING_SELECT (which made the training
        # inspector loop forever clicking a non-existent training card).
        self.assertFalse(
            _has_training_select_signature({"training_select_card_wisdom": "3024 保护训练的秘笈"})
        )
        self.assertTrue(
            _has_training_select_signature(
                {
                    "training_select_card_power": "力量训练 Lv.3",
                    "training_select_card_stamina": "体力训练 Lv.1",
                }
            )
        )

    def test_train_station_classifies_as_region_move(self) -> None:
        # The 列车月台 region-move screen (地区移动 + 列车月台) was mis-scored as
        # relic_choice by the fallback and got stuck. Its two anchors uniquely
        # identify REGION_MOVE so the bot can pick a destination and travel.
        screen, confidence = _match_screen(
            {
                "region_move_anchor_title": "地区移动",
                "region_move_station_title": "列车月台",
            }
        )

        self.assertEqual(screen, Screen.REGION_MOVE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_rest_submenu_signature_wins_over_battle_overlap(self) -> None:
        screen, confidence = _match_screen(
            {
                "battle_title": "参加评鉴战",
                "battle_accept_button": "休息",
                "rest_submenu_option_1": "露宿 免费",
                "rest_submenu_option_2": "住处 30",
                "rest_submenu_option_3": "冥想室 60",
            }
        )

        self.assertEqual(screen, Screen.REST_SUBMENU)
        self.assertGreaterEqual(confidence, 0.70)

    def test_shop_signature_wins_over_battle_overlap(self) -> None:
        # Journey Trading (交易) sits on the D-DAY background, so battle_title OCRs
        # 参加评鉴战 (a BATTLE anchor word) — without a shop signature it falls to
        # fallback scoring and misclassifies as BATTLE (1.00). The 购买 button plus
        # the selected item's effect detail identify the trading screen instead.
        screen, confidence = _match_screen(
            {
                "battle_title": "参加评鉴战",
                "shop_buy_button": "购买",
                "shop_detail_effect": "潜质点数8退还",
                "shop_item_2_name": "高级牛肉义",
            }
        )

        self.assertEqual(screen, Screen.SHOP)
        self.assertGreaterEqual(confidence, 0.70)

    def test_shop_signature_via_refresh_when_no_item_selected(self) -> None:
        # 刚进交易界面 / 没选中任何商品时, 中间详情和底部「购买」按钮都不显示, 只有右上
        # 「刷新」常驻 + 右侧商品列表。签名必须靠「刷新」识别(否则像实机那样 unknown)。
        screen, confidence = _match_screen(
            {
                "battle_title": "参加评鉴战",  # D-DAY 背景(否则会兜底成 BATTLE)
                "shop_refresh_button": "刷新",
                "shop_item_3_name": "身风扇",
                "shop_item_3_price": "40",
            }
        )

        self.assertEqual(screen, Screen.SHOP)
        self.assertGreaterEqual(confidence, 0.70)

    def test_journey_dialogue_text_wins_over_event_choice_title(self) -> None:
        screen, confidence = _match_screen(
            {
                "event_choice_title": "旅程事件",
                "dialogue_journey_event_label": "旅程事件",
                "dialogue_journey_text_area": "克莱儿获得了星之祝福!",
            }
        )

        self.assertEqual(screen, Screen.DIALOGUE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_event_choice_options_win_over_dialogue_event_label_overlap(self) -> None:
        screen, confidence = _match_screen(
            {
                "event_choice_title": "旅程事件 工坊的宣讲策略",
                "event_choice_option_1": "付钱购买。 50",
                "event_choice_option_2": "寻找序点攻略。 70",
                "dialogue_journey_event_label": "旅程事件 工坊的宣讲策略",
            }
        )

        self.assertEqual(screen, Screen.EVENT_CHOICE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_journey_dialogue_uses_bottom_text_even_without_reward_word(self) -> None:
        screen, confidence = _match_screen(
            {
                "event_choice_title": "旅程事件",
                "dialogue_journey_event_label": "阿尔那事件",
                "dialogue_journey_text_area": "听说了凌穿上现在这身衣服的契机。",
            }
        )

        self.assertEqual(screen, Screen.DIALOGUE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_post_training_success_wins_over_other_overlap(self) -> None:
        screen, confidence = _match_screen(
            {
                "relic_choice_confirm_button": "IMR",
                "post_training_title": "力量训练 Lv.1",
                "post_training_success_text": "训练成功!",
            }
        )

        self.assertEqual(screen, Screen.POST_TRAINING)
        self.assertGreaterEqual(confidence, 0.70)

    def test_commission_select_signature_wins_over_training_hub_when_options_have_text(self) -> None:
        screen, confidence = _match_screen(
            {
                "commission_select_anchor_title": "参加评鉴战",
                "commission_select_option_1_name": "史莱姆讨伐委托",
                "commission_select_option_2_name": "史莱姆讨伐委托",
                "commission_select_accept_button": "接受",
                "training_hub_anchor_title": "委托",
                "training_hub_action_commission": "委托",
            }
        )

        self.assertEqual(screen, Screen.COMMISSION_SELECT)
        self.assertGreaterEqual(confidence, 0.70)

    def test_commission_select_requires_anchor_keyword_to_distinguish_from_blessing_setup(self) -> None:
        screen, confidence = _match_screen(
            {
                "commission_select_anchor_title": "旅程起点",
                "commission_select_option_1_name": "旅程起点",
                "commission_select_option_2_name": "旅程起点",
            }
        )

        self.assertNotEqual(screen, Screen.COMMISSION_SELECT)

    def test_intro_skip_button_classifies_as_dialogue(self) -> None:
        # The story-intro cutscene's only reliable text anchor is its top-right
        # "SKIP" button; the dialogue signature must catch it (case-insensitively)
        # so the intro isn't left UNKNOWN (which fell through to a ~3.6s sweep).
        screen, confidence = _match_screen({"dialogue_intro_skip_button": "SKIP"})

        self.assertEqual(screen, Screen.DIALOGUE)
        self.assertGreaterEqual(confidence, 0.70)

    def test_has_real_event_options_false_when_option_rows_blank(self) -> None:
        # A journey DIALOGUE shares the "旅程事件" title but has no option rows.
        profile = load_region_profile("config/regions/2560x1440.json")
        image = Image.new("RGB", (2560, 1440))

        self.assertFalse(_has_real_event_options(image, profile, _FixedOcr("")))

    def test_has_real_event_options_true_when_option_row_has_text(self) -> None:
        profile = load_region_profile("config/regions/2560x1440.json")
        image = Image.new("RGB", (2560, 1440))

        self.assertTrue(_has_real_event_options(image, profile, _FixedOcr("对攻击有帮助的训练教材")))


class _FixedOcr:
    """OCR stub that returns the same text for every region (for option-row tests)."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self, _image: Image.Image) -> OcrResult:
        return OcrResult(text=self._text, confidence=0.99)


if __name__ == "__main__":
    unittest.main()
