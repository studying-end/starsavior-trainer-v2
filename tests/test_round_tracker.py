import unittest

from starsavior_trainer.round_tracker import RoundTracker


class RoundTrackerTest(unittest.TestCase):
    def test_advances_on_date_change(self) -> None:
        t = RoundTracker()
        self.assertIsNone(t.current_round)
        self.assertEqual(t.observe_date("3月上旬"), 1)
        self.assertEqual(t.observe_date("3月上旬"), 1)  # 同日期不增
        self.assertEqual(t.observe_date("3月中旬"), 2)  # 变化 +1

    def test_unparseable_date_does_not_advance(self) -> None:
        # 坑 #29: 读丢月份数字("月下旬")→无法解析→不前进(避免 3月上旬 vs 4月上旬 碰撞)
        t = RoundTracker()
        t.observe_date("3月上旬")
        # 无法解析 → 返回当前 round(不前进), 不是 None
        self.assertEqual(t.observe_date("月下旬"), 1)
        self.assertEqual(t.current_round, 1)  # 不前进

    def test_reset(self) -> None:
        t = RoundTracker()
        t.observe_date("3月上旬")
        t.reset()
        self.assertIsNone(t.current_round)


if __name__ == "__main__":
    unittest.main()
