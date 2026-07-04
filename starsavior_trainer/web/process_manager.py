"""Flask Web UI 的子进程/日志/配置基础设施。

从 web/app.py 抽出（满足单文件 ≤400 行规范）。持有全局单进程状态（current_process/
process_lock/log_queue）+ 子进程包装 _run_command + 配置读取 helper + 常量。
app.py 的路由通过本模块共享同一份状态（模块级单例）。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from queue import Queue

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGIONS_DIR = PROJECT_ROOT / "config" / "regions"
CHARACTERS_FILE = PROJECT_ROOT / "config" / "characters.json"

# Global process state (module-level singletons shared with app.py)
current_process: subprocess.Popen | None = None
process_lock = threading.Lock()
log_queue: Queue[str] = Queue()

BUILD_PROFILES = [
    "balanced",
    "power_focus",
    "focus_focus",
    "durability_focus",
    "stamina_tank",
    "protection_focus",
]

CLASSIFY_MODES = [
    {"label": "Hybrid (蓝键分类 + OCR)", "flag": "--hybrid-mode"},
    {"label": "Hybrid (蓝键分类 + RapidOCR GPU)", "flag": "--hybrid-mode --use-paddle"},
    {"label": "Blue button only (纯蓝键)", "flag": "--blue-mode"},
    {"label": "RapidOCR GPU [需要 N 卡]", "flag": "--use-paddle"},
    {"label": "Noop (无 OCR)", "flag": ""},
]


def _list_region_profiles() -> list[str]:
    """List available region profile JSON files."""
    if not REGIONS_DIR.is_dir():
        return ["config/regions/2560x1440.json"]
    rels = [
        str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for p in sorted(REGIONS_DIR.glob("*.json"))
    ]
    return rels or ["config/regions/2560x1440.json"]


def _load_characters() -> list[dict[str, str]]:
    """Load character roster from config/characters.json."""
    try:
        data = json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    roster: list[dict[str, str]] = []
    for entry in data.get("characters", []):
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        roster.append({
            "name": name,
            "profile": str(entry.get("profile", "balanced")).strip() or "balanced",
            "class": str(entry.get("class", "")).strip(),
            "variant": str(entry.get("variant", "")).strip(),
        })
    return roster


def _run_command(cmd: list[str]) -> None:
    """Run a command in a subprocess and stream output to log_queue."""
    global current_process

    try:
        with process_lock:
            if current_process and current_process.poll() is None:
                log_queue.put("[ERROR] 已有进程在运行\n")
                return

            log_queue.put(f"[CMD] {' '.join(cmd)}\n")

            # Force UTF-8 environment for subprocess on Windows
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(PROJECT_ROOT),
                encoding="utf-8",
                errors="replace",
                env=env,
            )

        # Stream output
        if current_process and current_process.stdout:
            for line in current_process.stdout:
                log_queue.put(line)
            current_process.stdout.close()  # 显式关管道，避免 FD 泄漏 ResourceWarning

        with process_lock:
            if current_process:
                current_process.wait()
                exit_code = current_process.returncode
                log_queue.put(f"\n[DONE] 进程退出，代码: {exit_code}\n")
                current_process = None

    except Exception as e:
        log_queue.put(f"[ERROR] {str(e)}\n")
        with process_lock:
            current_process = None
