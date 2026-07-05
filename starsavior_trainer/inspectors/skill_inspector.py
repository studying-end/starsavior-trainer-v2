"""潜质学习检视器 — 滑动扫库 → 贪心决策 → 习得循环（§22.13）。

跨帧状态机(仿 ShopInspector)，3 阶段循环：
- 阶段 A 扫库：滑到底识别全部潜质(name+价格+状态)，累积 self.skills。连续2次名字集合不变=到底。
- 阶段 B 决策：贪心选下一个要学的(优先级升序+折扣降序)，钱不够跳过，全部买不起→退出。
- 阶段 C 习得：点习得按钮 → 下帧回阶段 B(点数减少重新决策)。

战斗模型(本次): 用 battle_priority。种马模型(第二步): breeding_priority。
自己 OCR 识别潜质行(复用 collect_skills 状态标签锚点逻辑), 不走 parse_skill_select
(它不支持状态/价格/滑动)。

坑: 点习得后下帧刷新(点数减少), 不弹确认框(假设); 弹了则需额外处理。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

from starsavior_trainer import skill_db
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import Action, Rect, SkillLearnOption

logger = get_logger("skill_inspector")

# 滑动参数（同 collect_skills）
_SCROLL_PIXELS = 340
_SCROLL_SETTLE = 0.8
_SCROLL_MAX = 20
_KIND_SUFFIXES = ("感知", "技巧", "天赋")


@dataclass(frozen=True)
class _SeenSkill:
    """扫库累积的一个潜质（最后看到的价格/状态为准）。"""

    name: str
    price: int | None
    status: str  # "未习得"/"已习得"
    target_y: int  # 最后看到时的 y 中心(点习得用, 但 y 会随滚动变 → 决策时重读)


@dataclass
class SkillInspector:
    """滑动扫库识别全部潜质 → 贪心按优先级+折扣买 → 买到买不起退出。"""

    # 扫库累积: name → _SeenSkill
    skills: dict[str, _SeenSkill] = field(default_factory=dict)
    scanned: bool = False  # 扫库完成(到底)
    learned: set[str] = field(default_factory=set)  # 已学习的潜质名
    learn_count: int = 0  # 本次学习次数(防死循环)
    # 扫库状态
    _scroll_count: int = 0
    _prev_names: frozenset[str] = field(default_factory=frozenset)
    _same_count: int = 0
    # 从底往上学状态(扫库完成后)
    _scroll_up_count: int = 0  # 往上滑次数
    _top_reached: int = 0  # 连续名字不变计数(到顶判定)
    # 阶段: "scan"/"decide"（习得后回 decide）
    _phase: str = "scan"

    def decide(
        self,
        potential_points: int | None,
        policy,
        read_rows: Callable[[], list[tuple[str, int | None, str, Rect | None, int]]] | None = None,
        scroll: Callable[[], None] | None = None,
        close_button: Rect | None = None,
    ) -> Action:
        """跨帧决策。read_rows/scroll 由 live_loop 注入(截图+OCR+滑动)。

        read_rows() → [(name, price, status, target_rect, y), ...] 当前帧可见潜质。
        scroll() → 上滑一次(看下方潜质)。
        potential_points → 当前剩余潜质点数(None=未读到, 当作 0 不学)。
        """
        points = potential_points or 0
        max_learn = policy.config.skill_max_learn

        # 阶段 A: 扫库(滑到底)
        if self._phase == "scan" and not self.scanned:
            return self._do_scan(read_rows, scroll, close_button)

        # 阶段 B: 决策(贪心选下一个)。扫库到底后从底部往上学的策略:
        # 高优先级潜质大多在底部, 所以扫完直接从当前帧(底部)开始学, 学不到再往上滑。
        if self.learn_count >= max_learn:
            return self._exit(close_button, f"达学习上限 {max_learn} 次, 退出", policy)

        target = self._choose_next(policy, points, read_rows)
        if target is not None:
            # 阶段 C: 习得/升级。习得后画面位置不变(只刷新点数/状态), 下帧重新决策选下一个。
            # learned 按 (name, level) 防死循环(感知升级 name 同 level 不同)。
            self.learned.add((target.name, target.level))
            self.learn_count += 1
            lvl_s = f" Lv.{target.level+1}" if target.status == "升级" else ""
            logger.info(f"[潜质学习] 学 {target.name}{lvl_s} (priority={target.priority}, 价格={target.price}, 点数={points})")
            return Action("click", target.target, f"潜质学习 {target.name}{lvl_s} (p={target.priority}, 价={target.price})")

        # 当前帧无可学 → 往上滑看上方潜质(从底往上学)。到顶(连续2次非空名字不变)仍无可学 → 退出。
        if self._scroll_up_count < _SCROLL_MAX:
            from starsavior_trainer.skill_reader import drag_scroll_down
            drag_scroll_down()
            self._scroll_up_count += 1
            # 到顶判定: 读当前帧名字(空帧不参与, 防过渡帧误判), 与上次比
            rows = read_rows() if read_rows else []
            cur_names = frozenset(row[0] for row in rows if row[0])
            if cur_names and cur_names == self._prev_names:
                self._top_reached += 1
                if self._top_reached >= 2:
                    return self._exit(close_button, f"滑到顶仍无可学(点数 {points}), 退出", policy)
            elif cur_names:
                self._top_reached = 0
            if cur_names:
                self._prev_names = cur_names
            return Action("skip", None, f"当前帧无可学, 往上滑看上方({self._scroll_up_count})")
        return self._exit(close_button, f"滑到顶仍无可学(点数 {points}), 退出", policy)

    def _do_scan(self, read_rows, scroll, close_button) -> Action:
        """扫库: 读当前帧 → 累积 → 往下滑。到底(scanned=True)后转决策(从底往上学)。"""
        if read_rows is None:
            self.scanned = True
            self._phase = "decide"
            return Action("skip", None, "无 read_rows 回调, 进决策")
        rows = read_rows()
        cur_names = set()
        for row in rows:
            name = row[0]
            if not name:
                continue
            cur_names.add(name)
            # 累积(后看到的价格/状态覆盖; 价格取最大值纠正 OCR 少读)。row: (name,price,status,target,y,level?)
            price = row[1]; status = row[2]; y = row[4] if len(row) > 4 else 0
            old = self.skills.get(name)
            if old is None:
                self.skills[name] = _SeenSkill(name, price, status, y)
            else:
                new_price = price
                if old.price is not None and price is not None:
                    new_price = max(old.price, price)
                elif old.price is not None:
                    new_price = old.price
                self.skills[name] = _SeenSkill(name, new_price, status or old.status, y)

        # 到底判定: 连续 2 次名字集合不变。空帧(读到 0 个, 如画面过渡/非技能窗口)
        # 不参与判定——否则在大厅/过渡帧连续空会误判到底。
        cur_frozen = frozenset(cur_names)
        if cur_frozen and cur_frozen == self._prev_names:
            self._same_count += 1
            if self._same_count >= 2:
                self.scanned = True
                self._phase = "decide"
                self._prev_names = frozenset()  # 重置: 从底往上学时干净开始到顶判定
                logger.info(f"[潜质学习] 扫库完成, 共 {len(self.skills)} 个潜质")
                return Action("skip", None, f"扫库完成 {len(self.skills)} 个, 进决策")
        elif cur_frozen:
            self._same_count = 0
        self._prev_names = cur_frozen if cur_frozen else self._prev_names

        # 继续滑动
        if self._scroll_count >= _SCROLL_MAX:
            self.scanned = True
            self._phase = "decide"
            return Action("skip", None, f"扫库达上限 {_SCROLL_MAX} 次, 进决策")
        if scroll is None:
            self.scanned = True
            self._phase = "decide"
            return Action("skip", None, "无 scroll 回调, 进决策")
        self._scroll_count += 1
        scroll()
        return Action("skip", None, f"扫库滑动 {self._scroll_count}(累积 {len(self.skills)} 个)")

    def _choose_next(self, policy, points: int, read_rows) -> SkillLearnOption | None:
        """贪心选下一个要学的。读当前帧潜质行(拿最新 target rect), 匹配模板库 priority。"""
        if read_rows is None:
            return None
        rows = read_rows()
        # 当前帧潜质 → (name,level) 到 (price, status, target)。升级状态用 (name,level) 区分
        # (同一潜质不同等级是不同学习目标, 防死循环按 (name,level))。
        cur: dict[tuple[str, int], tuple[int | None, str, Rect | None]] = {}
        for row in rows:
            # row: (name, price, status, target, y) 或 (name, price, status, target, y, level)
            name = row[0]; price = row[1]; status = row[2]; target = row[3]
            level = row[5] if len(row) > 5 else 0
            if name:
                cur[(name, level)] = (price, status, target)
        # 加载模板库
        entries = skill_db.load_skills(policy.skill_db_path)
        run_type = policy.config.run_type
        # 构造 SkillLearnOption 列表(只含当前帧可见 + 库里有 priority 的)
        options: list[SkillLearnOption] = []
        for (name, level), (price, status, target) in cur.items():
            # 已尝试学过的跳过(按 (name,level) 防死循环: 升级时 name 同但 level 不同)
            if (name, level) in self.learned:
                continue
            entry = skill_db.find_skill(entries, name)
            if entry is None:
                continue  # 不在库里的不入决策(避免学未知潜质)
            priority = entry.battle_priority if run_type == "battle" else entry.breeding_priority
            from starsavior_trainer.policy.skill_learn import original_price_for_kind
            original = original_price_for_kind(entry.kind)
            options.append(SkillLearnOption(
                name=name, price=price, original_price=original,
                priority=priority, status=status, level=level, target=target,
            ))
        return policy.next_skill_to_learn(options, points)

    def _exit(self, close_button, reason: str, policy=None) -> Action:
        """退出: 点 X 关闭回大厅。设 policy._skill_done 防回大厅后重复进(死循环)。"""
        if policy is not None:
            policy._skill_done = True
        self.reset()
        if close_button is not None:
            return Action("click", close_button, f"潜质学习: {reason}")
        return Action("pause", None, f"潜质学习: {reason}(无关闭按钮)")

    def reset(self) -> None:
        self.skills = {}
        self.scanned = False
        self.learned = set()
        self.learn_count = 0
        self._scroll_count = 0
        self._prev_names = frozenset()
        self._same_count = 0
        self._scroll_up_count = 0
        self._top_reached = 0
        self._phase = "scan"
