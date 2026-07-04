"""商店/技能决策 Mixin — 商店按效果买; 技能评分(已习得返回 -inf)。

重构自 policy.py decide_shop/shop_item_worth_buying/choose_shop_item/skill_score/decide_skill
（行 719-778）。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Action, GameState, ShopItem, SkillOption


class ShopSkillMixin:
    def shop_item_worth_buying(self, item: ShopItem) -> bool:
        # 按"效果说明"判断(商品名与效果无关): 效果含想要关键词(回复体力 / 潜质点数退还)就买。
        effect = item.effect or ""
        return any(kw in effect for kw in self.config.shop_buy_effect_keywords)

    def choose_shop_item(self, items: Iterable[ShopItem]) -> ShopItem | None:
        for item in items:
            if self.shop_item_worth_buying(item):
                return item
        return None

    def decide_shop(self, items: Iterable[ShopItem]) -> Action:
        chosen = self.choose_shop_item(items)
        if chosen is not None:
            return Action("click", chosen.target, f"buy {chosen.name}: {(chosen.effect or '').strip()}")
        self._dday_trading_done = True  # 逛完交易 → D-DAY 大厅就去评鉴战
        return Action("skip", None, "交易: 没有想买的(回体力/潜质点退还), 退出")

    def skill_score(self, option: SkillOption, state: GameState) -> float:
        if option.target is None:
            return float("-inf")

        text = f"{option.name} {option.effect or ''}".lower()
        if "已习得" in text or "learned" in text:
            return float("-inf")

        keywords = self.config.skill_keywords_by_profile.get(
            state.build_profile,
            self.config.skill_keywords_by_profile["balanced"],
        )
        score = 0.0
        for index, keyword in enumerate(keywords):
            if keyword.lower() in text:
                score += 100 - index * 5

        if option.cost is not None:
            score -= option.cost / 100
        return score

    def decide_skill(self, options: Iterable[SkillOption], state: GameState) -> Action:
        ranked = sorted(
            ((self.skill_score(option, state), option) for option in options),
            key=lambda item: item[0],
            reverse=True,
        )
        if not ranked:
            return Action("pause", None, "no skill options recognized")

        score, best = ranked[0]
        if score == float("-inf"):
            return Action("pause", None, "no learnable skill option recognized")
        return Action(
            "click",
            best.target,
            f"learn skill {best.name}: score={score:.1f}, cost={best.cost}",
        )
