"""Tests for cli.offline_harness — 离线回放驱动识别+决策管线 + record/target helper。"""
import argparse
import unittest

from starsavior_trainer.cli.offline_harness import _load_inputs, _record, _target
from starsavior_trainer.models import Action, Observation, Rect, Screen
from starsavior_trainer.policy.engine import TrainerPolicy


class OfflineHarnessHelpersTest(unittest.TestCase):
    def test_target_none_when_no_target(self) -> None:
        self.assertIsNone(_target(Action("pause", None, "r")))

    def test_target_dict_when_rect(self) -> None:
        d = _target(Action("click", Rect(10, 20, 30, 40), "r"))
        assert d is not None
        self.assertEqual(d["x"], 10)
        self.assertEqual(d["width"], 30)
        self.assertEqual(d["center_x"], 25)  # 10 + 30 // 2
        self.assertEqual(d["center_y"], 40)  # 20 + 40 // 2

    def test_record_shape(self) -> None:
        obs = Observation(screen=Screen.UNKNOWN, confidence=0.5, source="demo")
        rec = _record(1, obs, Action("click", Rect(0, 0, 1, 1), "r"))
        self.assertEqual(rec["index"], 1)
        self.assertEqual(rec["screen"], "unknown")
        self.assertEqual(rec["action"], "click")
        self.assertEqual(rec["source"], "demo")


class OfflineHarnessPipelineTest(unittest.TestCase):
    def test_load_inputs_demo_default(self) -> None:
        args = argparse.Namespace(manifest=None, screenshots=None)
        state, observations = _load_inputs(args)
        self.assertIsNotNone(state)
        self.assertGreater(len(observations), 0)

    def test_demo_pipeline_runs_decide(self) -> None:
        # 离线回放跑通识别+决策管线：demo observations 经 policy.decide 全程不抛错。
        args = argparse.Namespace(manifest=None, screenshots=None)
        state, observations = _load_inputs(args)
        policy = TrainerPolicy()
        for observation in observations:
            action = policy.decide(state, observation)
            self.assertIsNotNone(action)  # decide 总返回一个 Action


if __name__ == "__main__":
    unittest.main()
