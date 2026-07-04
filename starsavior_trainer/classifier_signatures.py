"""画面消歧 signature + 视觉密度 helper。

重构自 classifier.py §5（行 514-784）。每个易混淆画面配 _has_X_signature 多信号消歧
(坑台账 A 类 1-11); 旅程起点组(角色选择/祝福装备/旅程起点)靠视觉内容密度区分。
"""
from __future__ import annotations

from PIL import Image

from starsavior_trainer.image_regions import crop_region
from starsavior_trainer.models import Screen
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text
from starsavior_trainer.vision import BlueButtonDetector


def _has_initial_signature(anchors: dict[str, str]) -> bool:
    start_text = anchors.get("start_button", "")
    route_text = " ".join(
        anchors.get(name, "")
        for name in (
            "route_select_anchor_title",
            "route_select_route_title",
        )
    )
    return contains_any_text(start_text, ("开始",)) and contains_any_text(
        route_text,
        ("选择旅程", "星光引导者", "starsavior"),
    )


def _has_post_training_signature(anchors: dict[str, str]) -> bool:
    post_text = " ".join(
        anchors.get(name, "")
        for name in (
            "post_training_result_text",
            "post_training_title",
            "post_training_success_text",
        )
    )
    return contains_any_text(post_text, ("训练成功", "力量训练", "体力训练", "提升"))


def _has_event_choice_signature(anchors: dict[str, str]) -> bool:
    option_text = " ".join(
        anchors.get(f"event_choice_option_{index}", "")
        for index in range(1, 5)
    )
    return bool(option_text.strip()) and contains_any_text(
        anchors.get("event_choice_title", ""),
        ("旅程事件", "事件"),
    )


def _has_dialogue_signature(anchors: dict[str, str]) -> bool:
    event_label = anchors.get("dialogue_journey_event_label", "") + anchors.get("dialogue_journey_title", "")
    bottom_text = anchors.get("dialogue_journey_text_area", "")
    if bottom_text.strip() and contains_any_text(event_label, ("事件",)):
        return True

    dialogue_text = " ".join(
        anchors.get(name, "")
        for name in (
            "dialogue_intro_skip_button",
            "dialogue_journey_event_label",
            "dialogue_journey_text_area",
        )
    )
    return contains_any_text(
        dialogue_text,
        ("获得", "星之祝福", "跳过", "skip"),
    )


def _has_commission_select_signature(anchors: dict[str, str]) -> bool:
    title = anchors.get("commission_select_anchor_title", "")
    names = " ".join(anchors.get(f"commission_select_option_{i}_name", "") for i in range(1, 6))
    accept = anchors.get("commission_select_accept_button", "")
    # 训练大厅也有「委托」按钮, 要求唯一「接受」按钮消歧(坑 #8)。
    # OCR 偶尔把 受 读成 文, 匹配前导「接」即可(坑 #26)。
    has_commission_text = contains_any_text(names, ("委托", "commission")) or contains_any_text(
        title, ("委托", "commission")
    )
    has_accept = contains_any_text(accept, ("接受", "接", "accept"))
    return has_commission_text and has_accept


def _has_shop_signature(anchors: dict[str, str]) -> bool:
    # D-DAY 交易坐在评鉴战背景上, battle_title 读「参加评鉴战」会让 fallback 误判 BATTLE(坑 #4)。
    # 唯一常驻标记是右上「刷新」按钮(1级 D-DAY 大厅没有); 「购买」只在选中商品后出现。
    refresh_text = anchors.get("shop_refresh_button", "")
    buy_text = anchors.get("shop_buy_button", "")
    if not (contains_any_text(refresh_text, ("刷新",)) or contains_any_text(buy_text, ("购买", "购"))):
        return False
    detail = anchors.get("shop_detail_effect", "")
    names = " ".join(anchors.get(f"shop_item_{i}_name", "") for i in range(1, 6))
    prices = " ".join(anchors.get(f"shop_item_{i}_price", "") for i in range(1, 6))
    return bool(detail.strip() or names.strip() or prices.strip())


def _has_battle_signature(anchors: dict[str, str]) -> bool:
    # 基础评鉴战 entry confirm: 居中对话框, classify_by_ocr 会 UNKNOWN, 蓝键 fallback 误判
    # event_fast_forward(坑 #6)。「跳过战斗」+「评鉴战/委托」标题唯一识别。
    skip = anchors.get("battle_skip_battle_button", "")
    title = anchors.get("battle_confirm_title", "")
    return contains_any_text(skip, ("跳过战斗", "跳过")) and contains_any_text(
        title, ("评鉴战", "鉴战", "委托")
    )


def _has_training_hub_shop_signature(anchors: dict[str, str]) -> bool:
    shop_text = " ".join(
        anchors.get(name, "")
        for name in (
            "training_hub_action_shop",
            "training_hub_shop_alert",
            "training_hub_nav_potential",
        )
    )
    return contains_any_text(shop_text, ("交易", "商品", "到货")) and contains_any_text(
        shop_text,
        ("潜质", "商品", "到货"),
    )


def _has_rest_submenu_signature(anchors: dict[str, str]) -> bool:
    rest_text = " ".join(
        anchors.get(name, "")
        for name in (
            "rest_submenu_option_1",
            "rest_submenu_option_2",
            "rest_submenu_option_3",
        )
    )
    return contains_any_text(rest_text, ("露宿", "住处", "冥想室"))


def _has_reward_signature(anchors: dict[str, str]) -> bool:
    # 获得奖励 popup(坑 #9): 中心标题区分于角色选择, 避免角色滚动死循环。
    title = anchors.get("reward_title", "")
    return contains_any_text(title, ("获得奖励", "获得", "奖励"))


def _has_region_move_signature(anchors: dict[str, str]) -> bool:
    # 列车月台(坑 #5): 地区移动 + 列车月台 双锚点, 避免 relic_choice 误判。
    anchor = anchors.get("region_move_anchor_title", "")
    station = anchors.get("region_move_station_title", "")
    return contains_any_text(anchor, ("地区移动", "区移动")) and contains_any_text(
        station, ("列车月台", "车月台", "月台")
    )


def _has_game_menu_signature(anchors: dict[str, str]) -> bool:
    # 误触菜单弹窗(坑 #10): 菜单标题 + 观测行双信号, 绝不点中部 重新观测/观测结束。
    title = anchors.get("game_menu_anchor_title", "")
    observe = anchors.get("game_menu_observe_marker", "")
    return contains_any_text(title, ("菜单", "菜車", "茶单")) and contains_any_text(
        observe, ("观测", "重新观测", "观测结束", "观测信息")
    )


def _has_training_select_signature(anchors: dict[str, str]) -> bool:
    # 统计多少卡槽读到训练名(坑 #3): 真训练有 5 张, D-DAY 商店只卖 1 张「保护训练的秘笈」。
    # 要求 ≥2 张匹配, 避免商店被误判 TRAINING_SELECT 导致检视器死循环。
    names = (
        "力量训练",
        "体力训练",
        "韧性训练",
        "集中训练",
        "保护训练",
    )
    hits = sum(
        1
        for attr in ("power", "stamina", "guts", "wisdom", "speed")
        if contains_any_text(anchors.get(f"training_select_card_{attr}", ""), names)
    )
    return hits >= 2


# ---------------------------------------------------------------------------
# Visual density helpers — journey-origin group disambiguation (坑 #1/#11)
# ---------------------------------------------------------------------------


def _region_content_density(image: Image.Image) -> float:
    """Estimate visual content density via pixel variance (0.0 uniform → ~1.0 dense)."""
    try:
        gray = image.convert("L")
        pixel_data = gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata()
        pixels = list(pixel_data)
        total = len(pixels)
        if total < 2:
            return 0.0
        mean = sum(pixels) / total
        variance = sum((p - mean) ** 2 for p in pixels) / total
        return min(variance / 4000.0, 1.0)
    except Exception:
        return 0.0


def _has_blessing_choice_visual_signature(image: Image.Image, profile: RegionProfile) -> bool:
    confirm = profile.regions.get("blessing_choice_confirm_button")
    archive = profile.regions.get("blessing_choice_anchor_archive")
    if confirm is None or archive is None:
        return False
    try:
        confirm_signal = BlueButtonDetector().detect(crop_region(image, confirm))
        archive_density = _region_content_density(crop_region(image, archive))
        return confirm_signal.name == "active_blue" and confirm_signal.coverage >= 0.40 and archive_density >= 0.40
    except Exception:
        return False


def classify_journey_origin_by_visual(image: Image.Image, profile: RegionProfile) -> Screen | None:
    """Separate character select from blessing setup when both OCR as journey origin."""
    character_score, blessing_score = journey_origin_visual_scores(image, profile)
    if character_score < 0.40 and blessing_score >= 0.18:
        return Screen.BLESSING_SETUP
    if blessing_score >= 0.45 and blessing_score > character_score + 0.18:
        return Screen.BLESSING_SETUP
    if character_score >= 0.75 and character_score >= blessing_score:
        return Screen.CHARACTER_SELECT
    return None


def journey_origin_visual_scores(image: Image.Image, profile: RegionProfile) -> tuple[float, float]:
    character_score = _average_region_density(image, profile, ("character_option_1", "character_option_2", "character_option_3"))
    blessing_score = _average_region_density(image, profile, ("blessing_slot_1", "blessing_slot_2"))
    return character_score, blessing_score


def _average_region_density(image: Image.Image, profile: RegionProfile, names: tuple[str, ...]) -> float:
    densities: list[float] = []
    for name in names:
        rect = profile.regions.get(name)
        if rect is not None:
            densities.append(_region_content_density(crop_region(image, rect)))
    if not densities:
        return 0.0
    return sum(densities) / len(densities)
