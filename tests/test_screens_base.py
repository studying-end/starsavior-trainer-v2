import unittest

from starsavior_trainer.models import GameState, Observation, Screen
from starsavior_trainer.screens.base import DelegatingScreenHandler, ScreenHandler


class ScreensBaseTest(unittest.TestCase):
    def test_delegating_has_anchor_uses_fn_and_confidence(self) -> None:
        def anchor_fn(anchors: dict[str, str]) -> bool:
            return anchors.get("hit") == "yes"

        h = DelegatingScreenHandler(
            Screen.UNKNOWN, decide_fn=lambda *a: None, anchor_fn=anchor_fn, anchor_confidence=0.9
        )

        self.assertEqual(h.has_anchor({"hit": "yes"}), (True, 0.9))
        self.assertEqual(h.has_anchor({"hit": "no"}), (False, 0.0))

    def test_delegating_has_anchor_without_fn_returns_false(self) -> None:
        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None)

        self.assertEqual(h.has_anchor({}), (False, 0.0))

    def test_delegating_parse_forwards_region_texts_and_profile(self) -> None:
        def parse_fn(region_texts, profile):
            return ("parsed", region_texts, profile)

        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None, parse_fn=parse_fn)

        self.assertEqual(h.parse({"a": 1}, "PROFILE"), ("parsed", {"a": 1}, "PROFILE"))

    def test_delegating_parse_without_fn_returns_none(self) -> None:
        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None)

        self.assertIsNone(h.parse({}, None))

    def test_delegating_decide_forwards_to_fn(self) -> None:
        def decide_fn(obs, state, policy):
            return ("decided", policy)

        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=decide_fn)

        self.assertEqual(h.decide(Observation(Screen.UNKNOWN, 1.0), GameState(), "POL"), ("decided", "POL"))

    def test_delegating_satisfies_screen_handler_protocol(self) -> None:
        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None)

        self.assertIsInstance(h, ScreenHandler)


if __name__ == "__main__":
    unittest.main()
