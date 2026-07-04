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

from starsavior_trainer.models import Action, ShopScene
from starsavior_trainer import shop_db


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

    def decide(self, scene: ShopScene, policy) -> Action | None:
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
            self.effects[self.pending_index] = new_effect
            self.last_selected_index = self.pending_index
            self.pending_index = None
            self.last_seen_effect = new_effect
            self.settle_wait = 0

        # 1.5) 首次进入交易界面: 游戏默认打开第一个商品的详细界面 (selected_effect 非空)。
        # 此时再点第一个商品会 *关闭* 详细而非打开 (与点击其他行相反)。直接把当前
        # selected_effect 当作第一个商品的 effect 记录, 跳过点击 idx=1, 从 idx=2 开始检视。
        if not self.effects and self.pending_index is None and scene.selected_effect.strip():
            self.effects[1] = scene.selected_effect.strip()
            self.names[1] = items[0].name
            self.prices[1] = items[0].price
            self.last_selected_index = 1
            self.last_seen_effect = scene.selected_effect.strip()

        # 2) Inspect any not-yet-seen row by clicking it (selects it -> detail shows
        #    its effect next frame). 同时记录 name/price（items[idx-1] 上帧已 OCR 出）。
        for idx in range(1, n + 1):
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

        # 4) 按 priority 升序遍历所有商品，找第一个未买的 + class_matches 的买
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

    def reset(self) -> None:
        self.effects = {}
        self.names = {}
        self.prices = {}
        self.pending_index = None
        self.last_selected_index = None
        self.bought_effects = set()
