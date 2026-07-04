"""Track the current journey round by watching the hub date advance.

重构自 round_tracker.py。大厅无回合数, 只有日期(如"3月下旬"); 靠日期变化计数。
规范化成 "<月>月<上中下>", 读丢月份数字(如"月下旬")→None 不前进(坑 #29 避免月份碰撞)。
"""
from __future__ import annotations

import re

_DATE_RE = re.compile(r"(\d{1,2})\s*月\s*([上中下])\s*旬")


def _canonical_date(date: str | None) -> str | None:
    if not date:
        return None
    match = _DATE_RE.search(date)
    if match is None:
        return None
    return f"{int(match.group(1))}月{match.group(2)}"


class RoundTracker:
    """current_round is None until the first parseable date, then 1, and +1 on
    every date change. reset() clears it for a new journey."""

    def __init__(self) -> None:
        self._last_date: str | None = None
        self._round = 0

    def reset(self) -> None:
        self._last_date = None
        self._round = 0

    @property
    def current_round(self) -> int | None:
        return self._round or None

    def observe_date(self, date: str | None) -> int | None:
        """Feed the latest OCR'd hub date; returns the (possibly updated) round."""
        canonical = _canonical_date(date)
        if canonical is None:
            return self.current_round
        if canonical != self._last_date:
            self._last_date = canonical
            self._round += 1
        return self.current_round

    def set_round(self, n: int) -> None:
        """用目标弹窗 N/45 的绝对回合数校准(§22.9)。N/45 比日期计数准(日期同旬漏计/
        OCR 丢月份跳帧), 故读到 N 时直接覆盖 _round。保留 observe_date 作 fallback
        (目标弹窗没读到时仍能靠日期计数兜底)。"""
        if isinstance(n, int) and n > 0:
            self._round = n
