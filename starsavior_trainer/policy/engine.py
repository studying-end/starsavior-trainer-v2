"""TrainerPolicy 决策引擎核心 — init(_pending_X 状态) + decide(分发 HANDLERS) + training_score。

重构自 policy.py §5（行 258-357）。decide 通过 screens 注册表分发到 handler.decide
(决策也走注册表); _pending_X 状态防两步确认翻转(坑 B 类); training_score 共享给训练 handler。
各 decide_X 决策方法在 policy/各决策.py(T13), 由 handler 调用。
"""
from __future__ import annotations

from starsavior_trainer.models import Action, GameState, Observation, Rect, Screen, TrainingChoice
from starsavior_trainer.policy.blessing import BlessingMixin
from starsavior_trainer.policy.character_select import CharacterSelectMixin
from starsavior_trainer.policy.config import PolicyConfig
from starsavior_trainer.policy.event import EventMixin
from starsavior_trainer.policy.relic_commission import RelicCommissionMixin
from starsavior_trainer.policy.shop_skill import ShopSkillMixin
from starsavior_trainer.policy.simple import SimpleMixin
from starsavior_trainer.policy.training import TrainingMixin


class TrainerPolicy(
    CharacterSelectMixin,
    TrainingMixin,
    SimpleMixin,
    BlessingMixin,
    EventMixin,
    RelicCommissionMixin,
    ShopSkillMixin,
):
    def __init__(self, config: PolicyConfig | None = None, relic_db_path: "Path | str | None" = None, shop_db_path: "Path | str | None" = None):
        self.config = config or PolicyConfig()
        # 奖励模板库 JSON 路径。None=不查/不自动入库(decide_relic 退化到按 score 选);
        # 默认 config/relics.json(由 live_loop 注入; 测试可传 None 或临时文件)。
        from pathlib import Path
        if relic_db_path is None:
            relic_db_path = Path(__file__).resolve().parent.parent.parent / "config" / "relics.json"
        self.relic_db_path = relic_db_path
        # 商品模板库 JSON 路径（ShopInspector 用）。默认 config/shop_items.json。
        if shop_db_path is None:
            shop_db_path = Path(__file__).resolve().parent.parent.parent / "config" / "shop_items.json"
        self.shop_db_path = shop_db_path
        self._pending_commission: Rect | None = None
        # Two-step relic confirm: remembers the relic card we clicked so the next
        # call clicks 确认 instead of re-evaluating "best" every frame. Without this
        # a normal relic choice never reached a confirm path (selected_name is only
        # set for the fixed initial relic), so it re-picked each frame and flipped
        # between near-scored cards — the back-and-forth oscillation.
        self._pending_relic: Rect | None = None
        # Same two-step confirm for blessing choice: equal-value cards can't be told
        # apart by selected_name (OCR), so confirming on selected_name==best never
        # fires → loop. Remember the card we clicked; next frame click 确认 directly.
        self._pending_blessing: Rect | None = None
        # Set when we bail out of TRAINING_SELECT because every option's fail rate
        # is too high; the next TRAINING_HUB decision consumes it to go rest.
        self._needs_rest: bool = False
        # 早期游戏"全人头<=1 → 住处休息回心情"时置位; decide_rest 见此选住处(30, mood)
        # 而非冥想室(60, 体力)。mood NORMAL→GOOD→BEST, 越高训练属性越高。
        self._rest_for_mood: bool = False
        # §22.3 休息策略: 从最近一次 TRAINING_HUB 缓存的心情(mood)与耐力(endurance_ratio),
        # 供 REST_SUBMENU 的 decide_rest 决策（住处/露宿/冥想室）。详见 设计方案 §22.3。
        self._cached_mood: str | None = None
        self._cached_endurance: float = 0.0
        # Two-step rest: remembers the option we selected so the next call confirms.
        self._pending_rest: Rect | None = None
        # Character-list search state (bidirectional, bounded — avoids the
        # infinite one-direction scroll that missed a target above the start).
        self._char_scroll_count: int = 0
        self._char_scroll_down: bool = True
        self._char_reversed: bool = False
        self._char_seen_names: frozenset[str] | None = None
        # Two-step character confirm: remembers the desired character whose row we
        # just clicked, so the next call clicks 选择 to confirm — WITHOUT relying on
        # the left-panel selected-name OCR (which is unreliable for some characters).
        self._char_pending_confirm: str | None = None
        # D-DAY 评鉴战日: 是否已逛过交易(打过评鉴战交易就消失,所以先交易再评鉴战)。
        self._dday_trading_done: bool = False
        # D-DAY 评鉴战日: 是否已点过评鉴战按钮(避免返回大厅后 OCR 仍命中 评鉴战 文字 → 死循环)。
        self._dday_rating_done: bool = False
        # §22.9: 需要读目标弹窗 N/45 校准回合数。live_loop 在旅程首次进大厅 / 日期变化时置 True,
        # _decide_training_hub 见此标志优先点 goal_button → 下帧 GOAL_DIALOG 读 N/45。
        self._needs_goal_round: bool = False

    def decide(self, state: GameState, observation: Observation) -> Action:
        if observation.confidence < self.config.min_screen_confidence:
            return Action("pause", None, f"low screen confidence: {observation.confidence:.2f}")

        # Leaving the character-select screen ends any in-progress list search, so
        # a later visit (e.g. the next journey) starts a fresh bidirectional scan.
        if observation.screen != Screen.CHARACTER_SELECT:
            self._reset_character_scroll()
            self._char_pending_confirm = None
        # Forget any half-finished relic pick once we leave the relic screen.
        if observation.screen != Screen.RELIC_CHOICE:
            self._pending_relic = None
        if observation.screen != Screen.BLESSING_CHOICE:
            self._pending_blessing = None

        # Dispatch through the screen registry instead of a hardcoded if/elif
        # chain. Each handler.decide is a verbatim copy of the branch that used
        # to live here and receives this policy for config/instance-state access.
        # Imported lazily to avoid an import cycle (screens/__init__ imports policy).
        from starsavior_trainer.screens import HANDLERS

        handler = HANDLERS.get(observation.screen)
        if handler is None:
            return Action("pause", None, "unknown screen")
        return handler.decide(observation, state, self)

    def training_score(self, choice: TrainingChoice, state: GameState | None = None) -> float:
        # fail_rate is None when the card's 失败率 isn't shown (it isn't the selected
        # card) — i.e. UNKNOWN, not 0%. Never gamble on an un-inspected card: treat
        # unknown (and over-threshold) fail rates as un-trainable so the policy bails
        # to rest instead of training a card whose real fail rate could be ~99%.
        # §22.4: 失败率阈值随训练值 gain 动态放宽（gain<50→20%, 50-99→35%, ≥100→80%）。
        max_fail = self._max_fail_for_gain(choice.stat_gain)
        if choice.fail_rate is None or choice.fail_rate > max_fail:
            return float("-inf")
        if choice.fail_rate <= 5:
            fail_penalty = 0
        elif choice.fail_rate <= 15:
            fail_penalty = choice.fail_rate * 1.5
        else:
            fail_penalty = choice.fail_rate * 3

        profile = state.build_profile if state else "balanced"
        strategic_bias = self.config.training_bias_by_profile.get(profile, {}).get(choice.name, 0)

        is_early_round = (
            state is not None
            and state.current_round is not None
            and state.current_round <= self.config.early_game_rounds
        )

        ring_value = self.config.ring_bonus.get(choice.ring, 0)
        early_bonus = 0
        if is_early_round:
            ring_value *= self.config.early_ring_multiplier
            early_bonus = self.config.early_game_stat_weight.get(choice.name, 0)

        return (
            choice.stat_gain
            + ring_value
            - fail_penalty
            + strategic_bias
            + early_bonus
        )

    def _max_fail_for_gain(self, gain: int) -> int:
        """失败率上限随训练值 gain 线性放宽（§22.4）：min(99, base + slope×gain)。
        训练成功=+gain, 失败=0+降心情(可恢复); gain 越高越愿赌高失败率。
        校准: gain=20→20%, 50→35%, 60→40%, 100→60%, 188→99%。"""
        cfg = self.config
        return min(99, int(round(cfg.fail_rate_base + cfg.fail_rate_slope * gain)))

    def _reset_character_scroll(self) -> None:
        self._char_scroll_count = 0
        self._char_scroll_down = True
        self._char_reversed = False
        self._char_seen_names = None


def _is_iterable_of(value: object, item_type: type) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    return all(isinstance(item, item_type) for item in value)
