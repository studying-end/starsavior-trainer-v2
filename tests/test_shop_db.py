"""商品模板库 (shop_db) 单元测试。

覆盖：
- class_matches: 空分类=所有角色；多分类任一命中；无角色类型时空分类才匹配
- should_buy: class_matches + priority ≤ 5 + 未买过 三条都要满足
- filter_buyable: 按 priority 升序排序
- find_shop / save_shop: 查找 + 自动入库（首次写入 + 已存在 upsert 保留 priority）
- ShopInspector 集成: 多件购买流程 + 角色类型不匹配时退出
"""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

from starsavior_trainer import shop_db
from starsavior_trainer.inspectors.shop_inspector import ShopInspector
from starsavior_trainer.models import Rect, ShopItem, ShopScene
from starsavior_trainer.policy.engine import TrainerPolicy


class ClassMatchesTest(unittest.TestCase):
    def test_empty_classes_match_all(self) -> None:
        """空分类 = 适合所有角色（任何角色类型都匹配）。"""
        self.assertTrue(shop_db.class_matches((), "刺客"))
        self.assertTrue(shop_db.class_matches((), "坦克"))
        self.assertTrue(shop_db.class_matches((), None))

    def test_single_class_match(self) -> None:
        """单分类匹配。"""
        self.assertTrue(shop_db.class_matches(("刺客",), "刺客"))
        self.assertFalse(shop_db.class_matches(("刺客",), "坦克"))

    def test_multi_class_any_match(self) -> None:
        """多分类任一命中即匹配（用户: 一件商品可既是游侠+刺客+坦克）。"""
        self.assertTrue(shop_db.class_matches(("游侠", "刺客", "坦克"), "刺客"))
        self.assertTrue(shop_db.class_matches(("游侠", "刺客", "坦克"), "游侠"))
        self.assertTrue(shop_db.class_matches(("游侠", "刺客", "坦克"), "坦克"))
        self.assertFalse(shop_db.class_matches(("游侠", "刺客", "坦克"), "术师"))

    def test_no_character_class(self) -> None:
        """无角色类型时: 空分类匹配, 具体分类不匹配。"""
        self.assertTrue(shop_db.class_matches((), None))
        self.assertFalse(shop_db.class_matches(("刺客",), None))
        self.assertFalse(shop_db.class_matches(("刺客",), ""))


class ShouldBuyTest(unittest.TestCase):
    def test_class_match_and_priority_ok(self) -> None:
        """分类匹配 + priority ≤ 5 → 可买。"""
        item = shop_db.ShopItemEntry(name="力量药剂", effect="力量+3", classes=("刺客",), priority=0)
        self.assertTrue(shop_db.should_buy(item, "刺客"))

    def test_class_mismatch(self) -> None:
        """分类不匹配 → 不买（即使 priority=0）。"""
        item = shop_db.ShopItemEntry(name="坦克装备", effect="防御+3", classes=("坦克",), priority=0)
        self.assertFalse(shop_db.should_buy(item, "游侠"))

    def test_priority_too_low(self) -> None:
        """priority=99（自动入库默认）→ 不买（用户未手填）。"""
        item = shop_db.ShopItemEntry(name="未知商品", effect="", classes=(), priority=99)
        self.assertFalse(shop_db.should_buy(item, "刺客"))

    def test_priority_max_boundary(self) -> None:
        """priority=5（最大可买值）→ 买；priority=6 → 不买。"""
        item5 = shop_db.ShopItemEntry(name="低优先", effect="效果", classes=(), priority=5)
        self.assertTrue(shop_db.should_buy(item5, "刺客"))
        item6 = shop_db.ShopItemEntry(name="太低优先", effect="效果", classes=(), priority=6)
        self.assertFalse(shop_db.should_buy(item6, "刺客"))

    def test_already_bought(self) -> None:
        """已买过的（effect 在 bought_effects）→ 不买。"""
        item = shop_db.ShopItemEntry(name="药剂", effect="力量+3", classes=(), priority=0)
        self.assertTrue(shop_db.should_buy(item, "刺客"))
        self.assertFalse(shop_db.should_buy(item, "刺客", bought_effects={"力量+3"}))


class FilterBuyableTest(unittest.TestCase):
    def test_sort_by_priority_ascending(self) -> None:
        """按 priority 升序排序（小=优先）。"""
        items = [
            shop_db.ShopItemEntry(name="C", priority=5, classes=()),
            shop_db.ShopItemEntry(name="A", priority=0, classes=()),
            shop_db.ShopItemEntry(name="B", priority=2, classes=()),
        ]
        result = shop_db.filter_buyable(items, "刺客")
        self.assertEqual([it.name for it in result], ["A", "B", "C"])

    def test_filter_class_mismatch(self) -> None:
        """分类不匹配的被过滤掉。"""
        items = [
            shop_db.ShopItemEntry(name="刺客装备", priority=0, classes=("刺客",)),
            shop_db.ShopItemEntry(name="坦克装备", priority=0, classes=("坦克",)),
        ]
        result = shop_db.filter_buyable(items, "刺客")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "刺客装备")


class FindSaveShopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "shop_items.json"

    def test_save_then_find(self) -> None:
        """首次入库 → find_shop 能查到。"""
        shop_db.save_shop(self.db_path, "力量药剂", "力量+3", 100, ("刺客", "术师"), 0)
        items = shop_db.load_shop(self.db_path)
        self.assertEqual(len(items), 1)
        entry = shop_db.find_shop(items, "力量药剂")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.classes, ("刺客", "术师"))
        self.assertEqual(entry.priority, 0)

    def test_upsert_preserves_priority(self) -> None:
        """同名商品再次入库 → 更新 effect/price/classes，但保留 priority（避免覆盖用户手填值）。"""
        shop_db.save_shop(self.db_path, "力量药剂", "力量+3", 100, ("刺客",), 0)
        # 用户手填 priority=0 → 再次自动入库时不应覆盖
        shop_db.save_shop(self.db_path, "力量药剂", "力量+3 (更新)", 120, ("刺客", "术师"))
        items = shop_db.load_shop(self.db_path)
        self.assertEqual(len(items), 1)  # 仍是 1 条
        self.assertEqual(items[0].priority, 0)  # priority 保留
        self.assertEqual(items[0].effect, "力量+3 (更新)")  # effect 已更新
        self.assertEqual(items[0].price, 120)

    def test_default_priority_99_when_auto_inserted(self) -> None:
        """自动入库（未指定 priority）→ 默认 99（用户手填前不买）。"""
        shop_db.save_shop(self.db_path, "新商品", "效果", 50)
        items = shop_db.load_shop(self.db_path)
        self.assertEqual(items[0].priority, 99)

    def test_load_empty(self) -> None:
        """文件不存在 → 空 list。"""
        self.assertEqual(shop_db.load_shop(self.tmpdir + "/nonexistent.json"), [])

    def test_load_corrupted(self) -> None:
        """文件损坏 → 空 list。"""
        self.db_path.write_text("not json {{{", encoding="utf-8")
        self.assertEqual(shop_db.load_shop(self.db_path), [])

    def test_save_load_always_buy(self) -> None:
        """§22.10 always_buy=True 写入 → 读取回来为 True。"""
        shop_db.save_shop(self.db_path, "综合营养剂", "解除负面", 20, always_buy=True)
        items = shop_db.load_shop(self.db_path)
        entry = shop_db.find_shop(items, "综合营养剂")
        self.assertIsNotNone(entry)
        self.assertTrue(entry.always_buy)

    def test_always_buy_default_false(self) -> None:
        """未指定 always_buy → 默认 False（普通商品不强制买）。"""
        shop_db.save_shop(self.db_path, "普通商品", "效果", 10)
        items = shop_db.load_shop(self.db_path)
        self.assertFalse(items[0].always_buy)

    def test_upsert_preserves_always_buy(self) -> None:
        """§22.10 同 priority: 自动入库(不传 always_buy)时保留用户手填的 always_buy 不被覆盖。"""
        shop_db.save_shop(self.db_path, "综合营养剂", "解除负面", 20, always_buy=True)
        # 自动入库再次写入(不传 always_buy=None) → 应保留 True
        shop_db.save_shop(self.db_path, "综合营养剂", "解除负面(更新)", 25)
        items = shop_db.load_shop(self.db_path)
        self.assertTrue(items[0].always_buy)


class ShopInspectorIntegrationTest(unittest.TestCase):
    """ShopInspector 集成测试: 检视 → 自动入库 → 多件购买 → 不匹配时退出。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "shop_items.json"
        # 预置 3 个商品到模板库（模拟用户已手填 priority）
        shop_db.save_shop(self.db_path, "力量药剂", "力量+3", 100, ("刺客", "游侠"), 0)
        shop_db.save_shop(self.db_path, "体力药剂", "体力+3", 80, ("坦克", "辅助"), 1)
        shop_db.save_shop(self.db_path, "通用面包", "HP+10", 50, (), 2)
        self.policy = TrainerPolicy(shop_db_path=self.db_path, relic_db_path=self.tmpdir + "/r.json")
        # 模拟 3 个商品画面（与模板库 3 条对齐）
        self.scene = ShopScene(
            items=(
                ShopItem(name="力量药剂", price=100, target=Rect(100, 100, 200, 50), effect=""),
                ShopItem(name="体力药剂", price=80, target=Rect(100, 200, 200, 50), effect=""),
                ShopItem(name="通用面包", price=50, target=Rect(100, 300, 200, 50), effect=""),
            ),
            selected_effect="",
            buy_button=Rect(1000, 800, 100, 50),
            back_button=Rect(50, 50, 50, 50),
        )

    def _drive_inspection(self, inspector: ShopInspector, scene: ShopScene, effects: dict[int, str]) -> None:
        """模拟检视器按 2→3→1 顺序逐个点开 3 行（每行点击 → 下一帧 selected_effect 变为该行 effect）。
        检视完后停止，不做后续决策（让测试自己驱动后续 decide）。

        新顺序(§22.8): 2→3→1。#1 放最后避开"点已选中态关闭详情"坑。
        注意: 若 effects[X]==上一条已记 effect, inspector 会等 3 帧才强制记录 → 循环到记录成功。
        """
        # iter 1: 点 #2 (scene.selected_effect="")
        inspector.decide(scene, self.policy)  # pending_index=2
        # iter 2+: #2 详情显示 → 记 effects[2], 点 #3。若与初始相同等 3 帧。
        scene2 = replace(scene, selected_effect=effects[2])
        for _ in range(5):
            if 2 in inspector.effects:
                break
            inspector.decide(scene2, self.policy)
        # iter 3+: #3 详情显示 → 记 effects[3], 点 #1
        scene3 = replace(scene, selected_effect=effects[3])
        for _ in range(5):
            if 3 in inspector.effects:
                break
            inspector.decide(scene3, self.policy)
        # 模拟 #1 已读（最后一点，#1 详情显示后 inspector 会记 effects[1] 并进入决策）
        inspector.effects[1] = effects[1]
        inspector.pending_index = None
        inspector.last_selected_index = 1

    def test_inspector_inspects_all_rows_first(self) -> None:
        """未检视完前只点 inspect，不买。新顺序首帧点 #2(§22.8)。"""
        inspector = ShopInspector()
        # iter 1: 点 #2 (新顺序 2→3→1)
        action = inspector.decide(self.scene, self.policy)
        self.assertIn("inspect shop item #2", action.reason)

    def test_attacker_buys_attacker_item_first(self) -> None:
        """刺客角色 → 买刺客分类的商品（力量药剂 priority=0）而非坦克（体力药剂 priority=1）。"""
        self.policy.character_class = "刺客"  # 直接设在 policy 上（测试 hack）
        inspector = ShopInspector()
        # 模拟 3 帧检视（新顺序 2→3→1, _drive_inspection 最后点 #1）
        self._drive_inspection(inspector, self.scene, {1: "力量+3", 2: "体力+3", 3: "HP+10"})
        # 第 4 帧检视完 → 选 priority 最高的（力量药剂 priority=0）。
        # 最后检视的是 #1(已选中) → 直接走"购买"分支(两步确认优化)。
        action = inspector.decide(self.scene, self.policy)
        self.assertIn("shop item #1", action.reason)
        self.assertIn("priority=0", action.reason)

    def test_tank_buys_tank_item_first(self) -> None:
        """坦克角色 → 体力药剂（坦克分类, priority=1）优先于通用面包（priority=2）。"""
        self.policy.character_class = "坦克"
        inspector = ShopInspector()
        self._drive_inspection(inspector, self.scene, {1: "力量+3", 2: "体力+3", 3: "HP+10"})
        # 坦克不匹配力量药剂（刺客/游侠），但匹配体力药剂（坦克/辅助）
        action = inspector.decide(self.scene, self.policy)
        self.assertIn("select shop item #2", action.reason)  # 体力药剂
        self.assertIn("priority=1", action.reason)

    def test_auto_insert_unknown_item(self) -> None:
        """未入库的商品 → 自动入库（priority=99 默认，不买）。"""
        # 改 scene：第一个商品名换成未入库的"未知药水"
        scene = replace(self.scene, items=(
            ShopItem(name="未知药水", price=999, target=Rect(100, 100, 200, 50), effect=""),
            ShopItem(name="力量药剂", price=100, target=Rect(100, 200, 200, 50), effect=""),
            ShopItem(name="体力药剂", price=80, target=Rect(100, 300, 200, 50), effect=""),
        ))
        self.policy.character_class = "刺客"
        inspector = ShopInspector()
        self._drive_inspection(inspector, scene, {1: "未知效果", 2: "力量+3", 3: "体力+3"})
        inspector.decide(scene, self.policy)
        # 未知药水 应该被自动入库到模板库
        items = shop_db.load_shop(self.db_path)
        names = [it.name for it in items]
        self.assertIn("未知药水", names)
        # 且 priority=99（不买）
        entry = shop_db.find_shop(items, "未知药水")
        self.assertEqual(entry.priority, 99)

    def test_exit_when_no_class_match(self) -> None:
        """用户场景: 界面商品分类只剩下坦克/辅助，但角色是游侠 → 退出。"""
        # 改 scene: 3 件商品都是坦克/辅助分类
        scene = ShopScene(
            items=(
                ShopItem(name="体力药剂A", price=80, target=Rect(100, 100, 200, 50), effect=""),
                ShopItem(name="体力药剂B", price=90, target=Rect(100, 200, 200, 50), effect=""),
                ShopItem(name="体力药剂C", price=100, target=Rect(100, 300, 200, 50), effect=""),
            ),
            selected_effect="",
            buy_button=Rect(1000, 800, 100, 50),
            back_button=Rect(50, 50, 50, 50),
        )
        # 预置模板库：3 件都是坦克/辅助分类
        shop_db.save_shop(self.db_path, "体力药剂A", "体力+3", 80, ("坦克", "辅助"), 0)
        shop_db.save_shop(self.db_path, "体力药剂B", "体力+3", 90, ("坦克", "辅助"), 0)
        shop_db.save_shop(self.db_path, "体力药剂C", "体力+3", 100, ("坦克", "辅助"), 0)
        self.policy.character_class = "游侠"
        inspector = ShopInspector()
        self._drive_inspection(inspector, scene, {1: "体力+3", 2: "体力+3", 3: "体力+3"})
        # 游侠不匹配任何坦克/辅助商品 → 退出
        action = inspector.decide(scene, self.policy)
        self.assertEqual(action.kind, "click")
        self.assertEqual(action.target, scene.back_button)
        self.assertIn("无匹配商品", action.reason)

    def test_buy_multiple_items(self) -> None:
        """买完第一件后继续买第二件（取消限购1件限制）。新顺序 2 件商品 = [2,1](§22.8)。"""
        # 预置 2 件刺客商品
        shop_db.save_shop(self.db_path, "刺客武器", "攻击+5", 200, ("刺客",), 0)
        shop_db.save_shop(self.db_path, "刺客护甲", "防御+2", 150, ("刺客",), 1)
        scene = ShopScene(
            items=(
                ShopItem(name="刺客武器", price=200, target=Rect(100, 100, 200, 50), effect=""),
                ShopItem(name="刺客护甲", price=150, target=Rect(100, 200, 200, 50), effect=""),
            ),
            selected_effect="",
            buy_button=Rect(1000, 800, 100, 50),
            back_button=Rect(50, 50, 50, 50),
        )
        self.policy.character_class = "刺客"
        inspector = ShopInspector()
        # 检视顺序 [2,1]: 首帧点 #2
        self.assertEqual(inspector.decide(scene, self.policy).reason, "inspect shop item #2")
        # 帧 2: #2 详情显示 → 记 effects[2]=防御+2, 点 #1
        inspector.decide(replace(scene, selected_effect="防御+2"), self.policy)
        # 帧 3: #1 详情显示 → 记 effects[1]=攻击+5, 检视完进入决策。
        # #1 是最后检视的(已选中, last_selected_index=1) → 选 priority 最高的 #1 直接购买。
        action = inspector.decide(replace(scene, selected_effect="攻击+5"), self.policy)
        self.assertIn("购买 shop item #1", action.reason)
        # 买完 #1 后继续买 #2（不退出）
        action = inspector.decide(scene, self.policy)
        # 应该选 #2 或继续流程，而不是退出
        self.assertNotEqual(action.target, scene.back_button)

    def test_default_open_first_item_skips_click(self) -> None:
        """进入交易界面游戏默认打开某商品 (selected_effect 非空)。

        §22.8 新逻辑: 不再假设默认打开的是 #1, 也不把首帧 selected_effect 当作 #1 的 effect
        (真机验证该假设不成立 → effect 错配 → 入库脏数据)。改为固定按 2→3→1 检视顺序,
        首帧无论 selected_effect 是否为空都直接点 #2, 不预记任何 effect。
        #1 放最后点(此时它非选中态, 点它正常打开详情)。
        """
        # 预置 #1 已入库（力量药剂 priority=0），#2/#3 未入库
        shop_db.save_shop(self.db_path, "力量药剂", "力量+3", 100, ("刺客",), 0)
        # 首帧: selected_effect 非空（游戏默认打开某商品，可能是任意行）
        scene_first = replace(self.scene, selected_effect="力量+3")
        inspector = ShopInspector()
        # 第一帧 decide: 直接点 #2（不预记 effects[1]，避开错配）
        action = inspector.decide(scene_first, self.policy)
        self.assertIn("inspect shop item #2", action.reason)
        # 关键: 不再把首帧 selected_effect 当作 #1 的 effect
        self.assertNotIn(1, inspector.effects)
        self.assertEqual(inspector.pending_index, 2)

    def test_wait_for_detail_refresh_before_recording(self) -> None:
        """live_loop 0.5s 太快: 点击 #2 后下一帧 OCR 可能仍读旧 effect(详情面板未刷新)。
        必须等 selected_effect 变化(或 settle_wait>=3)才记录 effects[2]。

        §22.8: 新顺序首帧点 #2(不预记 effects[1]), prev_effect 初始为 scene.selected_effect。
        """
        # 预置: #1 已入库 effect=体力4增加
        shop_db.save_shop(self.db_path, "奶油义大利面", "体力4增加", 20, (), 0)
        # 帧 1: 进入交易界面, 游戏默认打开某商品, selected_effect=体力4增加
        scene1 = replace(self.scene, selected_effect="体力4增加")
        inspector = ShopInspector()
        action1 = inspector.decide(scene1, self.policy)
        # 帧 1 应该: 点 #2, 不预记 effects[1]
        self.assertNotIn(1, inspector.effects)
        self.assertEqual(inspector.pending_index, 2)
        # 帧 2: 点击 #2 后下一帧, 详情面板未刷新, selected_effect 仍是 "体力4增加"
        scene2 = replace(self.scene, selected_effect="体力4增加")  # 未刷新
        action2 = inspector.decide(scene2, self.policy)
        # 应该等待(skip), 不记录 effects[2]
        self.assertEqual(action2.kind, "skip")
        self.assertIn("wait for shop item #2", action2.reason)
        self.assertNotIn(2, inspector.effects)  # 还没记录
        self.assertEqual(inspector.pending_index, 2)  # 仍等待
        self.assertEqual(inspector.settle_wait, 1)
        # 帧 3: 详情面板已刷新, selected_effect 变成 #2 的 effect
        scene3 = replace(self.scene, selected_effect="攻击+3")
        action3 = inspector.decide(scene3, self.policy)
        # 应该记录 effects[2]=攻击+3, 然后点 #3
        self.assertEqual(inspector.effects[2], "攻击+3")
        self.assertEqual(inspector.pending_index, 3)
        self.assertEqual(inspector.settle_wait, 0)  # 重置

    def test_force_record_after_3_waits_when_effects_genuinely_same(self) -> None:
        """真有商品 effect 与首帧 selected_effect 完全相同: 等 3 帧后强制记录(避免死循环)。

        §22.8: 新顺序首帧点 #2, prev_effect=首帧 selected_effect。若 #2 effect 与之相同,
        inspector 会等 3 帧后强制记录 effects[2]。
        """
        shop_db.save_shop(self.db_path, "药剂A", "体力4增加", 20, (), 0)
        shop_db.save_shop(self.db_path, "药剂B", "体力4增加", 30, (), 0)
        # 帧 1: 默认打开某商品, selected_effect="体力4增加", 点 #2
        scene1 = replace(self.scene, selected_effect="体力4增加")
        inspector = ShopInspector()
        inspector.decide(scene1, self.policy)  # 点 #2, 不预记 effects[1]
        # 帧 2-4: #2 的 effect 也是 "体力4增加" (真的相同), 等 3 帧后强制记录
        scene_same = replace(self.scene, selected_effect="体力4增加")
        inspector.decide(scene_same, self.policy)  # 等 1 (settle_wait=1)
        self.assertNotIn(2, inspector.effects)
        inspector.decide(scene_same, self.policy)  # 等 2 (settle_wait=2)
        self.assertNotIn(2, inspector.effects)
        inspector.decide(scene_same, self.policy)  # 等 3 (settle_wait=3)
        self.assertNotIn(2, inspector.effects)
        # 帧 5: settle_wait >= 3 → 强制记录
        action = inspector.decide(scene_same, self.policy)
        self.assertIn(2, inspector.effects)
        self.assertEqual(inspector.effects[2], "体力4增加")


class AlwaysBuyInspectorTest(unittest.TestCase):
    """§22.10 always_buy 商品(综合营养剂)按钮蓝色检测 + 最高优先购买。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "shop_items.json"
        # 综合营养剂 always_buy=True; 普通面包 priority=0 (会买的 priority 商品)
        shop_db.save_shop(self.db_path, "综合营养剂", "解除负面", 20, always_buy=True)
        shop_db.save_shop(self.db_path, "普通面包", "HP+10", 50, (), 0)
        self.policy = TrainerPolicy(shop_db_path=self.db_path, relic_db_path=self.tmpdir + "/r.json")
        self.scene = ShopScene(
            items=(
                ShopItem(name="综合营养剂", price=20, target=Rect(100, 100, 200, 50), effect=""),
                ShopItem(name="普通面包", price=50, target=Rect(100, 200, 200, 50), effect=""),
            ),
            selected_effect="",
            buy_button=Rect(1000, 800, 100, 50),
            back_button=Rect(50, 50, 50, 50),
        )

    def _blue_image(self) -> Image.Image:
        """构造一张 is_blue_region 判 True 的纯蓝色图(覆盖 buy_button 区域)。"""
        img = Image.new("RGB", (2560, 1440), (0, 0, 0))
        # buy_button=(1000,800,100,50) 涂满 muted-blue (h≈210, s≈0.25, v≈0.9) → BlueButtonDetector active
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([1000, 800, 1100, 850], fill=(120, 150, 210))
        return img

    def _gray_image(self) -> Image.Image:
        """构造一张 is_blue_region 判 False 的灰色图(按钮 inactive)。"""
        return Image.new("RGB", (2560, 1440), (80, 80, 80))

    def _drive_inspection_2rows(self, inspector, image):
        """模拟 2→1 顺序检视 2 行, 返回最后一帧(检视完 #1 后的决策)的 action。

        帧1: 点 #2 (inspect_order=[2,1])
        帧2: #2 effect 显示 → 记 effects[2] + 检测 #2 按钮(非 always_buy 跳过), 点 #1
        帧3: #1 effect 显示 → 记 effects[1] + 检测 #1 按钮(always_buy 综合营养剂!) + 检视完进入决策
        """
        inspector.decide(self.scene, self.policy, image=image)  # 点 #2
        inspector.decide(replace(self.scene, selected_effect="HP+10"), self.policy, image=image)  # 记#2, 点#1
        return inspector.decide(replace(self.scene, selected_effect="解除负面"), self.policy, image=image)  # 记#1+决策

    def test_always_buy_blue_button_recorded_as_buyable(self) -> None:
        """综合营养剂选中时按钮蓝色 → 记入 buyable_always。"""
        inspector = ShopInspector()
        self._drive_inspection_2rows(inspector, self._blue_image())
        # #1 是综合营养剂(always_buy), 按钮蓝 → 应在 buyable_always
        self.assertIn(1, inspector.buyable_always)

    def test_always_buy_gray_button_not_buyable(self) -> None:
        """综合营养剂选中时按钮灰色(无负面状态)→ 不在 buyable_always, 不买。"""
        inspector = ShopInspector()
        self._drive_inspection_2rows(inspector, self._gray_image())
        self.assertNotIn(1, inspector.buyable_always)

    def test_always_buy_takes_priority_over_normal(self) -> None:
        """综合营养剂能买(蓝)时, 优先于 priority=0 的普通面包。"""
        inspector = ShopInspector()
        action = self._drive_inspection_2rows(inspector, self._blue_image())
        # 检视完 → 决策: 应优先选综合营养剂(#1) 而非普通面包(#2, priority=0)
        self.assertIn("#1", action.reason)
        self.assertIn("always_buy", action.reason)

    def test_no_always_buy_when_gray_falls_to_priority(self) -> None:
        """综合营养剂不能买(灰)时, 回落到 priority 体系买普通面包。"""
        inspector = ShopInspector()
        action = self._drive_inspection_2rows(inspector, self._gray_image())
        # 应选普通面包(#2, priority=0), 不是综合营养剂
        self.assertIn("#2", action.reason)
        self.assertNotIn("always_buy", action.reason)


if __name__ == "__main__":
    unittest.main()
