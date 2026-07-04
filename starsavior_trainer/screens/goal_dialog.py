"""目标弹窗(旅程信息) parser — 读 N/45 绝对回合数校准 RoundTracker。

点大厅左上角"目标"二字打开此弹窗, 显示当前旅程的回合数 N/45 (N=当前回合, 45=总回合)。
N 比 RoundTracker 的日期计数更准(日期计数靠 OCR 日期字符串变化, 同旬内多次进大厅漏计、
OCR 丢月份数字跳帧), 用 N 校准 current_round 后, 固定流程(地区移动/交易/评鉴战等)能
稳定按回合数触发。读完点 ✕ 关闭回大厅。
"""
from __future__ import annotations

from collections.abc import Iterable

from starsavior_trainer.models import GoalDialogStatus
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import contains_any_text, parse_first_int


def parse_goal_dialog(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
) -> GoalDialogStatus | None:
    """解析目标弹窗: 锚点"旅程信息"标题 → 读 N/45 回合数 + ✕ 关闭按钮坐标。

    N/45 的 N 用 parse_first_int 提取("21/45" → 21, "/" 自动断开数字 token)。
    返回 None = 不是此画面(标题锚点未命中)。详见 设计方案 §22.9。
    """
    texts = {item.name: item.text for item in region_texts}
    title = texts.get("goal_dialog_anchor_title", "")
    if not contains_any_text(title, ("旅程信息", "旅程", "程信息")):
        return None

    round_text = texts.get("goal_dialog_round_label", "")
    round_num = parse_first_int(round_text)
    return GoalDialogStatus(
        round=round_num,
        close_button=profile.regions.get("goal_dialog_close_button"),
        title=title.strip(),
    )
