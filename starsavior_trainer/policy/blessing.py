"""祝福决策 Mixin — setup 装备空槽 + choice 两步确认 + 同值卡选最高。

重构自 policy.py decide_blessing_setup/choice/blessing_score（行 430-468）。
坑 #13: 同值卡 selected_name 不可靠, _pending_blessing 两步确认防翻转。
"""
from __future__ import annotations

from starsavior_trainer.models import Action, BlessingChoice, BlessingOption, BlessingSetup, GameState


class BlessingMixin:
    def decide_blessing_setup(self, setup: BlessingSetup) -> Action:
        empty_slots = [slot for slot in setup.slots if not slot.occupied]
        if empty_slots:
            first = sorted(empty_slots, key=lambda slot: slot.index)[0]
            return Action("click", first.target, f"open blessing slot {first.index}")
        if setup.can_confirm:
            return Action("click", setup.confirm_button, "all blessing slots filled, confirm")
        return Action("pause", None, "all blessing slots filled but confirm is disabled")

    def decide_blessing_choice(self, choice: BlessingChoice, state: GameState) -> Action:
        # Two-step confirm: we clicked a blessing last frame — confirm it now instead
        # of re-picking. Same-value cards are indistinguishable by selected_name (OCR),
        # and the sub-blessing count flickers frame-to-frame. Lock the first pick.
        if self._pending_blessing is not None and choice.confirm_button is not None:
            target = self._pending_blessing
            self._pending_blessing = None
            return Action("click", target, "confirm chosen blessing")

        attribute = state.desired_blessing_attribute or self.config.blessing_attribute_by_profile.get(state.build_profile, "power")
        matching = [option for option in choice.options if option.attribute == attribute and option.value is not None]
        if not matching:
            return Action("pause", None, f"no {attribute} blessing option with recognized value")

        # Highest value wins; ties broken by position (topmost-leftmost) — NOT by
        # sub-blessing count, which OCR can't read reliably.
        best = max(matching, key=self.blessing_score)
        if choice.confirm_button is not None:
            self._pending_blessing = choice.confirm_button
        return Action(
            "click",
            best.target,
            f"choose {attribute} blessing: {best.name}={best.value}",
        )

    def blessing_score(self, option: BlessingOption) -> tuple[int, int, int, str]:
        value = option.value if option.value is not None else -1
        return (value, -option.target.y, -option.target.x, option.name)
