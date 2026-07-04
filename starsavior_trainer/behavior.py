"""行为日志 — 用清晰中文叙述 bot 每一步的所作所为，便于实跑出问题时精确定位。

设计目标：任何人读 logs/behavior.log 就能看懂"bot 看到了什么、进了哪个界面、
因为什么选了什么、又因为什么退出了"，无需翻代码。

覆盖节点（由各模块调用 narrate）：
- 识别：看到什么画面、置信度、关键 OCR（回合/等级/选项文本等）
- 画面切换：从 A 进入 B / 退出 A 因为何
- 决策：选了什么动作(click/scroll/pause)、点哪、理由
- 检视器：逐张读了什么（训练卡增益/人头数、商品效果、委托阶等）
- 执行：点了哪个坐标、dry 还是真点
"""
from __future__ import annotations

from starsavior_trainer.logging_setup import get_logger

_log = get_logger("behavior")


def narrate(msg: str) -> None:
    """记一条行为日志（建议中文、一句话说清"做了什么+为什么"）。"""
    _log.info(msg)
