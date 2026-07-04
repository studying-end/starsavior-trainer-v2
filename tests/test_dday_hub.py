"""D-DAY 评鉴战日训练大厅决策测试。

覆盖 _decide_training_hub 的 D-DAY 分支（screens/__init__.py）：
- D-DAY 首次进大厅: 交易+评鉴战按钮都在 → 先点交易
- 交易完成 (_dday_trading_done=True): 跳过交易, 点评鉴战 + 设 _dday_rating_done=True
- 评鉴战完成 (_dday_rating_done=True, 按钮 OCR 仍命中): 不再点评鉴战, fall through 到正常 hub 流程
- 非 D-DAY: 清两个标志, 下次评鉴战日重新走流程

修复背景 (2026-07-04)：评鉴战打完后返回大厅, rating_battle_button OCR 仍命中"评鉴战"
文字(按钮未刷新或 D-DAY 未真正结束) → _dday_trading_done=True 跳过交易 → 又点
评鉴战 → 死循环。新增 _dday_rating_done 标志: 点过一次评鉴战后不再点, fall through。
"""
import unittest

from starsavior_trainer.models import (
    Action,
    GameState,
    Observation,
    Rect,
    Screen,
    TrainingHubStatus,
)
from starsavior_trainer.policy.engine import TrainerPolicy


def _hub_obs(rating_battle_button: Rect | None, trading_button: Rect | None) -> Observation:
    return Observation(
        screen=Screen.TRAINING_HUB,
        confidence=0.95,
        payload=TrainingHubStatus(
            # training_button 用与 rating_battle_button 不同的坐标, 便于断言区分
            training_button=Rect(1100, 545, 250, 95),
            commission_button=Rect(2230, 700, 250, 95),
            rest_button=Rect(2230, 858, 250, 95),
            rating_battle_button=rating_battle_button,
            trading_button=trading_button,
        ),
        source="dday_test",
    )


class DDayHubFlowTest(unittest.TestCase):
    """D-DAY 评鉴战日: 交易 → 评鉴战 → 评鉴战完成后不再死循环。"""

    def setUp(self) -> None:
        self.policy = TrainerPolicy()
        self.state = GameState(character_rank=22)
        self.rating_btn = Rect(2230, 545, 250, 95)
        self.trading_btn = Rect(2230, 700, 250, 95)
        self.training_btn = Rect(1100, 545, 250, 95)  # 与 rating_btn 不同坐标

    def test_dday_first_visit_clicks_trading(self) -> None:
        """D-DAY 首次进大厅: 交易+评鉴战按钮都在, _dday_trading_done=False → 先点交易。"""
        action = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, self.trading_btn)
        self.assertIn("先去交易", action.reason)

    def test_dday_after_trading_clicks_rating_battle(self) -> None:
        """交易完成 (_dday_trading_done=True): 跳过交易 → 点评鉴战 + 设 _dday_rating_done=True。"""
        self.policy._dday_trading_done = True
        action = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, self.rating_btn)
        self.assertIn("去评鉴战", action.reason)
        # 标志已设: 下次返回大厅不再点
        self.assertTrue(self.policy._dday_rating_done)

    def test_dday_after_rating_battle_does_not_loop(self) -> None:
        """评鉴战完成 (_dday_rating_done=True) 但按钮 OCR 仍命中 → 不再点评鉴战, fall through。"""
        self.policy._dday_trading_done = True
        self.policy._dday_rating_done = True
        action = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        # ★ 关键: 不能再点 rating_battle_button (否则死循环)
        self.assertNotEqual(action.target, self.rating_btn)
        # 应该 fall through 到正常 hub 流程 (training_button, 与 rating_btn 不同坐标)
        self.assertEqual(action.target, self.training_btn)
        # 标志保持 True (D-DAY 还在, 不能重置让下次又点评鉴战)
        self.assertTrue(self.policy._dday_rating_done)

    def test_non_dday_resets_flags(self) -> None:
        """非 D-DAY (rating_battle_button=None) → 清两个标志, 下次评鉴战日重新走流程。"""
        self.policy._dday_trading_done = True
        self.policy._dday_rating_done = True
        # rating_battle_button=None → 非 D-DAY
        self.policy.decide(self.state, _hub_obs(None, None))
        self.assertFalse(self.policy._dday_trading_done)
        self.assertFalse(self.policy._dday_rating_done)

    def test_full_dday_cycle_then_next_dday_works(self) -> None:
        """完整流程: 交易 → 评鉴战 → 评鉴战完成 fall through → D-DAY 结束清标志 → 下次 D-DAY 重新走流程。"""
        # 帧 1: 首次进 D-DAY 大厅 → 点交易
        a1 = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertEqual(a1.target, self.trading_btn)
        # 帧 2: 模拟交易完成 (_dday_trading_done 由 ShopInspector 设置)
        self.policy._dday_trading_done = True
        a2 = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertEqual(a2.target, self.rating_btn)
        self.assertTrue(self.policy._dday_rating_done)
        # 帧 3: 模拟评鉴战完成返回大厅, 按钮 OCR 仍命中
        a3 = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertNotEqual(a3.target, self.rating_btn)  # 不再点评鉴战
        self.assertTrue(self.policy._dday_rating_done)  # 仍 True
        # 帧 4: D-DAY 结束 (按钮消失) → 清标志
        self.policy.decide(self.state, _hub_obs(None, None))
        self.assertFalse(self.policy._dday_trading_done)
        self.assertFalse(self.policy._dday_rating_done)
        # 帧 5: 下次 D-DAY → 重新走流程 (先交易)
        a5 = self.policy.decide(self.state, _hub_obs(self.rating_btn, self.trading_btn))
        self.assertEqual(a5.target, self.trading_btn)


if __name__ == "__main__":
    unittest.main()
