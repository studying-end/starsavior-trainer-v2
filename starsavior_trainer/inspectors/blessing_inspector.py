"""祝福选择检视器 — 同值卡按子祝福数选最多(必须 click)。

重构自 blessing_inspector.py。卡片网格只显示属性/值, 子祝福数只在选中后右侧详情显示。
悬停(合成移动)不刷新面板(读回 0 是 bug) → 必须 CLICK 每张候选读子祝福数, 选最多。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from starsavior_trainer.models import Action, BlessingChoice, BlessingOption, GameState


@dataclass
class BlessingChoiceInspector:
    """Pick the best of several equal-value blessing cards by sub-blessing count.

    Only the right-side detail panel shows sub-blessings, and only for the currently
    *selected* card. Hovering (a synthetic move) never refreshes the panel in this
    game, so every card read back 0 — that was the bug. We CLICK each candidate
    instead (a click reliably selects it and updates the panel).
    """

    blessing_attribute_by_profile: dict[str, str]
    key: tuple[str, tuple[str, ...]] | None = None
    records: dict[str, int] = field(default_factory=dict)
    pending_name: str | None = None
    # The candidate we clicked most recently — i.e. the one currently selected.
    # Used to confirm the best card WITHOUT relying on the parsed selected_name,
    # which is ambiguous for equal-value cards.
    last_clicked: str | None = None

    def decide(self, choice: BlessingChoice, state: GameState) -> Action | None:
        attribute = state.desired_blessing_attribute or self.blessing_attribute_by_profile.get(state.build_profile, "power")
        matching = [option for option in choice.options if option.attribute == attribute and option.value is not None]
        if len(matching) < 2:
            self.reset()
            return None

        # Attribute value is primary; sub-blessings only break a tie between cards of
        # the SAME top value. A single clear top card needs no inspection.
        best_value = max(option.value for option in matching if option.value is not None)
        candidates = sorted(
            [option for option in matching if option.value == best_value],
            key=lambda option: (option.target.y, option.target.x),
        )
        if len(candidates) < 2:
            self.reset()
            return None

        candidate_names = {option.name for option in candidates}
        key = (attribute, tuple(option.name for option in candidates))
        if key != self.key:
            self.key = key
            self.records = {}
            self.pending_name = None
            self.last_clicked = None

        # Record the sub-blessing count for the card we clicked last turn.
        if self.pending_name is not None and self.pending_name in candidate_names:
            self.records[self.pending_name] = choice.detail_sub_blessing_count
            self.pending_name = None

        # Inspect each not-yet-seen candidate by clicking it.
        unseen = [option for option in candidates if option.name not in self.records]
        if unseen:
            target = unseen[0]
            self.pending_name = target.name
            self.last_clicked = target.name
            return Action("click", target.target, f"inspect {attribute} blessing {target.name}={target.value}")

        # All inspected — the winner has the most sub-blessings (ties -> earliest).
        best = max(candidates, key=lambda option: (self.records.get(option.name, 0), -option.target.y, -option.target.x))
        subs = self.records.get(best.name, 0)

        # If best is already selected (we clicked it last), confirm now.
        if self.last_clicked == best.name and choice.confirm_button is not None:
            self.reset()
            return Action("click", choice.confirm_button, f"confirm inspected {attribute} blessing: {best.name}={best.value}, sub_blessings={subs}")
        self.last_clicked = best.name
        return Action("click", best.target, f"choose inspected {attribute} blessing: {best.name}={best.value}, sub_blessings={subs}")

    def reset(self) -> None:
        self.key = None
        self.records = {}
        self.pending_name = None
        self.last_clicked = None
