"""事件决策 Mixin — DB→攻击/生存分支→关键词 三级降级。

重构自 policy.py decide_event 及其 helper（行 543-629）。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Action, EventOption, GameState
from starsavior_trainer.policy.event_db import (
    DEFAULT_EVENT_KEYWORDS,
    _event_recommended_index,
    _load_event_db,
    _match_event,
)


class EventMixin:
    # Profiles that prefer the "survival/生存" branch in attack-vs-survival events.
    _SURVIVAL_PROFILES = ("stamina_tank", "durability_focus", "protection_focus")

    def event_priority(self, option: EventOption) -> tuple[int, str]:
        text = option.text.lower()
        if any(keyword.lower() in text for keyword in DEFAULT_EVENT_KEYWORDS["fatigue_cost"]):
            return -1000, "avoid fatigue cost"
        if any(keyword.lower() in text for keyword in DEFAULT_EVENT_KEYWORDS["coin_cost"]):
            return 400, "spend coins"
        if any(keyword.lower() in text for keyword in DEFAULT_EVENT_KEYWORDS["recover"]):
            return 300, "recover stamina"
        if any(keyword.lower() in text for keyword in DEFAULT_EVENT_KEYWORDS["mood"]):
            return 200, "improve mood"
        if any(keyword.lower() in text for keyword in DEFAULT_EVENT_KEYWORDS["attribute"]):
            return 100, "gain attributes"
        return 0, "unknown option"

    def _event_db_choice(
        self, options: list[EventOption], state: GameState | None
    ) -> tuple[EventOption, str] | None:
        """Look the event up in config/events.json and return its recommended option."""
        if not options:
            return None
        title = options[0].event_title
        if not title:
            return None
        event = _match_event(title, _load_event_db())
        if event is None:
            return None
        profile = state.build_profile if state else "balanced"
        index = _event_recommended_index(event, profile)
        if index is None or not (1 <= index <= len(options)):
            return None
        reason = f"event db: {event.get('title', '')} build={profile} -> option {index}"
        return options[index - 1], reason

    def _build_orientation_choice(
        self, options: list[EventOption], state: GameState | None
    ) -> tuple[EventOption, str] | None:
        """For attack-vs-survival branching events, pick by the character build."""
        if state is None:
            return None
        attack = next((o for o in options if ("攻击" in o.text or "攻撃" in o.text)), None)
        survival = next((o for o in options if "生存" in o.text), None)
        if attack is None or survival is None:
            return None
        if state.build_profile in self._SURVIVAL_PROFILES:
            return survival, f"build {state.build_profile} -> survival training"
        return attack, f"build {state.build_profile} -> attack training"

    def decide_event(self, options: Iterable[EventOption], state: GameState | None = None) -> Action:
        options = list(options)

        # 1) Event database lookup
        db_choice = self._event_db_choice(options, state)
        if db_choice is not None:
            choice, reason = db_choice
            return Action("click", choice.target, f"{reason}: {choice.text}")

        # 2) Generic attack-vs-survival branch fallback
        oriented = self._build_orientation_choice(options, state)
        if oriented is not None:
            choice, reason = oriented
            return Action("click", choice.target, f"{reason}: {choice.text}")

        # 3) Keyword heuristic
        ranked = sorted(
            ((self.event_priority(option), option) for option in options),
            key=lambda item: item[0][0],
            reverse=True,
        )
        if not ranked:
            return Action("pause", None, "no event options recognized")

        (score, reason), best = ranked[0]
        return Action("click", best.target, f"{reason}: {best.text}", confidence=0.7 if score == 0 else 1.0)
