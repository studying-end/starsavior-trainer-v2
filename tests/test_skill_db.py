"""潜质模板库 (skill_db) 单元测试。

覆盖：
- infer_kind: 按名尾字推断类型（感知/技巧/天赋/通用）
- load_skills / find_skill / save_skill: 加载/查找/自动入库（含 upsert 保留 priority）
"""
import tempfile
import unittest
from pathlib import Path

from starsavior_trainer import skill_db


class InferKindTest(unittest.TestCase):
    def test_感知_suffix(self) -> None:
        self.assertEqual(skill_db.infer_kind("破坏感知"), "感知")
        self.assertEqual(skill_db.infer_kind("攻击感知"), "感知")

    def test_技巧_suffix(self) -> None:
        self.assertEqual(skill_db.infer_kind("攻击技巧"), "技巧")

    def test_天赋_suffix(self) -> None:
        self.assertEqual(skill_db.infer_kind("攻击天赋"), "天赋")

    def test_generic_when_no_known_suffix(self) -> None:
        self.assertEqual(skill_db.infer_kind("未知技能"), "通用")
        self.assertEqual(skill_db.infer_kind(""), "通用")


class LoadFindSaveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "skills.json"

    def test_save_then_load_then_find(self) -> None:
        """首次入库 → load → find 能查到。"""
        skill_db.save_skill(self.db_path, "破坏感知", "暴击伤害增加", kind="感知")
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(len(entries), 1)
        e = skill_db.find_skill(entries, "破坏感知")
        self.assertIsNotNone(e)
        self.assertEqual(e.kind, "感知")
        self.assertEqual(e.battle_priority, 99)  # 默认
        self.assertEqual(e.breeding_priority, 99)

    def test_kind_auto_inferred_when_not_specified(self) -> None:
        """save_skill 不传 kind → 按名尾字自动推断。"""
        skill_db.save_skill(self.db_path, "攻击技巧", "效果")
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(entries[0].kind, "技巧")

    def test_priority_explicit(self) -> None:
        """显式传 battle_priority/breeding_priority → 写入对应值。"""
        skill_db.save_skill(self.db_path, "破坏感知", "", battle_priority=0, breeding_priority=3)
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(entries[0].battle_priority, 0)
        self.assertEqual(entries[0].breeding_priority, 3)

    def test_upsert_preserves_priority(self) -> None:
        """同名再次入库(不传 priority) → 保留用户手填 priority 不被覆盖。"""
        skill_db.save_skill(self.db_path, "破坏感知", "", battle_priority=0, breeding_priority=2)
        # 自动入库(不传 priority) → 应保留 0/2
        skill_db.save_skill(self.db_path, "破坏感知", "暴击伤害增加(更新)")
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].battle_priority, 0)  # 保留
        self.assertEqual(entries[0].breeding_priority, 2)  # 保留
        self.assertEqual(entries[0].effect, "暴击伤害增加(更新)")  # effect 更新

    def test_upsert_overwrite_priority_when_explicit(self) -> None:
        """显式传 priority → 覆盖（用户调整优先级）。"""
        skill_db.save_skill(self.db_path, "破坏感知", "", battle_priority=0)
        skill_db.save_skill(self.db_path, "破坏感知", "", battle_priority=5)
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(entries[0].battle_priority, 5)

    def test_find_not_found_returns_none(self) -> None:
        """find 找不到 → None。"""
        skill_db.save_skill(self.db_path, "破坏感知", "")
        entries = skill_db.load_skills(self.db_path)
        self.assertIsNone(skill_db.find_skill(entries, "不存在"))

    def test_find_empty_name_returns_none(self) -> None:
        """空名 → None。"""
        self.assertIsNone(skill_db.find_skill([], ""))

    def test_load_empty(self) -> None:
        """文件不存在 → 空 list。"""
        self.assertEqual(skill_db.load_skills(self.tmpdir + "/nonexistent.json"), [])

    def test_load_corrupted(self) -> None:
        """文件损坏 → 空 list。"""
        self.db_path.write_text("not json {{{", encoding="utf-8")
        self.assertEqual(skill_db.load_skills(self.db_path), [])

    def test_priority_zero_not_falsy(self) -> None:
        """priority=0 不能被当 falsy 替换成 99（最优先=0）。"""
        skill_db.save_skill(self.db_path, "破坏感知", "", battle_priority=0)
        entries = skill_db.load_skills(self.db_path)
        self.assertEqual(entries[0].battle_priority, 0)


if __name__ == "__main__":
    unittest.main()
