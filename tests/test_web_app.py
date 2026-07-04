"""Tests for web/app.py 路由 + web/process_manager.py 单进程锁 + SSE 日志流。

用 Flask test_client 测路由；单进程锁用 fake alive 进程测 guard（确定性、无需真并发）。
"""
import sys
import unittest

from starsavior_trainer.web import process_manager
from starsavior_trainer.web.app import app


def _drain_queue() -> str:
    logs = []
    while not process_manager.log_queue.empty():
        try:
            logs.append(process_manager.log_queue.get_nowait())
        except Exception:
            break
    return "".join(logs)


class WebAppRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        process_manager.current_process = None

    def test_config_endpoint(self) -> None:
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("profiles", data)
        self.assertIn("build_profiles", data)
        self.assertEqual(len(data["build_profiles"]), 6)
        self.assertEqual(len(data["classify_modes"]), 5)

    def test_process_status_idle(self) -> None:
        resp = self.client.get("/api/process/status")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["running"])

    def test_process_stop_when_idle(self) -> None:
        resp = self.client.post("/api/process/stop")
        self.assertFalse(resp.get_json()["success"])

    def test_train_requires_character(self) -> None:
        resp = self.client.post("/api/train/start", json={})
        self.assertEqual(resp.status_code, 400)

    def test_log_stream_emits_queued_log(self) -> None:
        process_manager.log_queue.put("streamed_line\n")
        resp = self.client.get("/api/logs/stream")
        chunk = next(resp.response)
        resp.close()
        self.assertIn("streamed_line", chunk.decode("utf-8"))


class ProcessLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_process = process_manager.current_process
        process_manager.current_process = None
        _drain_queue()

    def tearDown(self) -> None:
        if process_manager.current_process and hasattr(process_manager.current_process, "terminate"):
            if process_manager.current_process.poll() is None:
                process_manager.current_process.terminate()
        process_manager.current_process = None

    def test_runs_command_when_idle(self) -> None:
        # happy path：空闲时跑命令，输出 + [DONE] 入队。
        process_manager._run_command([sys.executable, "-c", "print('hello_world')"])
        joined = _drain_queue()
        self.assertIn("hello_world", joined)
        self.assertIn("[DONE]", joined)

    def test_rejects_second_command_while_running(self) -> None:
        # 单进程锁：模拟"运行中"进程 (poll() 返 None)，第二次 _run_command 应被拒、不执行。
        class _Alive:
            def poll(self):
                return None

        process_manager.current_process = _Alive()
        process_manager._run_command([sys.executable, "-c", "print('SHOULD_NOT_RUN')"])

        joined = _drain_queue()
        self.assertIn("已有进程在运行", joined)
        self.assertNotIn("SHOULD_NOT_RUN", joined)


if __name__ == "__main__":
    unittest.main()
