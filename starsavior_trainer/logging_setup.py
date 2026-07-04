"""Centralized logging for the Starsavior trainer.

Call ``get_logger(__name__)`` (or any short name) to obtain a logger that:
- prints INFO and above to the console, and
- writes DEBUG and above to a dated file ``logs/YYYY-MM-DD.log``.
- writes ERROR and above to a separate ``logs/YYYY-MM-DD_error.log``.

Everything is UTF-8 so Chinese messages are not mangled. Configuration runs once
(idempotent) on the shared ``starsavior`` parent logger, so importing this from
many modules is safe.

Features:
- 按日期自动分割日志文件
- 错误日志单独记录
- 自动清理 30 天前的旧日志
- 日志文件轮转（单文件最大 10MB）
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from logging.handlers import RotatingFileHandler

_LOG_ROOT = "starsavior"
_configured = False

# logs/ lives at the project root (one level up from this package).
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"


def _cleanup_old_logs(log_dir: Path, days: int = 7) -> None:
    """清理超过指定天数的日志文件"""
    if not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for log_file in log_dir.glob("*.log*"):
        try:
            # 从文件名提取日期（格式：YYYY-MM-DD.log 或 YYYY-MM-DD_error.log）
            date_str = log_file.stem.split("_")[0]
            if len(date_str) == 10:  # YYYY-MM-DD
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    log_file.unlink()
                    deleted_count += 1
        except (ValueError, IndexError):
            continue

    if deleted_count > 0:
        logging.getLogger(_LOG_ROOT).info(f"清理了 {deleted_count} 个旧日志文件")


def _configure() -> None:
    global _configured
    if _configured:
        return

    logger = logging.getLogger(_LOG_ROOT)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't double-log through the root logger

    # --- Console handler: INFO and above ---
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    try:  # force UTF-8 so Chinese isn't garbled on Windows consoles
        console.stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    logger.addHandler(console)

    # --- File handler: DEBUG and above, one file per day with rotation ---
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 清理旧日志（7天前）
        _cleanup_old_logs(LOG_DIR, days=7)

        today = date.today().isoformat()

        # 主日志文件（所有级别）
        file_handler = RotatingFileHandler(
            LOG_DIR / f"{today}.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(file_handler)

        # 错误日志单独记录
        error_handler = RotatingFileHandler(
            LOG_DIR / f"{today}_error.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s\n%(exc_info)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(error_handler)

        logger.info(f"日志系统已初始化，日志目录: {LOG_DIR}")
    except OSError as e:
        # File logging is best-effort; the console handler still works.
        logger.warning(f"无法创建日志文件: {e}")

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured child logger under the shared ``starsavior`` parent."""
    _configure()
    return logging.getLogger(f"{_LOG_ROOT}.{name}")
