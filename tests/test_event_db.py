"""§22.14 事件自动入库测试。

覆盖 event_db.find_event_exact / save_event / _clear_cache + decide_event 自动入库。
"""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from starsavior_trainer.models import EventOption, GameState, Rect
from starsavior_trainer.policy import event_db
from starsavior_trainer.policy.event import EventMixin


class _DummyPolicy(EventMixin):
    pass


class FindEventExactTest(unittest.TestCase):
    def test_exact_match(self) -> None:
        events = [{"title": "训练的方向"}, {"title": "神秘商人"}]
        self.assertIsNotNone(event_db.find_event_exact(events, "训练的方向"))

    def test_no_match(self) -> None:
        events = [{"title": "训练的方向"}]
        self.assertIsNone(event_db.find_event_exact(events, "神秘商人"))

    def test_empty_title(self) -> None:
        self.assertIsNone(event_db.find_event_exact([], ""))


class SaveEventTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "events.json"

    def test_save_new_event_writes_default_rules_choose_1(self) -> None:
        """新事件入库 → 写 default_rules choose_option:1。"""
        event_db.save_event("神秘事件", ["选项A", "选项B"], choose_option=1, path=self.db_path)
        data = json.loads(self.db_path.read_text(encoding="utf-8"))
        event = data["events"][0]
        self.assertEqual(event["title"], "神秘事件")
        self.assertEqual(event["default_rules"][0]["choose_option"], 1)
        self.assertEqual(event["default_rules"][0]["profile"], "default")
        self.assertEqual(len(event["options"]), 2)

    def test_save_does_not_overwrite_existing(self) -> None:
        """已存在(精确名)→ 不覆盖(保留用户手填规则)。"""
        # 先手填一个 choose_option:2
        data = {"schema": "starsavior.events.v1", "events": [
            {"title": "神秘事件", "default_rules": [{"profile": "default", "choose_option": 2}]}
        ]}
        self.db_path.write_text(json.dumps(data), encoding="utf-8")
        # 自动入库同标题 → 不覆盖
        event_db.save_event("神秘事件", ["选项A"], choose_option=1, path=self.db_path)
        data2 = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data2["events"]), 1)  # 没新增
        self.assertEqual(data2["events"][0]["default_rules"][0]["choose_option"], 2)  # 保留手填

    def test_clear_cache_after_save(self) -> None:
        """save_event 后 _EVENT_DB_CACHE 应清空(下次 _load_event_db 重读)。"""
        # 先加载(填充缓存)
        event_db._EVENT_DB_CACHE = [{"title": "旧"}]
        event_db.save_event("新事件", ["选项"], path=self.db_path)
        self.assertIsNone(event_db._EVENT_DB_CACHE)  # 已清


class DecideEventAutoInsertTest(unittest.TestCase):
    """§22.14 decide_event 未入库事件 → 自动入库 + 选第1个选项。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "events.json"
        # 空 events.json
        self.db_path.write_text(
            json.dumps({"schema": "starsavior.events.v1", "events": []}), encoding="utf-8"
        )
        # 临时替换 event_db 的 _EVENTS_PATH + 清缓存
        self._orig_path = event_db._EVENTS_PATH
        event_db._EVENTS_PATH = self.db_path
        event_db._clear_cache()

    def tearDown(self) -> None:
        event_db._EVENTS_PATH = self._orig_path
        event_db._clear_cache()

    def test_unknown_event_auto_inserted_and_picks_option_1(self) -> None:
        """未入库事件 → 自动入库 + decide_event 选第1个选项。"""
        policy = _DummyPolicy()
        options = [
            EventOption(text="选项A", target=Rect(100, 100, 50, 50), event_title="全新事件"),
            EventOption(text="选项B", target=Rect(200, 100, 50, 50), event_title="全新事件"),
        ]
        action = policy.decide_event(options, GameState(build_profile="balanced"))
        # 应选第1个选项(刚入库写 choose_option:1)
        self.assertEqual(action.target, Rect(100, 100, 50, 50))
        # 验证入库了
        events = event_db._load_event_db()
        self.assertIsNotNone(event_db.find_event_exact(events, "全新事件"))

    def test_known_event_uses_existing_rules(self) -> None:
        """已入库事件 → 用已有规则(不重新入库)。"""
        # 预置一个 choose_option:2 的事件
        data = {"schema": "starsavior.events.v1", "events": [
            {"title": "已知事件", "default_rules": [{"profile": "default", "choose_option": 2}]}
        ]}
        self.db_path.write_text(json.dumps(data), encoding="utf-8")
        event_db._clear_cache()

        policy = _DummyPolicy()
        options = [
            EventOption(text="选项A", target=Rect(100, 100, 50, 50), event_title="已知事件"),
            EventOption(text="选项B", target=Rect(200, 100, 50, 50), event_title="已知事件"),
        ]
        action = policy.decide_event(options, GameState(build_profile="balanced"))
        # 应选第2个选项(已有规则 choose_option:2)
        self.assertEqual(action.target, Rect(200, 100, 50, 50))


if __name__ == "__main__":
    unittest.main()
