"""§22.11 地区移动多目的地决策测试。

按角色类型选目的地:
- 弗洛拉=术士/游侠/突击者(力量+专注加成)
- 卡莱德=坦克/辅助(体力+保护加成)
- 已选目的地(go_button 亮)→ 点前往
- 角色类型未知/无匹配/第一次阿卡农(不在映射)→ fallback 点 destination_1
"""
import unittest
from dataclasses import replace

from starsavior_trainer.models import (
    Action,
    GameState,
    Observation,
    Rect,
    RegionDestination,
    RegionMoveStatus,
    Screen,
)
from starsavior_trainer.policy.engine import TrainerPolicy
from starsavior_trainer.screens import _decide_region_move


def _status(destinations=(), go_button=None) -> RegionMoveStatus:
    return RegionMoveStatus(destinations=destinations, go_button=go_button, is_region_move=True)


def _obs(payload) -> Observation:
    return Observation(screen=Screen.REGION_MOVE, confidence=1.0, payload=payload)


def _dest(name, rect) -> RegionDestination:
    return RegionDestination(name=name, rect=rect)


class RegionMoveDecisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = TrainerPolicy(
            shop_db_path="config/nonexistent.json", relic_db_path="config/nonexistent.json"
        )
        self.flora = _dest("弗洛拉", Rect(1950, 370, 150, 56))
        self.crayd = _dest("卡莱德", Rect(1950, 520, 150, 56))

    def test_术士_选弗洛拉(self) -> None:
        """术士 → 弗洛拉(术士/游侠/突击者 加成)。"""
        state = GameState(character_class="术士")
        obs = _obs(_status((self.flora, self.crayd)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, self.flora.rect)
        self.assertIn("弗洛拉", action.reason)

    def test_坦克_选卡莱德(self) -> None:
        """坦克 → 卡莱德(坦克/辅助 加成)。"""
        state = GameState(character_class="坦克")
        obs = _obs(_status((self.flora, self.crayd)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, self.crayd.rect)
        self.assertIn("卡莱德", action.reason)

    def test_游侠_选弗洛拉(self) -> None:
        """游侠 → 弗洛拉。"""
        state = GameState(character_class="游侠")
        obs = _obs(_status((self.flora, self.crayd)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, self.flora.rect)

    def test_辅助_选卡莱德(self) -> None:
        """辅助 → 卡莱德。"""
        state = GameState(character_class="辅助")
        obs = _obs(_status((self.flora, self.crayd)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, self.crayd.rect)

    def test_go_button_present_点前往(self) -> None:
        """已选目的地(go_button 亮)→ 点前往, 不再选目的地。"""
        state = GameState(character_class="术士")
        go = Rect(2150, 1262, 160, 58)
        obs = _obs(_status((self.flora, self.crayd), go_button=go))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, go)
        self.assertIn("前往", action.reason)

    def test_character_class_unknown_fallback_destination_1(self) -> None:
        """角色类型未知 → fallback 点 destination_1(第一个目的地)。"""
        state = GameState(character_class=None)
        obs = _obs(_status((self.flora, self.crayd)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, self.flora.rect)
        self.assertIn("fallback", action.reason)

    def test_first_time_阿卡农_fallback_destination_1(self) -> None:
        """第一次地区移动(阿卡农, 不在映射)→ fallback 点 destination_1。"""
        akanon = _dest("阿卡农", Rect(1950, 370, 150, 56))
        state = GameState(character_class="术士")
        obs = _obs(_status((akanon,)))
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.target, akanon.rect)
        self.assertIn("fallback", action.reason)

    def test_no_destinations_pause(self) -> None:
        """无目的地 → pause。"""
        state = GameState(character_class="术士")
        obs = _obs(_status())
        action = _decide_region_move(obs, state, self.policy)
        self.assertEqual(action.kind, "pause")


if __name__ == "__main__":
    unittest.main()
