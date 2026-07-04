"""简单决策 Mixin — 旅程起点/确认框/事件快进/对话/休息。

重构自 policy.py decide_journey_start/confirm_dialog/event_fast_forward_setting/dialogue/rest
（行 470-541）。dialogue 用 repeat=3 连点过场; rest 两步确认 + 冥想室优先。
"""
from __future__ import annotations

from starsavior_trainer.models import (
    Action,
    ConfirmDialog,
    DialogueScene,
    EventFastForwardSetting,
    JourneyStart,
    RestSubmenu,
)


class SimpleMixin:
    def decide_journey_start(self, journey: JourneyStart) -> Action:
        return Action("click", journey.start_button, "arcana is fixed, click journey start")

    def decide_confirm_dialog(self, dialog: ConfirmDialog) -> Action:
        return Action("click", dialog.confirm_button, f"confirm dialog: {dialog.title}")

    def decide_event_fast_forward_setting(self, setting: EventFastForwardSetting) -> Action:
        if setting.selected_mode == "all_events":
            return Action("click", setting.confirm_button, "confirm fast-forward all events")
        return Action("click", setting.all_events_option, "select fast-forward all events")

    def decide_dialogue(self, dialogue: DialogueScene) -> Action:
        # A small, calm burst of skip taps per frame (executor paces them at ~5 Hz).
        return Action("click", dialogue.skip_button, f"dialogue {dialogue.variant}, click skip", repeat=3)

    def decide_rest(self, rest: RestSubmenu) -> Action:
        # §22.3 休息策略（REST_SUBMENU 层，已决定休息）。依据：心情(mood) + 耐力(endurance)
        # + 金币(coins)，从最近一次 TRAINING_HUB 缓存。命名红线: endurance=耐力(训练资源)。
        #   心情≠BEST（或早期人头≤1）→ 住处回心情; 钱不够则露宿
        #   心情BEST + 耐力<40% → 有钱冥想室; 没钱露宿
        #   心情BEST + 耐力≥40% → 露宿（免费）
        mood = self._cached_mood
        endurance = self._cached_endurance
        if self._rest_for_mood or (mood is not None and mood != "BEST"):
            if rest.coins >= self.config.lodging_coin_threshold and rest.lodging is not None:
                target, label = rest.lodging, "lodging (心情≠BEST 回心情)"
            else:
                target, label = rest.rough_sleep, "rough_sleep (心情≠BEST 钱不够住处)"
        elif endurance < self.config.rest_endurance_threshold:
            if rest.coins >= self.config.meditation_coin_threshold and rest.has_meditation_room and rest.meditation_room is not None:
                target, label = rest.meditation_room, "meditation_room (耐力低+有钱)"
            else:
                target, label = rest.rough_sleep, "rough_sleep (耐力低+没钱)"
        else:
            target, label = rest.rough_sleep, "rough_sleep (心情BEST+耐力足)"

        # Two-step flow: select the option, then click the 休息 confirm button.
        if rest.confirm_button is None:
            self._pending_rest = None
            self._rest_for_mood = False
            return Action("click", target, f"rest: {label}")
        if self._pending_rest == target:
            self._pending_rest = None
            self._rest_for_mood = False
            return Action("click", rest.confirm_button, f"confirm rest: {label}")
        self._pending_rest = target
        return Action("click", target, f"select rest: {label}")
