"""PolicyConfig — 所有决策阈值/坐标集中。

重构自 policy.py §5（行 152-256）。改阈值/坐标只动这里。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from starsavior_trainer.models import Rect


@dataclass(frozen=True)
class PolicyConfig:
    min_screen_confidence: float = 0.75
    max_training_fail_rate: int = 30  # 早期游戏 inspector 失败率阈值（training_score 用动态 §22.4）
    # §22.4 失败率上限随训练值 gain 线性放宽：max_fail = min(99, base + slope×gain)。
    # 理由：训练成功=+gain, 失败=0+降心情(可恢复); gain 越高收益越大于失败代价, 越值得赌。
    # 校准点: gain=20→20%(普通保守), 50→35%, 60→40%, 100→60%, 188→99%(cap)。
    fail_rate_base: int = 10
    fail_rate_slope: float = 0.5
    meditation_coin_threshold: int = 60
    lodging_coin_threshold: int = 30
    # §22.3 休息策略: 耐力(endurance_ratio)<此阈值(0.40=40%)且心情BEST → 冥想室/露宿。
    rest_endurance_threshold: float = 0.40
    min_skill_points: int = 90
    ring_bonus: dict[str, int] = field(
        default_factory=lambda: {
            "rainbow": 40,
            "gold": 25,
            "blue": 10,
            "none": 0,
        }
    )
    shop_whitelist: dict[str, int] = field(
        default_factory=lambda: {
            "advanced_training_book": 120,
            "stamina_potion": 80,
            "mood_candy": 60,
        }
    )
    shop_aliases: dict[str, str] = field(
        default_factory=lambda: {
            "高级训练书": "advanced_training_book",
            "体力药": "stamina_potion",
            "心情糖": "mood_candy",
        }
    )
    # 交易按"效果说明"买(商品名与效果无关): 效果文本含这些关键词就买 —— 回复体力
    # 类 + "潜质点数N退还"(白嫖潜质点,含固定买的手持风扇). 不刷新、不限价。
    shop_buy_effect_keywords: tuple[str, ...] = (
        "回复体力", "体力", "耐力", "潜质点", "退还",
    )
    # Internal stat keys map to the game's training types as:
    #   power=力量  stamina=体力(生命)  guts=韧性(防御)  wisdom=专注(命中)  speed=保护(命抗)
    # Power runs follow "力量/生命为主, 防御为辅": 力量 main, 体力 co-primary, 韧性
    # secondary; 专注/保护 stay at 0 (only worth it via support-card heads, which the
    # ring_bonus already rewards). Over-biasing 韧性/防御 would starve the main stat's
    # proficiency and miss the 1250 cap, so keep it modest.
    training_bias_by_profile: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            "balanced": {},
            "power_focus": {"power": 18, "stamina": 12, "guts": 8},
            "focus_focus": {"wisdom": 18, "speed": 8},
            "durability_focus": {"stamina": 16, "guts": 10},
            "stamina_tank": {"stamina": 20, "guts": 12},
            "protection_focus": {"guts": 16, "stamina": 10},
        }
    )
    # Early-game (前12回合) bias: inside this round window, 力量(power)/生命(stamina)
    # get an extra score weight so the bot front-loads them. Added on top of the
    # profile bias (加权打分) — not a hard override, still compared against the rest.
    early_game_rounds: int = 12
    early_game_stat_weight: dict[str, int] = field(
        default_factory=lambda: {"power": 15, "stamina": 15}
    )
    # Early-game rings matter more (proficiency compounds), so amplify the
    # ring_bonus inside the early window. 1.0 = no amplification.
    early_ring_multiplier: float = 2.5
    # 组合圣遗物(队员全体)按部位属性 + build 优先级选: 在当前3张里选优先级最高的属性;
    # 优先级里都没出现则随便选(取第一张). 属性 key: attack/crit_rate/crit_dmg/hp/defense/hit/resist/speed.
    relic_attribute_priority_by_profile: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "power_focus": ("attack", "crit_rate", "crit_dmg"),
            "stamina_tank": ("hp", "defense", "attack", "crit_rate", "crit_dmg"),
        }
    )
    skill_keywords_by_profile: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "balanced": ("攻击", "集中", "生命", "保护", "洞察"),
            "power_focus": ("攻击", "力量", "attack", "power"),
            "focus_focus": ("集中", "洞察", "专注", "focus", "wisdom"),
            "durability_focus": ("生命", "保护", "体力", "韧性", "stamina", "guts"),
            "stamina_tank": ("生命", "体力", "stamina", "hp"),
            "protection_focus": ("保护", "韧性", "protection", "guts"),
        }
    )
    blessing_attribute_by_profile: dict[str, str] = field(
        default_factory=lambda: {
            "balanced": "power",
            "power_focus": "power",
            "focus_focus": "wisdom",
            "durability_focus": "stamina",
            "stamina_tank": "stamina",
            "protection_focus": "guts",
        }
    )
    max_blessing_value: int = 50
    max_total_blessing_value: int = 100
    start_button: Rect = Rect(2040, 1318, 470, 75)
    skip_button: Rect = Rect(1740, 980, 120, 60)
    move_button: Rect = Rect(1580, 900, 220, 80)
    # "点击以继续" prompt on the 获得奖励 reward popup. The centre card is a dead
    # click zone; this bottom-centre prompt is the only spot that advances.
    reward_continue_button: Rect = Rect(1180, 1250, 230, 64)
    # 技能/潜质界面右上角 ✕ 关闭按钮(前期不学技能,进了就点它退出)。
    skill_select_close_button: Rect = Rect(2125, 300, 90, 66)
    # 屏幕中心: 用于推进"被误判成 relic_choice 的奖励/结果展示"(委托 SUCCESS、评鉴战
    # 奖励纯展示、阿尔克那等点任意处继续的全屏展示), 避免它们 parse 不出选项时 pause 卡死。
    screen_center: Rect = Rect(1180, 660, 200, 120)
    # 误触弹出的游戏「菜单」弹窗右上角 ✕ 关闭按钮。识别到菜单就点它关闭(自愈), 绝不点
    # 菜单中部的 重新观测/观测结束(会重开/结束本局)。坐标取自真帧 OCR 的 X 块中心。
    game_menu_close_button: Rect = Rect(1808, 535, 64, 60)
