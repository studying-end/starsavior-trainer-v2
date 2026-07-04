"""委托检视器 — 逐个点开委托读建议综合等级, 选可做最高阶。

重构自 commission_inspector.py。列表只显示阶名(低/中/高阶), 建议综合等级(RANK 17)只在
选中后中央详情显示 → 点击每个委托读建议等级, 选≤角色等级+3 的最高阶。坑 #39 解耦:
character_rank 直接从委托界面读(choice.character_rank), 不依赖先经过训练大厅。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from starsavior_trainer.models import Action, CommissionChoice, GameState


@dataclass
class CommissionInspector:
    """Pick the highest-tier commission the character can still complete.

    Fixes the old behaviour where every tier read as un-ranked (the list shows tier
    text, not a number) so the policy always fell back to the lowest tier.
    """

    records: dict[int, int] = field(default_factory=dict)  # option index -> suggested rank
    pending: int | None = None
    last_clicked: int | None = None
    # A commission whose 建议综合等级 is at most this many levels ABOVE our character
    # rank is still acceptable; more than this above is "too hard → pick another".
    # (User: 大于当前等级3级就选其他委托.)
    rank_tolerance: int = 3

    def decide(self, choice: CommissionChoice, state: GameState | None = None) -> Action | None:
        options = choice.options
        # 0/1 commissions: nothing to compare — let the policy handle it (exit/accept).
        if len(options) < 2:
            self.reset()
            return None

        char_rank = choice.character_rank
        if char_rank is None and state is not None:
            char_rank = state.character_rank

        # Record the suggested rank of the commission we clicked last turn: clicking
        # it selected it, so the centre detail now shows its 建议综合等级.
        if self.pending is not None and choice.selected_suggested_rank is not None:
            self.records[self.pending] = choice.selected_suggested_rank
            self.pending = None

        # Without a character rank we can't judge doability — defer to the policy's
        # conservative fallback rather than guess.
        if char_rank is None:
            self.reset()
            return None

        # Inspect each not-yet-read commission by clicking it (reveals its rank).
        unseen = [i for i in range(len(options)) if i not in self.records]
        if unseen:
            idx = unseen[0]
            self.pending = idx
            self.last_clicked = idx
            return Action("click", options[idx].target, f"inspect commission: {options[idx].rank}")

        # All read. Take the highest-tier commission whose suggested rank is within
        # tolerance; if every one is too hard (rare), take the easiest (lowest).
        limit = char_rank + self.rank_tolerance
        doable = [(i, r) for i, r in self.records.items() if r <= limit]
        if doable:
            best_idx = max(doable, key=lambda item: item[1])[0]
        else:
            best_idx = min(self.records.items(), key=lambda item: item[1])[0]
        best = options[best_idx]

        # Two-step confirm (no reliance on a parsed selected name).
        if self.last_clicked == best_idx and choice.accept_button is not None:
            self.reset()
            return Action(
                "click",
                choice.accept_button,
                f"accept commission: {best.name} ({best.rank}, 建议≤角色RANK{char_rank})",
            )
        self.last_clicked = best_idx
        return Action("click", best.target, f"select commission: {best.name} ({best.rank})")

    def reset(self) -> None:
        self.records = {}
        self.pending = None
        self.last_clicked = None
