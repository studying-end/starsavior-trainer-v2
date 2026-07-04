"""讨伐委托全流程端到端测试。

模拟用户实机场景（rank 22 + 三委托 17/19/24，红字 banner 触发）从训练主界面看到
"受理讨伐委托！"红字 banner → 点委托按钮 → 委托选择画面 → 选 rank 24 → accept
→ 战斗 → 接受战斗结果。整链路 5 帧 observation 跑 policy.decide，验证每帧 action
符合预期（不 mock 任何决策函数，只 mock observation 序列）。

覆盖规则（2026-07-04 用户规则更新，见 docs/设计方案.md §16）：
- TRAINING_HUB 红字 banner 命中时点委托按钮（受理讨伐委托 gate）
- 委托选择：rank ≤ character_rank + 3 (=25) 中取最高（rank 24，非 19）
- 战斗：开战 → 战斗结果确认
"""
import unittest

from starsavior_trainer.models import (
    Action,
    BattleScene,
    CommissionChoice,
    CommissionOption,
    GameState,
    Observation,
    Rect,
    Screen,
    TrainingHubStatus,
)
from starsavior_trainer.policy.engine import TrainerPolicy


class CommissionFullFlowTest(unittest.TestCase):
    """端到端：训练主界面红字 → 委托选择 → accept → 战斗 → 战斗结束。"""

    def setUp(self) -> None:
        self.policy = TrainerPolicy()
        # 实机当前角色综合等级 22（用户实况）
        self.state = GameState(character_rank=22)

        # 区域配置（2560×1440.json 实际坐标）
        self.commission_button = Rect(2230, 700, 250, 95)
        self.training_button = Rect(2230, 545, 250, 95)
        self.rest_button = Rect(2230, 858, 250, 95)

        # 三个委托（rank 17/19/24，全部无红字 → 进 rank 比较）
        self.opt_low = CommissionOption(
            "低阶", "RANK 17", False, Rect(760, 640, 320, 90)
        )
        self.opt_mid = CommissionOption(
            "中阶", "RANK 19", False, Rect(940, 640, 320, 90)
        )
        self.opt_high = CommissionOption(
            "高阶", "RANK 24", False, Rect(1120, 640, 320, 90)
        )
        self.accept_button = Rect(1200, 1000, 200, 60)
        self.battle_skip_button = Rect(1180, 920, 200, 80)
        self.battle_confirm_button = Rect(1180, 940, 200, 60)

    def test_full_flow_hub_red_banner_to_battle_end(self) -> None:
        """5 帧画面序列：hub(红字) → 委托选(选) → 委托选(确认) → 战斗(开战) → 战斗(确认)。"""
        # ── 帧 1：TRAINING_HUB，has_commission_alert=True（受理讨伐委托！红字 banner）
        # 期望：_decide_training_hub 命中 commission_alert 分支 → 点 commission_button
        hub_obs = Observation(
            screen=Screen.TRAINING_HUB,
            confidence=0.95,
            payload=TrainingHubStatus(
                training_button=self.training_button,
                commission_button=self.commission_button,
                rest_button=self.rest_button,
                has_commission_alert=True,  # ★ "受理讨伐委托！"红字 banner
            ),
            source="frame1_hub_red_banner",
        )
        action1 = self.policy.decide(self.state, hub_obs)
        self.assertEqual(action1.kind, "click")
        self.assertEqual(action1.target, self.commission_button)
        self.assertIn("commission alert", action1.reason)

        # ── 帧 2：COMMISSION_SELECT，三委托 17/19/24，无红字
        # 期望：decide_commission 第一次进 doable 分支，取 ≤22+3=25 的最高 = rank 24
        # → _pending_commission = opt_high.target，点 opt_high
        commission_obs = Observation(
            screen=Screen.COMMISSION_SELECT,
            confidence=0.95,
            payload=CommissionChoice(
                options=[self.opt_low, self.opt_mid, self.opt_high],
                accept_button=self.accept_button,
            ),
            source="frame2_commission_select",
        )
        action2 = self.policy.decide(self.state, commission_obs)
        self.assertEqual(action2.kind, "click")
        self.assertEqual(action2.target, self.opt_high.target)  # ★ 选 rank 24，非 19
        self.assertEqual(self.policy._pending_commission, self.opt_high.target)

        # ── 帧 3：COMMISSION_SELECT（同画面，已选 opt_high）
        # 期望：_pending_commission 命中 → 点 accept_button 确认委托
        action3 = self.policy.decide(self.state, commission_obs)
        self.assertEqual(action3.kind, "click")
        self.assertEqual(action3.target, self.accept_button)
        self.assertIsNone(self.policy._pending_commission)  # 确认后清

        # ── 帧 4：BATTLE，confirm_active=False（战斗入场画面，skip_button 可见）
        # 期望：_decide_battle 点 skip_button 开战
        battle_open_obs = Observation(
            screen=Screen.BATTLE,
            confidence=0.95,
            payload=BattleScene(
                skip_button=self.battle_skip_button,
                confirm_active=False,
            ),
            source="frame4_battle_open",
        )
        action4 = self.policy.decide(self.state, battle_open_obs)
        self.assertEqual(action4.kind, "click")
        self.assertEqual(action4.target, self.battle_skip_button)
        self.assertIn("open battle entry", action4.reason)

        # ── 帧 5：BATTLE，confirm_active=True（战斗结束，确认按钮激活）
        # 期望：_decide_battle 点 confirm_button 接受战斗结果
        battle_end_obs = Observation(
            screen=Screen.BATTLE,
            confidence=0.95,
            payload=BattleScene(
                skip_button=self.battle_skip_button,
                confirm_button=self.battle_confirm_button,
                confirm_active=True,
            ),
            source="frame5_battle_end",
        )
        action5 = self.policy.decide(self.state, battle_end_obs)
        self.assertEqual(action5.kind, "click")
        self.assertEqual(action5.target, self.battle_confirm_button)
        self.assertIn("accept battle", action5.reason)

    def test_red_text_on_commission_overrides_rank_rule(self) -> None:
        """有红字标记时红字优先于 rank 比较：rank 17 有红字 → 取 17 而非 24。
        红字 = 适合当前角色的委托（游戏 UI 提示），始终优先于 +3 buffer 规则。"""
        red_low = CommissionOption("低阶", "RANK 17", True, Rect(760, 640, 320, 90))
        no_red_high = CommissionOption("高阶", "RANK 24", False, Rect(1120, 640, 320, 90))
        choice = CommissionChoice(
            options=[red_low, no_red_high],
            accept_button=self.accept_button,
        )
        action = self.policy.decide_commission(choice, GameState(character_rank=22))
        self.assertEqual(action.target, red_low.target)  # red 优先

    def test_buffer_constant_value(self) -> None:
        """COMMISSION_RANK_BUFFER=3（用户规则：rank 22 最高能打 rank 25）。"""
        self.assertEqual(TrainerPolicy.COMMISSION_RANK_BUFFER, 3)


if __name__ == "__main__":
    unittest.main()
