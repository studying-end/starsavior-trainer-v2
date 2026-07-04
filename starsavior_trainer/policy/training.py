"""训练决策 Mixin — training_score 排序 + 两步确认 + 全失败率过高回 hub + blue 模式降级。

重构自 policy.py decide_training（行 488-521）。坑 #16: 全失败率过高→点返回箭头回 hub,
设 _needs_rest 标志, hub 消费它去休息。

命名红线（不可违背）: 训练资源耐力 = endurance（耗尽→失败率高→休息）; 体力 = stamina
（5 训练属性之一: 力量/体力/韧性/专注/保护, 即 HP）。两者不相干, 勿混用。全失败率过高
的根因是耐力(endurance)低, 不是体力(HP)。

blue 模式（无 OCR）: blue_parsers 读不到 stat_gain/fail_rate → 全卡 fail_rate=None →
engine.training_score 一律 -inf（None 在 OCR 模式表示"未检视卡不可赌", 正确）→ 死锁成只
休息。decide_training 检测全 None 走 ring+bias 降级排序盲训。详见 设计方案 §22.2。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Action, GameState, TrainingChoice


class TrainingMixin:
    def decide_training(self, choices: Iterable[TrainingChoice], state: GameState | None = None) -> Action:
        choices = list(choices)
        if not choices:
            return Action("pause", None, "no training choices recognized")

        # Blue mode (no OCR): blue_parsers can't read fail_rate → every card is
        # None → engine.training_score returns -inf for all (it treats None as
        # "un-inspected, never gamble", correct for OCR mode). That would deadlock
        # blue mode into rest-only, so detect all-None and rank by ring + build
        # bias instead, letting training proceed blind. 详见 §22.2.
        if all(c.fail_rate is None for c in choices):
            best = max(choices, key=lambda c: self._blue_training_score(c, state))
            score = self._blue_training_score(best, state)
            if best.selected and best.confirm_button is not None:
                return Action(
                    "click",
                    best.confirm_button,
                    f"blue mode confirm {best.name}: ring={best.ring}, score={score:.1f} (no OCR, blind)",
                )
            return Action(
                "click",
                best.target,
                f"blue mode select {best.name}: ring={best.ring}, score={score:.1f} (no OCR, blind)",
            )

        ranked = sorted(
            ((self.training_score(choice, state), choice) for choice in choices),
            key=lambda item: item[0],
            reverse=True,
        )

        score, best = ranked[0]
        if score == float("-inf"):
            # Every training's fail rate is too high (low endurance — 训练资源耐力,
            # NOT 体力/HP stamina). Return to the hub via the top-left back arrow;
            # the hub-level decision consumes _needs_rest to choose rest.
            back_button = next((c.back_button for _, c in ranked if c.back_button is not None), None)
            if back_button is not None:
                self._needs_rest = True  # hub will consume this to choose rest
                return Action("click", back_button, "all training fail rates too high, return to hub to rest")
            return Action("pause", None, "all training choices exceed failure threshold")

        # Two-step flow: first click the desired card to select it, then click 训练 confirm.
        if best.selected and best.confirm_button is not None:
            return Action(
                "click",
                best.confirm_button,
                f"confirm training {best.name}: score={score:.1f}, ring={best.ring}, fail={best.fail_rate}%",
            )
        return Action(
            "click",
            best.target,
            f"select {best.name}: score={score:.1f}, ring={best.ring}, fail={best.fail_rate}%",
        )

    def _blue_training_score(self, choice: TrainingChoice, state: GameState | None) -> float:
        """Blue-mode ranking: ring colour + build attribute bias (no fail_rate).

        Ring is the only signal blue_parsers can read, so prefer the best ring;
        break ties by the build's attribute bias. 不涉及耐力/体力, 仅为无 OCR 模式降级。
        """
        profile = state.build_profile if state else "balanced"
        bias = self.config.training_bias_by_profile.get(profile, {}).get(choice.name, 0)
        return bias + self.config.ring_bonus.get(choice.ring, 0)
