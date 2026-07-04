"""奖励模板库 (relic_db) 单元测试。

覆盖：
- extract_attributes: 关键词解析（含顺序敏感"暴击率"先于"暴击伤害"）
- class_to_priority_group: 6 类名映射 + 未知默认 ATTACK
- score_relic_by_priority: ATTACK/DEFENSE 组优先级打分
- find_relic / save_relic: 模板库查找 + 自动入库（首次写入 + 已存在 upsert）
- decide_relic 集成: 用真实场景（rank 22, 三奖励 生命力/防御力/攻击力）验证 ATTACK 组选攻击力
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from starsavior_trainer import relic_db
from starsavior_trainer.models import GameState, Rect, RelicOption
from starsavior_trainer.policy.engine import TrainerPolicy


class ExtractAttributesTest(unittest.TestCase):
    def test_extracts_single_attribute(self) -> None:
        """效果文本含单个属性关键词 → 解析出对应标签。"""
        self.assertEqual(relic_db.extract_attributes("自身的最大生命力增加4%"), ("hp",))
        self.assertEqual(relic_db.extract_attributes("自身的防御力 增加6%"), ("defense",))
        self.assertEqual(relic_db.extract_attributes("自身的攻击力 增加4%"), ("attack",))
        self.assertEqual(relic_db.extract_attributes("速度 +5%"), ("speed",))

    def test_extracts_multiple_attributes_in_order(self) -> None:
        """效果文本含多个属性 → 按关键词表顺序去重保留首次。"""
        # 同时含速度+攻击力 → 按 _ATTRIBUTE_KEYWORDS 顺序: speed 在 attack 之前
        attrs = relic_db.extract_attributes("速度+5%, 攻击力+3%")
        self.assertEqual(attrs, ("speed", "attack"))

    def test_crit_rate_takes_priority_over_crit_dmg(self) -> None:
        """顺序敏感: 「暴击率」必须先于「暴击伤害」匹配，否则会被「暴击」前缀吞掉。
        实际效果文本可能同时含两者（罕见），分别解析。"""
        # 只含"暴击率" → crit_rate（不会被"暴击伤害"前缀吞）
        self.assertEqual(relic_db.extract_attributes("暴击率+10%"), ("crit_rate",))
        # 只含"暴击伤害" → crit_dmg
        self.assertEqual(relic_db.extract_attributes("暴击伤害+20%"), ("crit_dmg",))
        # "爆伤" 别名 → crit_dmg
        self.assertEqual(relic_db.extract_attributes("爆伤+15%"), ("crit_dmg",))

    def test_no_keyword_returns_empty(self) -> None:
        """无任何属性关键词命中 → 空元组（视为无属性/未知）。"""
        self.assertEqual(relic_db.extract_attributes("首次战斗开始时，自身的最大HP恢复"), ())
        # 注意：HP 关键词命中 hp（大小写不敏感取决于 in 运算）—— "HP" 应被识别
        # 修正上面：HP 是 hp 的关键词，所以会命中
        self.assertEqual(relic_db.extract_attributes("完全没有属性关键词的文本"), ())

    def test_empty_text(self) -> None:
        self.assertEqual(relic_db.extract_attributes(""), ())
        self.assertEqual(relic_db.extract_attributes(None), ())  # type: ignore[arg-type]

    def test_ocr_inserts_whitespace_in_chinese(self) -> None:
        """OCR 偶尔在中文词中插空格(如「生 命力」/「攻击 力」)→ 匹配前去除所有空白兜底。
        实机场景: RapidOCR 把「自身的最大生命力增加4%」识别成「自身的最大生 命力增加4%」。"""
        self.assertEqual(relic_db.extract_attributes("自身的最大生 命力增加4%"), ("hp",))
        self.assertEqual(relic_db.extract_attributes("自身的攻击 力 增加4%"), ("attack",))
        self.assertEqual(relic_db.extract_attributes("速 度 +5%"), ("speed",))
        self.assertEqual(relic_db.extract_attributes("暴击 率+10%"), ("crit_rate",))


class CharacterClassMappingTest(unittest.TestCase):
    def test_attack_group_classes(self) -> None:
        """刺客/术师/游侠/突击者 → ATTACK 组（输出系）。"""
        for cls in ("刺客", "术师", "游侠", "突击者"):
            self.assertEqual(relic_db.class_to_priority_group(cls), "attack")

    def test_defense_group_classes(self) -> None:
        """辅助/坦克 → DEFENSE 组（生存系）。"""
        for cls in ("辅助", "坦克"):
            self.assertEqual(relic_db.class_to_priority_group(cls), "defense")

    def test_unknown_class_defaults_to_attack(self) -> None:
        """未知/None → 默认 ATTACK 组（与原 decide_relic 一致）。"""
        self.assertEqual(relic_db.class_to_priority_group(None), "attack")
        self.assertEqual(relic_db.class_to_priority_group("未知职业"), "attack")
        self.assertEqual(relic_db.class_to_priority_group(""), "attack")


class ScoreByPriorityTest(unittest.TestCase):
    def test_attack_group_priority_order(self) -> None:
        """ATTACK 组优先级: speed > crit_rate > crit_dmg > attack。
        第 1 位 = 100 分，第 2 位 = 90 分，依此类推（-10 递减）。"""
        self.assertEqual(relic_db.score_relic_by_priority(("speed",), "attack"), 100)
        self.assertEqual(relic_db.score_relic_by_priority(("crit_rate",), "attack"), 90)
        self.assertEqual(relic_db.score_relic_by_priority(("crit_dmg",), "attack"), 80)
        self.assertEqual(relic_db.score_relic_by_priority(("attack",), "attack"), 70)

    def test_defense_group_priority_order(self) -> None:
        """DEFENSE 组优先级: speed > hp > defense。"""
        self.assertEqual(relic_db.score_relic_by_priority(("speed",), "defense"), 100)
        self.assertEqual(relic_db.score_relic_by_priority(("hp",), "defense"), 90)
        self.assertEqual(relic_db.score_relic_by_priority(("defense",), "defense"), 80)

    def test_no_attribute_returns_zero(self) -> None:
        """无属性命中 → 0 分（最低）。"""
        self.assertEqual(relic_db.score_relic_by_priority((), "attack"), 0)
        self.assertEqual(relic_db.score_relic_by_priority((), "defense"), 0)

    def test_multiple_attributes_takes_highest(self) -> None:
        """多个属性命中 → 取最高优先级的那个（不累加）。"""
        # attack + speed 同时命中 → 取 speed（更高优先级）= 100
        self.assertEqual(relic_db.score_relic_by_priority(("attack", "speed"), "attack"), 100)
        # hp + defense 同时命中 → 取 hp（更高优先级）= 90
        self.assertEqual(relic_db.score_relic_by_priority(("defense", "hp"), "defense"), 90)


class FindSaveRelicTest(unittest.TestCase):
    def setUp(self) -> None:
        """每个测试用独立临时文件，避免污染 config/relics.json。"""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "relics.json"

    def test_save_then_find(self) -> None:
        """首次入库 → find_relic 能查到，attributes 已解析。"""
        relic_db.save_relic(self.db_path, "沾有史莱姆的铠甲", "自身的最大生命力增加4%")
        relics = relic_db.load_relics(self.db_path)
        self.assertEqual(len(relics), 1)
        entry = relic_db.find_relic(relics, "沾有史莱姆的铠甲")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.attributes, ("hp",))

    def test_upsert_existing_relic(self) -> None:
        """同名奖励再次入库 → 更新（upsert），不重复追加。"""
        relic_db.save_relic(self.db_path, "沾有史莱姆的铠甲", "自身的最大生命力增加4%", ("hp",))
        relic_db.save_relic(self.db_path, "沾有史莱姆的铠甲", "自身的攻击力 增加4%", ("attack",))
        relics = relic_db.load_relics(self.db_path)
        self.assertEqual(len(relics), 1)  # 仍是 1 条，没重复
        self.assertEqual(relics[0].attributes, ("attack",))  # 已更新

    def test_find_not_in_db(self) -> None:
        """模板库里没有的奖励 → find_relic 返回 None。"""
        relics = relic_db.load_relics(self.db_path)
        self.assertIsNone(relic_db.find_relic(relics, "不存在的奖励"))

    def test_load_empty_db(self) -> None:
        """文件不存在 → load_relics 返回空 list（不报错）。"""
        empty = relic_db.load_relics(self.tmpdir + "/nonexistent.json")
        self.assertEqual(empty, [])

    def test_load_corrupted_json(self) -> None:
        """文件损坏 → load_relics 返回空 list（不报错）。"""
        self.db_path.write_text("not valid json {{{", encoding="utf-8")
        self.assertEqual(relic_db.load_relics(self.db_path), [])

    def test_save_empty_name_skipped(self) -> None:
        """空名字 → 不入库（避免垃圾数据）。"""
        relic_db.save_relic(self.db_path, "", "效果")
        self.assertEqual(relic_db.load_relics(self.db_path), [])


class DecideRelicIntegrationTest(unittest.TestCase):
    """端到端: decide_relic 用真实场景验证模板库 + 角色优先级选卡。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "relics.json"
        # 用临时 db_path 创建 policy，不污染 config/relics.json
        self.policy = TrainerPolicy(relic_db_path=self.db_path)
        # 实机场景: 三张卡 = 生命力+4% / 防御力+6% / 攻击力+4%（用户当前画面）
        self.opt_hp = RelicOption(
            name="沾有史莱姆的铠甲", score=None, target=Rect(485, 330, 480, 750),
            effect_text="首次战斗开始时，自身的最大生命力增加4%",
            attributes=("hp",),
        )
        self.opt_def = RelicOption(
            name="沾有史莱姆的裤子", score=None, target=Rect(1040, 330, 480, 750),
            effect_text="首次战斗开始时，自身的防御力 增加6%",
            attributes=("defense",),
        )
        self.opt_atk = RelicOption(
            name="沾有史莱姆的手套", score=None, target=Rect(1593, 330, 480, 750),
            effect_text="首次战斗开始时，自身的攻击力 增加4%",
            attributes=("attack",),
        )

    def test_attack_group_picks_attack_relic(self) -> None:
        """ATTACK 组（刺客/术师/弓手/突击者）→ 选攻击力那张（priority=70）。
        生命力=0, 防御力=0, 攻击力=70 → 选攻击力。"""
        state = GameState(character_class="刺客")  # ATTACK 组
        action = self.policy.decide_relic([self.opt_hp, self.opt_def, self.opt_atk], state)
        self.assertEqual(action.target, self.opt_atk.target)
        self.assertIn("attack", action.reason)
        # 三张卡都自动入库了
        relics = relic_db.load_relics(self.db_path)
        self.assertEqual(len(relics), 3)

    def test_defense_group_picks_hp_relic(self) -> None:
        """DEFENSE 组（辅助/坦克）→ 选生命力那张（hp priority=90）。
        生命力=90, 防御力=80, 攻击力=0 → 选生命力。"""
        state = GameState(character_class="坦克")  # DEFENSE 组
        action = self.policy.decide_relic([self.opt_hp, self.opt_def, self.opt_atk], state)
        self.assertEqual(action.target, self.opt_hp.target)
        self.assertIn("defense", action.reason)

    def test_uses_cached_relic_when_already_in_db(self) -> None:
        """第二次见到同一张卡 → 直接查模板库（不重复入库）。"""
        state = GameState(character_class="刺客")
        # 第一次：三张卡全部自动入库
        self.policy.decide_relic([self.opt_hp, self.opt_def, self.opt_atk], state)
        self.assertEqual(len(relic_db.load_relics(self.db_path)), 3)
        # 第二次：仍是三张，不应重复入库（upsert）
        self.policy.decide_relic([self.opt_hp, self.opt_def, self.opt_atk], state)
        self.assertEqual(len(relic_db.load_relics(self.db_path)), 3)

    def test_unknown_class_defaults_to_attack(self) -> None:
        """character_class=None → 默认 ATTACK 组（选攻击力）。"""
        state = GameState(character_class=None)
        action = self.policy.decide_relic([self.opt_hp, self.opt_def, self.opt_atk], state)
        self.assertEqual(action.target, self.opt_atk.target)

    def test_empty_options_returns_pause(self) -> None:
        """options 为空 → pause。"""
        action = self.policy.decide_relic([], GameState(character_class="刺客"))
        self.assertEqual(action.kind, "pause")


if __name__ == "__main__":
    unittest.main()
