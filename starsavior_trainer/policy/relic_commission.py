"""遗物/委托决策 Mixin — 遗物两步确认+组合圣遗物; 委托选可做最高阶。

重构自 policy.py decide_relic/relic_choice/_combo_relic_pick/commission（行 631-717）。
坑 #12: _pending_relic 两步确认防近分卡翻转; 委托按建议综合等级≤角色等级选最高阶。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import Action, CommissionChoice, GameState, RelicChoice, RelicOption
from starsavior_trainer import relic_db
from starsavior_trainer.text_utils import parse_first_int


class RelicCommissionMixin:
    def decide_relic(self, options: Iterable[RelicOption], state: GameState | None = None) -> Action:
        """按模板库 attributes + 角色类型优先级组选卡。

        新规则(2026-07-04): 画面已无 score 数字, 改按效果文本里的属性关键词
        (speed/crit_rate/crit_dmg/attack/hp/defense) + 角色类型(刺客/术师/弓手/
        突击者=ATTACK 组; 辅助/坦克=DEFENSE 组)的属性优先级组选最高优先级那张卡。

        - 未匹配模板库的卡 → 自动入库(relic_db.save_relic), 下次直接查表
        - 同优先级分数 → 按 score 数字（若有）二次排序；都无则取第一个
        - 全部 attributes 为空 → 退化到按 score 数字（兼容旧 score 画面）
        """
        opts = list(options)
        if not opts:
            return Action("pause", None, "no relic options recognized")

        character_class = state.character_class if state else None
        group = relic_db.class_to_priority_group(character_class)
        # 加载模板库 + 自动入库未匹配的卡
        relics = relic_db.load_relics(self.relic_db_path)
        scored: list[tuple[int, int, int, RelicOption]] = []  # (priority_score, score_num, idx, option)
        for idx, option in enumerate(opts):
            # 1. 查模板库; 没有就自动入库（首次见到的奖励）
            entry = relic_db.find_relic(relics, option.name)
            attributes = entry.attributes if entry else option.attributes
            if entry is None and option.effect_text:
                # 自动入库: 名字 + effect_text → 解析 attributes 后写入
                relic_db.save_relic(self.relic_db_path, option.name, option.effect_text, attributes)
            # 2. 按角色优先级组打分
            priority_score = relic_db.score_relic_by_priority(attributes, group)
            score_num = option.score or 0
            scored.append((priority_score, score_num, idx, option))

        # 排序: priority_score 优先; 同 priority 取 score_num 高; 仍同取 idx 小(更靠左)
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        best = scored[0][3]
        best_score = scored[0][0]
        attrs_str = ",".join(best.attributes) if best.attributes else "(none)"
        return Action(
            "click",
            best.target,
            f"relic by {group} priority={best_score}: {best.name}[{attrs_str}]",
        )

    def decide_relic_choice(self, choice: RelicChoice, state: GameState | None = None) -> Action:
        if choice.selected_name and choice.confirm_button is not None:
            self._pending_relic = None
            return Action("click", choice.confirm_button, f"confirm selected relic {choice.selected_name}")

        # Two-step: we clicked a relic last frame — confirm it now instead of re-evaluating.
        if self._pending_relic is not None and choice.confirm_button is not None:
            self._pending_relic = None
            return Action("click", choice.confirm_button, "confirm chosen relic")

        if choice.fixed_name:
            for option in choice.options:
                if option.name == choice.fixed_name:
                    self._pending_relic = option.target
                    return Action("click", option.target, f"choose fixed relic {option.name}")
            return Action("pause", None, f"fixed relic not visible: {choice.fixed_name}")

        # Combo relics (队员全体): pick by build's part/attribute priority, not score.
        combo = self._combo_relic_pick(choice.options, state)
        if combo is not None:
            self._pending_relic = combo.target
            profile = state.build_profile if state else "balanced"
            return Action("click", combo.target, f"combo relic by build {profile}: {combo.name}({combo.attribute})")

        action = self.decide_relic(choice.options, state)
        if action.kind == "click":
            self._pending_relic = action.target
        return action

    def _combo_relic_pick(self, options: Iterable[RelicOption], state: GameState | None) -> RelicOption | None:
        """组合圣遗物(全部 is_team 且带 attribute)→ 按 build 属性优先级选;否则 None."""
        opts = list(options)
        team = [o for o in opts if o.is_team and o.attribute]
        if not team or len(team) < len(opts):
            return None
        profile = state.build_profile if state else "balanced"
        priority = self.config.relic_attribute_priority_by_profile.get(profile, ())
        for attr in priority:
            for option in team:
                if option.attribute == attr:
                    return option
        return team[0]

    # 委托可打上限 = 角色综合等级 + 此 buffer。委托建议等级 ≤ 上限者即可打；
    # 用户规则：rank 22 最高能打 rank 25（buffer=3）。原值 0（≤character_rank）会
    # 漏掉 rank 24 这种"超自己 2 级但可打"的高阶讨伐，与用户预期不符。
    COMMISSION_RANK_BUFFER = 3

    def decide_commission(self, choice: CommissionChoice, state: GameState) -> Action:
        if not choice.options:
            self._pending_commission = None
            if choice.back_button is not None:
                return Action("click", choice.back_button, "no commission listed, exit")
            return Action("pause", None, "no commission options recognized")

        # Red-text (suitable) first; else highest tier ≤ character_rank + COMMISSION_RANK_BUFFER.
        suitable = [option for option in choice.options if option.has_red_text]
        if suitable:
            best = suitable[0]
        elif state.character_rank is not None:
            limit = state.character_rank + self.COMMISSION_RANK_BUFFER
            doable = [
                (rank, option)
                for option in choice.options
                if (rank := parse_first_int(option.rank)) is not None and rank <= limit
            ]
            if doable:
                best = max(doable, key=lambda item: item[0])[1]
            else:
                # 全部委托建议等级都超 limit（高阶讨伐太硬）→ 退一阶：取所有委托里
                # 次高 rank 的（最高那档太硬打不动，降一档）。降一档比无脑选最低更合理：
                # 仍尽量挑战能打的高阶，避免每次都打最低阶的低阶委托。
                ranked = sorted(
                    ((parse_first_int(opt.rank) or 0, opt) for opt in choice.options),
                    key=lambda item: item[0],
                    reverse=True,
                )
                best = ranked[1][1] if len(ranked) >= 2 else choice.options[0]
        else:
            best = choice.options[0]
        if self._pending_commission == best.target and choice.accept_button is not None:
            self._pending_commission = None
            return Action("click", choice.accept_button, f"accept commission: {best.name}")
        self._pending_commission = best.target
        return Action("click", best.target, f"select commission: {best.name}")
