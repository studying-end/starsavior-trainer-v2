import unittest

from starsavior_trainer.models import Screen
from starsavior_trainer.screens import ANCHOR_HANDLERS, HANDLERS, rebuild_anchor_handlers
from starsavior_trainer.screens.base import DelegatingScreenHandler


class ScreensRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        HANDLERS.clear()
        rebuild_anchor_handlers()

    def tearDown(self) -> None:
        # 恢复空注册表，避免 fake handler 残留污染模块级状态。
        HANDLERS.clear()
        rebuild_anchor_handlers()

    def test_initially_empty(self) -> None:
        self.assertEqual(HANDLERS, {})
        self.assertEqual(ANCHOR_HANDLERS, [])

    def test_register_and_lookup(self) -> None:
        h = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None)

        HANDLERS[Screen.UNKNOWN] = h

        self.assertIs(HANDLERS[Screen.UNKNOWN], h)

    def test_rebuild_keeps_only_anchor_handlers_sorted_by_priority(self) -> None:
        with_anchor_hi = DelegatingScreenHandler(
            Screen.REWARD, decide_fn=lambda *a: None, priority=2,
            anchor_fn=lambda a: True, anchor_confidence=1.0,
        )
        with_anchor_lo = DelegatingScreenHandler(
            Screen.INITIAL, decide_fn=lambda *a: None, priority=1,
            anchor_fn=lambda a: True, anchor_confidence=1.0,
        )
        no_anchor = DelegatingScreenHandler(Screen.UNKNOWN, decide_fn=lambda *a: None)
        for h in (with_anchor_hi, with_anchor_lo, no_anchor):
            HANDLERS[h.screen] = h

        rebuild_anchor_handlers()

        # 无 anchor_fn 的被排除；剩下的按 priority 升序。
        self.assertEqual(ANCHOR_HANDLERS, [with_anchor_lo, with_anchor_hi])


if __name__ == "__main__":
    unittest.main()
