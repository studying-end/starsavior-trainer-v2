"""角色选择决策 Mixin — 候选排序 + 双向滚动 + 同名多形态 + 两步确认。

重构自 policy.py decide_character_select（行 359-428）+ 模块 helper（786-828）。
坑 #14/#15: _char_pending_confirm 两步确认防翻转; 双向滚动 cap=30 覆盖上方目标。
"""
from __future__ import annotations

from starsavior_trainer.models import Action, CharacterOption, CharacterSelect, GameState, Rect

# Max character-list scrolls before giving up (≈ half down, half up). The list is
# short enough that this fully covers it in each direction.
_CHARACTER_SCROLL_CAP = 30


class CharacterSelectMixin:
    def decide_character_select(self, selection: CharacterSelect, state: GameState) -> Action:
        if state.desired_character:
            desired_variant = state.desired_variant or ""
            candidates = [
                opt
                for opt in selection.options
                if opt.name == state.desired_character
                or _character_name_matches(opt.name, state.desired_character)
            ]
            candidates.sort(
                key=lambda o: (
                    0 if o.name == state.desired_character else 1,  # exact name before substring
                    0 if (o.variant or "") == desired_variant else 1,  # then variant match
                )
            )
            match = candidates[0] if candidates else None
            if match is not None:
                self._reset_character_scroll()
                # Confirm if the game shows her selected, OR if we already clicked
                # her row last turn — the click works even when the left-panel name
                # OCR can't verify it, so a remembered click is enough to proceed.
                if match.selected or self._char_pending_confirm == match.name:
                    self._char_pending_confirm = None
                    return Action("click", selection.confirm_button, f"confirm desired character {match.name}")
                # First sighting: click her row to select, and remember we did so.
                self._char_pending_confirm = match.name
                return Action("click", match.target, f"select desired character {match.name}")

            # Not visible — search the list in BOTH directions (target may be above).
            self._char_pending_confirm = None
            scroll_target = _character_list_scroll_target(selection)
            current_names = frozenset(option.name for option in selection.options)
            if scroll_target is not None and selection.can_scroll and self._char_scroll_count < _CHARACTER_SCROLL_CAP:
                # Reverse direction exactly once: when the list stops changing (end
                # reached) or at the halfway cap, whichever comes first.
                end_reached = self._char_seen_names is not None and current_names == self._char_seen_names
                if not self._char_reversed and (end_reached or self._char_scroll_count >= _CHARACTER_SCROLL_CAP // 2):
                    self._char_scroll_down = not self._char_scroll_down
                    self._char_reversed = True
                self._char_seen_names = current_names
                self._char_scroll_count += 1
                clicks = -3 if self._char_scroll_down else 3
                direction = "down" if self._char_scroll_down else "up"
                return Action(
                    "scroll",
                    scroll_target,
                    f"scroll character list {direction} to find: {state.desired_character}",
                    scroll_clicks=clicks,
                )
            return Action("pause", None, f"desired character not found after scrolling: {state.desired_character}")

        selected = _selected_character(selection.options, selection.selected_name)
        if selected is not None:
            return Action("click", selection.confirm_button, f"confirm selected character {selected.name}")

        return Action("pause", None, "no selected character recognized")


def _selected_character(options, selected_name: str | None) -> CharacterOption | None:
    for option in options:
        if option.selected or (selected_name is not None and option.name == selected_name):
            return option
    return None


def _character_name_matches(option_name: str | None, desired: str) -> bool:
    """Tolerant character-name match: equal, or one contains the other (≥2 chars)."""
    if not option_name:
        return False

    def _norm(text: str) -> str:
        return text.replace(" ", "").replace("·", "").replace("・", "").strip()

    a = _norm(option_name)
    b = _norm(desired)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 2 and shorter in longer


def _character_list_scroll_target(selection: CharacterSelect) -> Rect | None:
    """Return a rect inside the character list suitable as a scroll anchor.

    Prefers the middle option so the scroll gesture lands at the centre.
    """
    list_options = [opt for opt in selection.options if not opt.selected]
    if not list_options:
        return None
    mid = list_options[len(list_options) // 2]
    return mid.target
