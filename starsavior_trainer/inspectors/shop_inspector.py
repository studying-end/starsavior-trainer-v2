"""商店检视器 — 逐个点开商品读效果, 按商品模板库 priority + 角色类型买多件。

重构自旧 shop_inspector.py（限购1件 + 关键词匹配）。新规则（2026-07-04）：
- 商品模板库 config/shop_items.json 存 name/effect/price/classes/priority
- classes 按角色类型分(可多选)；空=适合所有角色
- priority 0-5（数字越小越优先，用户手填）；99=自动入库默认值（不买）
- 按角色类型筛选 class_matches + priority ≤ MAX_BUY_PRIORITY(5) 的商品
- 按 priority 升序逐个买（可买多件，每次仍需两步确认 select→buy）
- 全部不符合或已买完 → 退出（用户场景：界面只剩坦克/辅助，但角色是游侠 → 停止）

坑: 悬停不刷新详情面板, 必须 click。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from starsavior_trainer.models import Action, ShopScene
from starsavior_trainer import shop_db
from starsavior_trainer.vision import is_blue_region


@dataclass
class ShopInspector:
    """Buy Journey Trading (交易) items by template-db priority + character class.

    CLICK each row in turn; the next frame's centre detail (``scene.selected_effect``)
    is that row's effect, attributed to the row we clicked last. Once every row's
    effect is known we look up each item in shop_db (auto-insert unseen ones) and
    buy by priority order: filter class_matches(character_class) + priority ≤ 5,
    sort ascending, buy first not-yet-bought (two-step select→购买 each buy).

    Rows tracked by 1-based index (stable within a visit). ``bought_effects`` guards
    against re-buying if an item lingers on screen after purchase.
    """

    effects: dict[int, str] = field(default_factory=dict)  # 1-based row index -> effect text
    names: dict[int, str] = field(default_factory=dict)  # 1-based row index -> name text
    prices: dict[int, int] = field(default_factory=dict)  # 1-based row index -> price
    pending_index: int | None = None  # row clicked to inspect, awaiting its detail next frame
    last_selected_index: int | None = None  # row currently selected on screen
    bought_effects: set[str] = field(default_factory=set)
    # 详情面板刷新等待: 点击 #X 后下一帧 OCR 可能仍读旧 effect(live_loop 0.5s 太快)。
    # 记录上次见到的 effect, 仅当 selected_effect 变化才记录 effects[X]; 最多等 3 帧避免死锁。
    last_seen_effect: str = ""
    settle_wait: int = 0
    # 检视顺序(1-based idx 列表)。首次进入交易界面时按 2→3→...→N→1 排定(§22.8)：
    # 游戏默认打开 #1, 点已选中的 #1 会*关闭*详情而非打开 → #1 放最后点(此时它非选中态)。
    # 这样每个 effect 都明确归属于点击的那行, 消除首商品 effect 错配导致入库脏数据。
    inspect_order: list[int] = field(default_factory=list)
    # §22.10 always_buy 商品(如综合营养剂)选中时购买按钮蓝色(能买)的行 idx。
    # 检视时顺带检测按钮颜色, 蓝色 → 记入此集合, 决策时最高优先购买(无视 priority)。
    buyable_always: set[int] = field(default_factory=set)

    def decide(self, scene: ShopScene, policy, image: Image.Image | None = None) -> Action | None:
        items = list(scene.items)
        if not items:
            return None  # let the policy pause — nothing to act on
        n = len(items)

        # 1) Record the effect of the row we clicked last turn: clicking it selected
        #    it, so the centre detail now shows ITS effect.
        if self.pending_index is not None and scene.selected_effect.strip():
            new_effect = scene.selected_effect.strip()
            # 详情面板可能未刷新(仍显示上一个商品的 effect) → 等待变化
            # 最多等 3 帧: 真相同 effect 的商品也会被强制记录(settle_wait >= 3)
            if new_effect == self.last_seen_effect and self.settle_wait < 3:
                self.settle_wait += 1
                return Action("skip", None, f"wait for shop item #{self.pending_index} detail to refresh")
            just_recorded_idx = self.pending_index
            self.effects[just_recorded_idx] = new_effect
            self.last_selected_index = just_recorded_idx
            self.pending_index = None
            self.last_seen_effect = new_effect
            self.settle_wait = 0
            # §22.10 always_buy 商品(如综合营养剂)检视时顺带检测购买按钮颜色:
            # 蓝=能买(有负面旅程状态等触发条件满足)→ 记入 buyable_always, 决策时最高优先买。
            # 此时 just_recorded_idx 行正被选中, shop_buy_button 颜色反映它能否购买。
            self._check_always_buy_button(just_recorded_idx, scene, image, policy)

        # 1.5) 首次进入交易界面: 排定检视顺序 2→3→...→N→1(§22.8)。
        # 游戏默认打开 #1 → 点已选中的 #1 会*关闭*详情而非打开(与点其它行相反)。
        # 故 #1 放最后点(此时它已被其它行的点击取消选中, 再点正常打开详情)。
        # 旧实现的"直接把当前 selected_effect 当作 #1 的 effect"假设游戏默认选中 #1,
        # 但真机验证该假设不成立(默认选中的可能是任意行)→ effect 错配 → 入库脏数据。
        # N=1 时退化为 [1](只有一件商品, 点它会关闭再点开, settle_wait 兜底处理)。
        if not self.inspect_order:
            if n >= 2:
                self.inspect_order = list(range(2, n + 1)) + [1]
            else:
                self.inspect_order = [1]
            # 把首帧 selected_effect 作为 last_seen_effect 基线, 让 settle_wait 机制能
            # 判断"点击 #2 后 selected_effect 是否变化"(否则 last_seen_effect="" 时第一个
            # 非空 effect 永远 != "" → 直接记录, 跳过刷新等待 → 可能录入未刷新的旧值)。
            self.last_seen_effect = scene.selected_effect.strip()

        # 2) 按 inspect_order 检视未读的行(点它选中 → 下帧面板显示其 effect)。
        #    name/price 用 items[idx-1] 本帧 OCR 结果记录。
        for idx in self.inspect_order:
            if idx not in self.effects:
                self.names[idx] = items[idx - 1].name
                self.prices[idx] = items[idx - 1].price
                self.pending_index = idx
                return Action("click", items[idx - 1].target, f"inspect shop item #{idx}")

        # 3) 全部检视完。查模板库（自动入库未见的），按 priority 升序选可买的。
        character_class = getattr(policy, "state", None)
        character_class = getattr(character_class, "character_class", None) if character_class else None
        # 也可从 policy 直接读（兼容 state 没传的情况）
        if not character_class:
            character_class = getattr(policy, "character_class", None)

        # 加载模板库
        shop_db_path = getattr(policy, "shop_db_path", None)
        if not shop_db_path:
            from pathlib import Path
            shop_db_path = Path(__file__).resolve().parent.parent / "config" / "shop_items.json"
        all_entries = shop_db.load_shop(shop_db_path)

        # 自动入库未见过的新商品（用 name + effect + price 入库，priority 默认 99）
        for idx in range(1, n + 1):
            name = self.names.get(idx, "")
            effect = self.effects.get(idx, "")
            price = self.prices.get(idx, 0)
            if name and not shop_db.find_shop(all_entries, name):
                shop_db.save_shop(shop_db_path, name, effect, price)
                # 重新加载（save_shop 已 upsert）
                all_entries = shop_db.load_shop(shop_db_path)

        # 4) §22.10 always_buy 商品(如综合营养剂, 能买=按钮蓝色时)最高优先购买, 无视 priority。
        #    遍历 buyable_always(检视时检测为蓝色的行), 找第一个未买的, 两步确认 select→buy。
        for idx in self.inspect_order:
            if idx not in self.buyable_always:
                continue
            entry = shop_db.find_shop(all_entries, self.names.get(idx, ""))
            if entry is None or (entry.effect or entry.name) in self.bought_effects:
                continue
            # 已选这行 → 点 buy_button
            if self.last_selected_index == idx and scene.buy_button is not None:
                self.bought_effects.add(entry.effect or entry.name)
                self.last_selected_index = None
                return Action("click", scene.buy_button, f"购买 shop item #{idx}: {entry.name} (always_buy, 蓝色能买)")
            # 没选 → 先选这行(下帧再点 buy)
            self.last_selected_index = idx
            self.pending_index = None
            return Action("click", items[idx - 1].target, f"select shop item #{idx}: {entry.name} (always_buy, 蓝色能买)")

        # 5) 按 priority 升序遍历所有商品，找第一个未买的 + class_matches 的买
        #    每件商品需要两次点击：先 select 行，下帧点 buy_button
        for entry in shop_db.filter_buyable(all_entries, character_class, self.bought_effects):
            # 找到这个 entry 对应的行 idx（按 effect 匹配，因为 name OCR 可能不稳）
            # 优先按 effect 匹配；effect 空时按 name 匹配
            target_idx = None
            for idx in range(1, n + 1):
                row_effect = self.effects.get(idx, "")
                row_name = self.names.get(idx, "")
                if entry.effect and row_effect == entry.effect:
                    target_idx = idx
                    break
                if not entry.effect and row_name and row_name == entry.name:
                    target_idx = idx
                    break
            if target_idx is None:
                continue

            # 已选这行 → 点 buy_button
            if self.last_selected_index == target_idx and scene.buy_button is not None:
                self.bought_effects.add(entry.effect or entry.name)
                # 不清 effects/names/prices — 继续买下一件
                self.last_selected_index = None
                return Action("click", scene.buy_button, f"购买 shop item #{target_idx}: {entry.name} (priority={entry.priority})")
            # 没选 → 先选这行
            self.last_selected_index = target_idx
            self.pending_index = None
            return Action("click", items[target_idx - 1].target, f"select shop item #{target_idx}: {entry.name} (priority={entry.priority})")

        # 5) 没有可买的 → 退出
        policy._dday_trading_done = True
        self.reset()
        if scene.back_button is not None:
            reason = "交易: 没有匹配角色类型/priority 的商品, 退出"
            if character_class:
                reason = f"交易: 角色类型={character_class}, 无匹配商品, 退出"
            return Action("click", scene.back_button, reason)
        return Action("skip", None, "交易: 没有想买的, 无返回按钮")

    def _check_always_buy_button(self, idx: int, scene: ShopScene, image, policy) -> None:
        """§22.10 检视时顺带检测: idx 行若是 always_buy 商品, 查购买按钮颜色。
        蓝(能买, 如综合营养剂有负面状态时)→ 记入 buyable_always; 灰(不能买)→ 不记。
        此时 idx 行正被选中, scene.buy_button 颜色反映它能否购买。"""
        if image is None or scene.buy_button is None:
            return
        name = self.names.get(idx, "")
        if not name:
            return
        shop_db_path = getattr(policy, "shop_db_path", None)
        if not shop_db_path:
            from pathlib import Path
            shop_db_path = Path(__file__).resolve().parent.parent / "config" / "shop_items.json"
        entry = shop_db.find_shop(shop_db.load_shop(shop_db_path), name)
        if entry is None or not entry.always_buy:
            return
        if is_blue_region(scene.buy_button, image):
            self.buyable_always.add(idx)

    def reset(self) -> None:
        self.effects = {}
        self.names = {}
        self.prices = {}
        self.pending_index = None
        self.last_selected_index = None
        self.bought_effects = set()
        self.inspect_order = []
        self.buyable_always = set()
