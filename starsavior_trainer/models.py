from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Screen(str, Enum):
    INITIAL = "initial"
    CHARACTER_SELECT = "character_select"
    BLESSING_SETUP = "blessing_setup"
    BLESSING_CHOICE = "blessing_choice"
    JOURNEY_START = "journey_start"
    CONFIRM_DIALOG = "confirm_dialog"
    EVENT_FAST_FORWARD_SETTING = "event_fast_forward_setting"
    DIALOGUE = "dialogue"
    TRAINING_HUB = "training_hub"
    TRAINING_SELECT = "training_select"
    REST_SUBMENU = "rest_submenu"
    EVENT_CHOICE = "event_choice"
    RELIC_CHOICE = "relic_choice"
    COMMISSION_SELECT = "commission_select"
    SHOP = "shop"
    POST_TRAINING = "post_training"
    BATTLE = "battle"
    SKILL_SELECT = "skill_select"
    REGION_MOVE = "region_move"
    # "获得奖励" reward-obtained popup in a fixed relic is granted, no choice). The
    # centre card is a dead click zone; only the "点击以继续" prompt advances it.
    REWARD = "reward"
    # The in-game 菜单 popup (指南/选项/编制信息/观测信息/重新观测/储存后前往大厅 +
    # an ✕ close). Reached by an accidental mis-click on the top-right menu button.
    # Dangerous to leave: its centre holds 重新观测/观测结束, which would restart or
    # end the run if clicked — so we must recognise it and click ✕ to close, never
    # the generic "click centre to advance" fallback.
    GAME_MENU = "game_menu"
    # "旅程信息"目标弹窗: 点大厅左上角"目标"二字打开, 显示当前回合 N/45 (绝对回合数)。
    # 用 N 校准 RoundTracker 的日期计数(日期计数不准: 同旬漏计/OCR 丢月份跳帧)。
    # priority=2 早检查(弹窗背景是大厅, 晚检查会被 TRAINING_HUB priority=8 抢走)。
    GOAL_DIALOG = "goal_dialog"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass(frozen=True)
class Action:
    kind: str
    target: Rect | None
    reason: str
    confidence: float = 1.0
    scroll_clicks: int = 0
    # Number of times to repeat a click in one execution. >1 turns a single
    # click into a rapid burst — used for "tap to continue / skip" advance
    # screens (reward popup, dialogue, post-training) so they're blown through
    # quickly instead of one click per loop iteration.
    repeat: int = 1


@dataclass(frozen=True)
class TrainingChoice:
    name: str
    stat_gain: int
    ring: str
    # 失败率(百分数)。None = 该卡未被选中,屏幕没显示它的失败率 → 未知(不是0%)。
    # 只有当前选中的卡会显示失败率;策略层把 None 当作"不可冒险"(见 training_score)。
    fail_rate: int | None
    target: Rect
    # Whether this card is currently highlighted/selected (only the selected card
    # shows its 失败率 on screen). The screen-level confirm (训练) button is carried
    # on each choice so the policy can confirm once the desired card is selected.
    selected: bool = False
    confirm_button: Rect | None = None
    # Top-left back arrow, used to leave TRAINING_SELECT back to the hub when every
    # training's fail rate is too high (so the hub-level decision can choose rest).
    back_button: Rect | None = None
    # §22.1: 耐力(训练资源)条填充比例(0.0-1.0)，SELECT 顶部 HUD 读（绿=当前耐力，
    # 灰=训练消耗预览，CV 绿前缀排除灰）。画面级，每卡同值。0.0=未读到。
    endurance_ratio: float = 0.0
    # §22.6: 该训练卡是否闪光（金黄，大量训练值）；CV 检测卡金黄背景/边框（detect_flash_card）。
    is_flash: bool = False


@dataclass(frozen=True)
class RestSubmenu:
    coins: int
    has_meditation_room: bool
    meditation_room: Rect
    rough_sleep: Rect
    # 住处 (30-coin lodging) option and the bottom-right 休息 confirm button.
    # Rest is a two-step flow (select option, then confirm) like training/commission.
    lodging: Rect | None = None
    confirm_button: Rect | None = None


@dataclass(frozen=True)
class EventOption:
    text: str
    target: Rect
    # The event's title (OCR'd from the screen), carried so the policy can look
    # the event up in config/events.json for its recommended option.
    event_title: str = ""


@dataclass(frozen=True)
class RelicOption:
    name: str
    score: int | None
    target: Rect
    # 部位映射出的战斗属性(attack/crit_rate/crit_dmg/hp/defense/hit/resist/speed),
    # 与是否"队员全体"(组合圣遗物)。组合圣遗物按属性+build优先级选,普通按 score。
    attribute: str | None = None
    is_team: bool = False
    # 效果文本(从 relic_choice_card_N_description 区域 OCR 读, 如「首次战斗开始时,
    # 自身的最大生命力增加4%」)。新规则(2026-07-04): decide_relic 按效果文本里的
    # 属性关键词 + 角色类型优先级组选卡, 不再用 score 数字(画面已无 score)。
    effect_text: str = ""
    # 从 effect_text 解析出的属性标签元组(speed/crit_rate/crit_dmg/attack/hp/defense)。
    # parse_relic_choice 调 relic_db.extract_attributes 填; decide_relic 按角色优先级组
    # 取 attributes 命中最高优先级者。空元组=无属性/未知(默认最差)。
    attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelicChoice:
    options: list[RelicOption]
    confirm_button: Rect | None = None
    fixed_name: str | None = None
    selected_name: str | None = None


@dataclass(frozen=True)
class CommissionOption:
    name: str
    rank: str
    has_red_text: bool
    target: Rect


@dataclass(frozen=True)
class CommissionChoice:
    options: list[CommissionOption]
    accept_button: Rect | None = None
    # Top-left back arrow, used to leave the screen when no suitable commission
    # is available (rule: only accept red-text/suitable commissions, else exit).
    back_button: Rect | None = None
    # 当前选中委托的「建议综合等级」(详情区数字, 如 RANK 17)。列表项只有阶名(低/中/
    # 高阶委托), 建议等级只在选中后于中央详情区显示 → 检视器逐个点开读它来选阶。
    selected_suggested_rank: int | None = None
    # 角色综合等级(委托界面左上 "RANK 21")。选"建议等级≤它的最高阶"委托用; 直接从本
    # 界面读, 不依赖先经过训练大厅。
    character_rank: int | None = None


@dataclass(frozen=True)
class ShopItem:
    name: str
    price: int
    target: Rect
    # 效果说明文本(商品名与效果无关,买/不买看效果). 需逐个点开商品读取。
    effect: str = ""


@dataclass(frozen=True)
class ShopScene:
    """Journey Trading (交易) screen state.

    The right-side list (``items``) gives each row's click target; effects only
    show in the centre detail once an item is selected, so ``selected_effect`` is
    the *currently-selected* item's effect text for this frame. The shop inspector
    clicks each row in turn, attributing each frame's ``selected_effect`` to the
    row it clicked last, then buys by effect (回体力 / 潜质点退还) via ``buy_button``
    or leaves via ``back_button``.
    """

    items: tuple[ShopItem, ...] = ()
    selected_effect: str = ""
    buy_button: Rect | None = None
    back_button: Rect | None = None


@dataclass(frozen=True)
class CharacterOption:
    name: str
    rank: str | None
    stars: int | None
    specialty: str | None
    selected: bool
    target: Rect
    # 形态/系列标记(每行职业图标下方文字): ""=普通, "ANOTHER"=第二形态, "COSMIC"=系列。
    # 游戏更新后同名角色有多形态, 用它 + 名字一起锁定目标形态。
    variant: str = ""


@dataclass(frozen=True)
class CharacterSelect:
    options: list[CharacterOption]
    confirm_button: Rect
    selected_name: str | None = None
    can_scroll: bool = True


@dataclass(frozen=True)
class BlessingSlot:
    index: int
    occupied: bool
    target: Rect


@dataclass(frozen=True)
class BlessingSetup:
    slots: list[BlessingSlot]
    auto_equip_button: Rect
    confirm_button: Rect
    can_confirm: bool


@dataclass(frozen=True)
class BlessingOption:
    name: str
    attribute: str
    value: int | None
    target: Rect
    sub_blessing_count: int = 0
    sub_blessing_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlessingChoice:
    options: list[BlessingOption]
    confirm_button: Rect | None = None
    selected_name: str | None = None
    detail_sub_blessing_count: int = 0


@dataclass(frozen=True)
class JourneyStart:
    start_button: Rect
    auto_journey_button: Rect | None = None
    arcana_slots: list[Rect] | None = None


@dataclass(frozen=True)
class ConfirmDialog:
    title: str
    message: str
    confirm_button: Rect
    cancel_button: Rect | None = None


@dataclass(frozen=True)
class GoalDialogStatus:
    """目标弹窗(旅程信息)解析结果。N/45 的 N = 绝对回合数, 校准 RoundTracker。"""
    round: int | None
    close_button: Rect | None = None
    title: str = ""


@dataclass(frozen=True)
class RegionDestination:
    """地区移动的一个目的地(如弗洛拉/卡莱德/阿卡农)。name 来自 OCR, rect 是点击行。"""
    name: str
    rect: Rect


@dataclass(frozen=True)
class RegionMoveStatus:
    """地区移动(列车月台)解析结果。§22.11 多目的地按角色类型选。

    destinations 是右侧目的地列表(每行 name+rect); go_button 是"前往"按钮(选中目的地后出现)。
    is_region_move 锚点是否命中——供回合数兜底用(第15/30回合 UNKNOWN 时尝试 region_move)。
    """
    destinations: tuple[RegionDestination, ...] = ()
    go_button: Rect | None = None
    is_region_move: bool = False


@dataclass(frozen=True)
class EventFastForwardSetting:
    no_fast_forward_option: Rect
    watched_only_option: Rect
    all_events_option: Rect
    confirm_button: Rect
    selected_mode: str | None = None


@dataclass(frozen=True)
class DialogueScene:
    skip_button: Rect
    variant: str = "default"
    text_area: Rect | None = None


@dataclass(frozen=True)
class BattleScene:
    skip_button: Rect
    confirm_button: Rect | None = None
    confirm_active: bool = False


@dataclass(frozen=True)
class SkillOption:
    name: str
    effect: str | None = None
    cost: int | None = None
    target: Rect | None = None


@dataclass(frozen=True)
class SkillLearnOption:
    """潜质学习选项(§22.13)。含模板库优先级 + 原价(算折扣) + 当前状态 + 等级 + 习得按钮。"""
    name: str
    price: int | None = None  # 当前价格(含折扣)
    original_price: int | None = None  # 原价(按 kind 推断, 算折扣用)
    priority: int = 99  # 模板库优先级(battle/breeding, 由 run_type 决定用哪个)
    status: str = ""  # "未习得"/"升级"
    level: int = 0  # 当前等级(0=未习得, 1-4=可升级, 满级5不出现)
    target: Rect | None = None  # 习得/升级按钮 rect
    target: Rect | None = None  # 习得按钮 rect


@dataclass(frozen=True)
class TrainingHubStatus:
    turn_label: str | None = None
    coins: int | None = None
    rank_label: str | None = None
    potential_points: int | None = None
    training_button: Rect | None = None
    commission_button: Rect | None = None
    rest_button: Rect | None = None
    skill_button: Rect | None = None
    shop_button: Rect | None = None
    # 左上角"目标"按钮(点开旅程信息弹窗读 N/45 校准回合数, §22.9)。None = region 未配置。
    goal_button: Rect | None = None
    # D-DAY 评鉴战日大厅: 这俩按钮取代平时的 训练/委托/休息(评鉴战上、交易下)。
    rating_battle_button: Rect | None = None
    trading_button: Rect | None = None
    has_commission_alert: bool = False
    has_shop_alert: bool = False
    can_learn_skill: bool = False
    # 耐力（训练资源 endurance，非体力 HP）条填充比例 0.0-1.0；CV 估自顶部 HUD 绿色条
    # （vision.estimate_endurance_ratio）。0.0 = 未读到。详见 设计方案 §22.1。
    endurance_ratio: float = 0.0
    # 心情等级（BEST/GOOD/NORMAL）OCR 自顶部 HUD mood_label；None = 未读到。详见 §22.3。
    mood: str | None = None
    # 训练按钮是否闪光（金黄，闪光训练=大量训练值）；CV 检测按钮 R-B 偏金。详见 §22.6。
    has_flash_training: bool = False


@dataclass(frozen=True)
class GameState:
    current_rank: str = "C"
    coins: int = 0
    safe_mode: bool = True
    desired_character: str | None = None
    # 目标角色的形态(""=普通, "ANOTHER"/"COSMIC"等)。同名多形态时用它锁定正确那个。
    desired_variant: str = ""
    build_profile: str = "balanced"
    desired_blessing_attribute: str | None = None
    # Current journey round/turn (1-based). None when unknown/not yet read from the
    # hub. Drives the early-game training bias (see PolicyConfig.early_game_rounds).
    current_round: int | None = None
    # 角色综合等级(数字, 从训练大厅 "RANK 21" 读)。委托选阶用: 选建议综合等级≤它的最高阶
    # 委托(能做的最高阶)。None=未知时退回选最低阶。
    character_rank: int | None = None
    # 角色类型(characters.json 6 类名: 刺客/术师/游侠/突击者/辅助/坦克)。
    # 启动时按 desired_character 查 config/characters.json 填入; 决定奖励选择时的
    # 属性优先级组(attack/defense)。None=未知时按 ATTACK 组默认。
    character_class: str | None = None


@dataclass(frozen=True)
class Observation:
    screen: Screen
    confidence: float
    payload: object | None = None
    source: str | None = None
