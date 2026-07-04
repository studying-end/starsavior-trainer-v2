"""Tests for cli.live_loop helpers — OCR factory + emergency-stop wiring.

main() 的 12 步主循环本身依赖窗口/OCR/分类器实跑，其离线回放驱动测试归 T17
(offline_harness) / T18。此处覆盖可单测的 helper：_create_ocr 回退、急停 predicate。
"""
import unittest
from unittest import mock

from starsavior_trainer.cli.live_loop import _create_ocr
from starsavior_trainer.ocr import NoopOcrEngine, RapidOcrEngine


class CreateOcrTest(unittest.TestCase):
    def test_noop_when_ocr_not_requested(self) -> None:
        self.assertIsInstance(_create_ocr(False), NoopOcrEngine)

    def test_falls_back_to_noop_when_ocr_unavailable(self) -> None:
        # RapidOCR missing/unusable → RuntimeError caught → NoopOcrEngine fallback.
        with mock.patch.object(RapidOcrEngine, "__init__", side_effect=RuntimeError("rapidocr not installed")):
            self.assertIsInstance(_create_ocr(True), NoopOcrEngine)


if __name__ == "__main__":
    unittest.main()
