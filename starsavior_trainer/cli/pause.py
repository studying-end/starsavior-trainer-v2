"""暂停控制 — F9 全局热键 + PauseController 状态标志。

迁自旧 cli/live_loop.py（146-215）。F9 而非 F12：F12 是 Steam 截图键，会被 Steam
吞掉，全局钩子收不到；trigger_on_release=True 防止按住时 OS 按键重复把标志翻转回原状（坑 #17）。
keyboard 库装系统级钩子，Windows 下可能需管理员权限；注册失败只告警不抛，脚本照常运行。
"""
from __future__ import annotations

from starsavior_trainer.logging_setup import get_logger

logger = get_logger("pause")


class PauseController:
    """Toggle-able pause flag for the live loop, flipped by a global F9 hotkey.

    The main loop reads :pyattr:`paused` once per iteration; the hotkey
    callback runs on the ``keyboard`` library's listener thread and flips the
    flag.  A plain bool read/write is atomic in CPython, so no lock is needed.
    """

    def __init__(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def toggle(self) -> bool:
        """Flip the pause state and return the new value (bound to the hotkey)."""
        self._paused = not self._paused
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False


def install_pause_hotkey(controller: PauseController, key: str = "f11") -> bool:
    """Register a global hotkey that toggles ``controller``'s pause state.

    Defaults to **F11**（用户指定）。F12 是 Steam 截图键会被 Steam 吞掉、全局钩子
    收不到；F11 为暂停/恢复热键。

    Binds with ``trigger_on_release=True`` so a slightly-held press can't fire
    the OS key-repeat several times and toggle the flag back to where it started
    (another "no effect" failure mode).

    Uses the ``keyboard`` library.  IMPORTANT: ``keyboard`` installs a
    low-level, system-wide keyboard hook.  Listening for a *global* hotkey can
    therefore require **running this console as Administrator** on Windows
    (and requires root on Linux); without sufficient privileges the hook may
    fail to register.

    This function never raises: if the library isn't installed, or the hook
    can't be registered (e.g. insufficient privileges), it logs/prints a
    warning and returns ``False`` so the caller keeps running normally — just
    without the hotkey.
    """
    try:
        import keyboard  # type: ignore  # lazy: only needed for the live hotkey
    except Exception as exc:  # ImportError or any other import-time failure
        msg = f"暂停热键不可用（keyboard 库导入失败: {exc}）。脚本将正常运行。"
        logger.warning(msg)
        print(f"[warn] {msg}")
        return False

    try:
        keyboard.add_hotkey(key, controller.toggle, trigger_on_release=True)
    except Exception as exc:  # registration failed — often needs admin rights
        msg = f"暂停热键注册失败（监听全局热键可能需要管理员权限运行: {exc}）。脚本将正常运行。"
        logger.warning(msg)
        print(f"[warn] {msg}")
        return False

    logger.info(f"{key.upper()} 暂停热键已启用。")
    print(f"{key.upper()} 暂停热键已启用：实跑中按 {key.upper()} 可暂停/恢复（夺回控制权）。")
    return True
