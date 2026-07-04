"""CLI 运行时支持 — 鼠标急停 + OCR 工厂 + 窗口查找。

从 cli/live_loop.py 抽出（满足单文件 ≤400 行规范）。main 12 步主循环保留在
live_loop.py；这些无状态 helper 集中于此，让 live_loop 聚焦迭代编排。
"""
from __future__ import annotations

from starsavior_trainer.capture import WindowInfo, list_windows
from starsavior_trainer.ocr import NoopOcrEngine, RapidOcrEngine


# ---------------------------------------------------------------------------
# Mouse-corner emergency stop — most reliable "reclaim control" path
# ---------------------------------------------------------------------------


def _is_corner_point(x: int, y: int, width: int, height: int, margin: int = 120) -> bool:
    """True if (x, y) lies within ``margin`` px of ANY of the four screen corners.

    Robust emergency-stop predicate: a corner is "near a horizontal edge AND near
    a vertical edge" — so edge midpoints (near only one axis) don't count, but all
    four corner regions do. Unlike pyautogui's exact-pixel FAILSAFE this triggers
    on a whole region, so a quick mouse-slam reliably stops the bot.
    """
    near_left = x <= margin
    near_right = x >= width - margin
    near_top = y <= margin
    near_bottom = y >= height - margin
    return (near_left or near_right) and (near_top or near_bottom)


def _mouse_at_screen_corner(margin: int = 120) -> bool:
    """Read the OS cursor position and report whether it's in a screen corner.

    Used at the top of every loop iteration as a reliable manual stop that does
    NOT depend on pyautogui's call timing or exact-pixel FAILSAFE points. Never
    raises — any failure (non-Windows, ctypes issue) reports "not in corner" so
    the loop keeps running.
    """
    try:
        import ctypes
        from ctypes import wintypes

        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)
        return _is_corner_point(pt.x, pt.y, width, height, margin)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Shared CLI helpers
# ---------------------------------------------------------------------------


def _create_ocr(use_paddle: bool, ocr_engine: str = "auto"):
    # use_paddle 旧名保留（兼容 --use-paddle flag / web UI）；实际用 RapidOcrEngine。
    # ocr_engine 新参数（2026-07-04）: "auto"/"gpu"/"cpu" 让用户选 OCR 引擎。
    #   auto: 优先 GPU, 不可用回退 CPU（默认）
    #   gpu: 强制 GPU, 不可用回退 CPU（带 warning）
    #   cpu: 强制 CPU
    if use_paddle:
        try:
            return RapidOcrEngine(engine=ocr_engine)
        except RuntimeError as exc:
            print(f"warning: OCR not available ({exc}), falling back to noop")
    return NoopOcrEngine()


def _find_or_exit(title: str) -> WindowInfo:
    windows = list_windows()
    for win in windows:
        if title.casefold() in win.title.casefold():
            return win
    print(f"window '{title}' not found. Available windows:")
    _print_windows()
    raise SystemExit(1)


def _print_windows() -> None:
    for win in sorted(list_windows(), key=lambda w: w.title.casefold()):
        print(f"  {win.hwnd} {win.rect.width}x{win.rect.height} {win.title}")
