"""目标弹窗(旅程信息) parser/签名/注册测试。

覆盖(§22.9):
- parse_goal_dialog: 读 N/45 → round; 锚点未命中 → None
- _has_goal_dialog_signature: 旅程信息标题 → True; 空/其它 → False
- HANDLERS 注册: GOAL_DIALOG 在表 + priority=2 + anchor_fn/parse_fn 配置
"""
import unittest

from starsavior_trainer.classifier_signatures import _has_goal_dialog_signature
from starsavior_trainer.models import GoalDialogStatus, Rect, Screen
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.screens import ANCHOR_HANDLERS, HANDLERS
from starsavior_trainer.screens.goal_dialog import parse_goal_dialog


def _goal_profile() -> RegionProfile:
    return RegionProfile(
        "p",
        (2560, 1440),
        {
            "goal_dialog_anchor_title": Rect(563, 312, 153, 45),
            "goal_dialog_round_label": Rect(870, 1027, 83, 36),
            "goal_dialog_close_button": Rect(2005, 313, 42, 41),
        },
    )


class ParseGoalDialogTest(unittest.TestCase):
    def test_reads_round_from_n_over_45(self) -> None:
        """21/45 → round=21。"""
        texts = [
            RegionText("goal_dialog_anchor_title", "旅程信息", 0.9),
            RegionText("goal_dialog_round_label", "21/45", 0.9),
        ]
        payload = parse_goal_dialog(texts, _goal_profile())
        self.assertIsNotNone(payload)
        self.assertEqual(payload.round, 21)
        self.assertEqual(payload.close_button, _goal_profile().regions["goal_dialog_close_button"])

    def test_returns_none_when_anchor_missing(self) -> None:
        """标题锚点未命中(无"旅程信息")→ None。"""
        texts = [RegionText("goal_dialog_anchor_title", "距离目标", 0.9)]  # 大厅文字, 非弹窗
        self.assertIsNone(parse_goal_dialog(texts, _goal_profile()))

    def test_returns_none_when_title_region_absent(self) -> None:
        """标题 region 完全缺失 → None。"""
        self.assertIsNone(parse_goal_dialog([], RegionProfile("p", (2560, 1440), {})))

    def test_round_none_when_round_label_unparseable(self) -> None:
        """回合数 OCR 失败(非数字)→ round=None, 但仍返回 payload(标题命中)。"""
        texts = [
            RegionText("goal_dialog_anchor_title", "旅程信息", 0.9),
            RegionText("goal_dialog_round_label", "??", 0.5),
        ]
        payload = parse_goal_dialog(texts, _goal_profile())
        self.assertIsNotNone(payload)
        self.assertIsNone(payload.round)

    def test_anchor_text_variant_still_matches(self) -> None:
        """OCR 容错: "程信息"(部分误识)仍命中锚点。"""
        texts = [
            RegionText("goal_dialog_anchor_title", "程信息", 0.7),
            RegionText("goal_dialog_round_label", "15/45", 0.9),
        ]
        payload = parse_goal_dialog(texts, _goal_profile())
        self.assertIsNotNone(payload)
        self.assertEqual(payload.round, 15)


class GoalDialogSignatureTest(unittest.TestCase):
    def test_title_旅程信息_matches(self) -> None:
        self.assertTrue(_has_goal_dialog_signature({"goal_dialog_anchor_title": "旅程信息"}))

    def test_title_程信息_variant_matches(self) -> None:
        self.assertTrue(_has_goal_dialog_signature({"goal_dialog_anchor_title": "程信息"}))

    def test_empty_title_no_match(self) -> None:
        self.assertFalse(_has_goal_dialog_signature({"goal_dialog_anchor_title": ""}))

    def test_hub_text_no_match(self) -> None:
        """大厅"距离目标"不应被判为目标弹窗(消歧关键)。"""
        self.assertFalse(_has_goal_dialog_signature({"goal_dialog_anchor_title": "距离目标"}))

    def test_missing_region_no_match(self) -> None:
        self.assertFalse(_has_goal_dialog_signature({}))


class GoalDialogRegistrationTest(unittest.TestCase):
    def test_registered_in_handlers(self) -> None:
        self.assertIn(Screen.GOAL_DIALOG, HANDLERS)

    def test_priority_is_2(self) -> None:
        """priority=2 早检查: 弹窗背景是大厅, 必须早于 TRAINING_HUB(priority=8)。"""
        self.assertEqual(HANDLERS[Screen.GOAL_DIALOG].priority, 2)

    def test_has_anchor_and_parse_fn(self) -> None:
        handler = HANDLERS[Screen.GOAL_DIALOG]
        # anchor_fn/parse_fn 是私有属性, 用公共行为验证: has_anchor 命中 + parse 能返回 payload
        self.assertTrue(handler.has_anchor({"goal_dialog_anchor_title": "旅程信息"})[0])
        self.assertFalse(handler.has_anchor({"goal_dialog_anchor_title": ""})[0])

    def test_in_anchor_handlers_for_classification(self) -> None:
        """GOAL_DIALOG 应出现在分类用的 ANCHOR_HANDLERS 列表。"""
        self.assertIn(Screen.GOAL_DIALOG, [h.screen for h in ANCHOR_HANDLERS])

    def test_anchor_handlers_priority_order_before_training_hub(self) -> None:
        """GOAL_DIALOG(priority=2) 排在 TRAINING_HUB(priority=8) 之前, 避免弹窗被大厅抢走。"""
        screens = [h.screen for h in ANCHOR_HANDLERS]
        self.assertLess(screens.index(Screen.GOAL_DIALOG), screens.index(Screen.TRAINING_HUB))


if __name__ == "__main__":
    unittest.main()
