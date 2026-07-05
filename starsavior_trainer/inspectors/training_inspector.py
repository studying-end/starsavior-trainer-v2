"""训练检视器 — 逐张点训练卡读增益, 选加成最多。

重构自 training_inspector.py。支援卡头像每回合随机, 固定偏置无法判断本回合最佳;
游戏只在选中卡后显示 +N 增益 → 点击每张候选(力量/体力/韧性)读增益, 选最高。
任一失败率≥阈值立即放弃其余去休息(疲劳全局); 两步确认不依赖 OCR selected_name。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from starsavior_trainer.models import Action, GameState, TrainingChoice
from starsavior_trainer.behavior import narrate
from starsavior_trainer.logging_setup import get_logger

logger = get_logger("training_inspector")

# 早期游戏(攒支援卡羁绊): 5 个训练属性, 按人头多少选; 全<=1 则去休息回心情。
EARLY_GAME_HEAD_ATTRS = ("power", "stamina", "guts", "wisdom", "speed")
# 早期游戏按人头选的回合窗口(可配置; 用户约定默认 20)。
EARLY_GAME_HEAD_ROUNDS = 20
# §22.24 confirm 后 N 帧画面仍没切走 → 强制 reset 重试（防 confirm 失败死锁）
_CONFIRMED_TIMEOUT_FRAMES = 5


def decide_early_training(head_counts: dict[str, int]) -> str | None:
    """早期游戏选"人头最多"的训练以最大化支援卡羁绊; 全部<=1 返回 None(去休息回心情)。

    mood(NORMAL→GOOD→BEST)越高训练属性越高, 全<=1 时无人头值得选, 不如花 30 块
    去"住处"休息回心情(见 rest 机制)。返回属性名或 None(休息)。
    平局按 EARLY_GAME_HEAD_ATTRS 顺序(力量>体力>韧性>专注>保护)。
    """
    if not head_counts or max(head_counts.values()) <= 1:
        return None  # 全<=1 → 休息
    order = {name: i for i, name in enumerate(EARLY_GAME_HEAD_ATTRS)}
    return max(head_counts, key=lambda c: (head_counts[c], -order.get(c, 99)))


@dataclass
class TrainingInspector:
    """Pick the best of the priority trainings by inspecting each one's preview gain.

    Internal stat keys map to the game's trainings as:
        power=力量  stamina=体力  guts=韧性  wisdom=专注  speed=保护
    """

    # The trainings worth comparing on a power run, top-to-bottom. 专注/保护
    # (命中/命抗) are skipped — only worth it on high affinity, a separate rule.
    inspect_attrs: tuple[str, ...] = ("power", "stamina", "guts")
    max_fail_rate: int = 30
    records: dict[str, int] = field(default_factory=dict)
    fails: dict[str, int] = field(default_factory=dict)
    pending: str | None = None
    last_clicked: str | None = None
    # 早期游戏(人头模式)状态
    head_counts: dict[str, int] = field(default_factory=dict)
    head_pending: str | None = None
    head_decided: str | None = None
    # §22.19 确认后等画面切换：防止同一 TRAINING_SELECT 帧重复检视/选卡。
    # confirmed(非早期) / head_confirmed(早期) 在点确认按钮后置 True，
    # 下一帧 inspector 返回 None(不点任何卡) → 等画面切走 → reset() 清除。
    confirmed: bool = False
    head_confirmed: bool = False
    # §22.24 auto_collect 每会话只采一次（避免每帧 ~0.4s × 5 卡 + 污染风险）
    _auto_collected_this_session: bool = False
    # §22.24 confirm 后帧计数（超 _CONFIRMED_TIMEOUT_FRAMES 强制 reset）
    _confirmed_count: int = 0

    def decide(self, choices: Iterable[TrainingChoice], state: GameState | None = None, image=None, policy=None, profile=None) -> Action | None:
        choices = list(choices)
        # §22.19 确认后等画面切换：不检视/不选卡，等 reset() 清除(画面切走时 live_loop 调)
        if self.confirmed:
            self._bump_confirmed_or_timeout()
            return None
        # 早期游戏(攒支援卡羁绊): 按人头选; 全<=1 去住处休息回心情
        if (
            state is not None
            and image is not None
            and state.current_round is not None
            and 0 < state.current_round <= EARLY_GAME_HEAD_ROUNDS
        ):
            return self._decide_early_game(choices, state, image, policy, profile)
        candidates = [c for c in choices if c.name in self.inspect_attrs]
        if len(candidates) < 2:
            self.reset()
            return None

        # Record the gain/fail for the card we clicked last turn: clicking it
        # selected it, so its +N preview is now on the panel (and its 失败率 shows).
        selected = next((c for c in choices if c.selected), None)
        if self.pending is not None and selected is not None and selected.name == self.pending:
            self.records[self.pending] = selected.stat_gain
            self.fails[self.pending] = selected.fail_rate
            self.pending = None
            # Fatigue is global: the moment any inspected training reads ≥ threshold,
            # stop inspecting the rest and defer to rest immediately — the others are
            # almost certainly too high too, so clicking them just wastes turns.
            if selected.fail_rate is not None and selected.fail_rate >= self.max_fail_rate:
                self.reset()
                return None

        # Inspect each not-yet-seen candidate by clicking it (selects -> panel
        # shows its gain next turn).
        unseen = [c for c in candidates if c.name not in self.records]
        if unseen:
            target = unseen[0]
            self.pending = target.name
            self.last_clicked = target.name
            return Action("click", target.target, f"inspect training {target.name}")

        # All inspected. Among those with an acceptable fail rate, take the most
        # gain (ties -> the inspect_attrs order, i.e. 力量 > 体力 > 韧性).
        # A missing fail entry = never confirmed its rate → un-affordable (not 0%),
        # so we bail to rest instead of training a card whose real fail rate is unknown.
        affordable = [
            c
            for c in candidates
            if (f := self.fails.get(c.name)) is not None and f <= self.max_fail_rate
        ]
        if not affordable:
            # Every priority training is too risky (low stamina) — defer to the
            # policy, which routes back to the hub to rest.
            self.reset()
            return None
        order = {name: i for i, name in enumerate(self.inspect_attrs)}
        best = max(affordable, key=lambda c: (self.records.get(c.name, 0), -order.get(c.name, 99)))
        gain = self.records.get(best.name, 0)

        # Two-step confirm that does NOT depend on a parsed selected_name: if best
        # is already selected (we clicked it last), confirm; else select it first.
        if self.last_clicked == best.name and best.confirm_button is not None:
            self.confirmed = True  # §22.19 等画面切换，不 reset（防重复检视）
            return Action("click", best.confirm_button, f"confirm training {best.name}: gain={gain}")
        self.last_clicked = best.name
        return Action("click", best.target, f"choose training {best.name}: gain={gain}")

    def _decide_early_game(self, choices, state, image, policy, profile=None):
        """早期游戏: 逐张点训练卡读人头(count_heads), 选人头最多; 全<=1 去住处休息回心情。

        读人头前先自动采集新人头入库(auto_collect_new_heads), 下一帧 count_heads 即生效。
        全<=1 时: 心情BEST+耐力充足 → 优先选有人头的卡(人头>0)中训练值最高; 全无人头
        → 选训练值最高(不浪费BEST回合); 否则 → 去住处休息回心情。
        """
        # §22.19 确认后等画面切换：不检视/不选卡
        if self.head_confirmed:
            self._bump_confirmed_or_timeout()
            return None

        from starsavior_trainer.vision import count_heads

        candidates = [c for c in choices if c.name in EARLY_GAME_HEAD_ATTRS]
        selected = next((c for c in choices if c.selected), None)
        # 已决定选某卡 → 确认阶段
        if self.head_decided is not None:
            target = next((c for c in candidates if c.name == self.head_decided), None)
            if target is not None:
                if selected is not None and selected.name == self.head_decided and target.confirm_button is not None:
                    self.head_confirmed = True  # §22.19 等画面切换，防重复检视
                    self.head_decided = None
                    return Action("click", target.confirm_button, f"early game confirm {target.name}")
                return Action("click", target.target, f"early game select {target.name} (to confirm)")
            self.head_decided = None
        # 记录上次点的卡的人头(它此时选中, image 显示其人头)
        if self.head_pending is not None and selected is not None and selected.name == self.head_pending:
            # §22.24 auto_collect 每会话只采一次（避免每帧 ~0.4s × 5 卡 ~2s + 污染风险）
            if profile is not None and not self._auto_collected_this_session:
                try:
                    from starsavior_trainer.tools.collect_head_templates import auto_collect_new_heads
                    panel_rect = profile.regions.get("training_select_heads_panel")
                    if panel_rect is not None:
                        new_count = auto_collect_new_heads(image, panel_rect)
                        if new_count > 0:
                            narrate(f"[自动入库] 发现 {new_count} 个新人头已入库（本会话首次）")
                except Exception as e:
                    logger.debug(f"[auto_collect_new_heads] failed: {e}")
                self._auto_collected_this_session = True
            n = count_heads(image, search_region=profile.regions.get("training_select_heads_panel") if profile is not None else None)
            self.head_counts[selected.name] = n
            narrate(f"[训练检视] {selected.name} 作数人头={n}")
            self.head_pending = None
        # 点下一张未读的卡
        unseen = [c for c in candidates if c.name not in self.head_counts]
        if unseen:
            target = unseen[0]
            self.head_pending = target.name
            return Action("click", target.target, f"early game inspect heads: {target.name}")
        # 全读完 → 决策
        counts = dict(self.head_counts)
        pick = decide_early_training(counts)
        self.head_counts = {}
        self.head_pending = None
        if pick is None:
            # 全<=1: 心情BEST+耐力充足 → 选训练值最高的继续训练(不浪费BEST回合);
            # 否则 → 去住处休息回心情(mood)
            mood = getattr(policy, "_cached_mood", None) if policy is not None else None
            endurance = getattr(policy, "_cached_endurance", None) if policy is not None else None
            threshold = getattr(getattr(policy, "config", None), "rest_endurance_threshold", 0.40)
            if mood == "BEST" and endurance is not None and endurance >= threshold:
                order = {name: i for i, name in enumerate(EARLY_GAME_HEAD_ATTRS)}
                # 优先选有人头的卡(counts>0)中训练值最高; 全无人头 → 选训练值最高
                with_heads = [c for c in candidates if counts.get(c.name, 0) > 0]
                pool = with_heads if with_heads else candidates
                best_gain = max(
                    pool,
                    key=lambda c: (c.stat_gain, -order.get(c.name, 99)),
                )
                head_note = f"heads={counts.get(best_gain.name, 0)}" if with_heads else "no heads"
                narrate(
                    f"[训练决策] 早期游戏 5 卡作数人头 {counts} 全<=1 但心情BEST+耐力{endurance:.0%} "
                    f"→ 选 {best_gain.name} (训练值={best_gain.stat_gain} 最高, {head_note}, 不浪费BEST回合)"
                )
                self.head_decided = best_gain.name
                return Action(
                    "click",
                    best_gain.target,
                    f"early game choose {best_gain.name}: gain={best_gain.stat_gain} (mood BEST, {head_note})",
                )
            narrate(f"[训练决策] 早期游戏 5 卡作数人头 {counts} 全<=1 → 退出训练选择，回大厅去住处休息回心情")
            if policy is not None:
                policy._needs_rest = True
                policy._rest_for_mood = True
            back = next((c.back_button for c in candidates if c.back_button is not None), None)
            return (
                Action("click", back, f"early game: heads {counts} all<=1, rest at 住处 for mood")
                if back is not None
                else None
            )
        # 选人头最多的 → 点它选中, 下帧确认
        narrate(f"[训练决策] 早期游戏 选 {pick}（作数人头 {counts[pick]} 最多，攒支援卡羁绊）")
        self.head_decided = pick
        target = next((c for c in candidates if c.name == pick), None)
        return Action("click", target.target, f"early game choose {pick}: heads={counts[pick]}")

    def _bump_confirmed_or_timeout(self) -> None:
        """§22.24 confirmed/head_confirmed 后等画面切走；超 N 帧强制 reset（防 confirm 失败死锁）。"""
        self._confirmed_count += 1
        if self._confirmed_count > _CONFIRMED_TIMEOUT_FRAMES:
            narrate(f"[confirm 超时] {_CONFIRMED_TIMEOUT_FRAMES} 帧画面没切走，强制 reset 重试")
            self.reset()

    def reset(self) -> None:
        self.records = {}
        self.fails = {}
        self.pending = None
        self.last_clicked = None
        self.head_counts = {}
        self.head_pending = None
        self.head_decided = None
        self.confirmed = False  # §22.19
        self.head_confirmed = False  # §22.19
        self._auto_collected_this_session = False  # §22.24
        self._confirmed_count = 0  # §22.24
