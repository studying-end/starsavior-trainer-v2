"""Starsavior Trainer Web UI - Flask Backend

A web-based control panel for the Starsavior trainer.
Provides REST API endpoints for all CLI operations.

子进程/日志/配置基础设施在 web/process_manager.py（本文件聚焦路由）。

Run with:
    python -m starsavior_trainer.web.app
    or
    python starsavior_trainer/web/app.py
"""
from __future__ import annotations

import json
import sys
import threading
from queue import Empty

from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS

from starsavior_trainer.web.process_manager import (
    BUILD_PROFILES,
    CLASSIFY_MODES,
    PROJECT_ROOT,
    _load_characters,
    _list_region_profiles,
    _run_command,
    current_process,
    log_queue,
    process_lock,
)

app = Flask(__name__,
            template_folder=str(PROJECT_ROOT / "starsavior_trainer" / "web" / "templates"),
            static_folder=str(PROJECT_ROOT / "starsavior_trainer" / "web" / "static"))
CORS(app)


@app.route("/")
def index():
    """Serve the main web UI."""
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get initial configuration data."""
    return jsonify({
        "profiles": _list_region_profiles(),
        "characters": _load_characters(),
        "build_profiles": BUILD_PROFILES,
        "classify_modes": CLASSIFY_MODES,
        "project_root": str(PROJECT_ROOT),
    })


@app.route("/api/process/status", methods=["GET"])
def process_status():
    """Check if a process is currently running."""
    with process_lock:
        running = current_process is not None and current_process.poll() is None
    return jsonify({"running": running})


@app.route("/api/process/stop", methods=["POST"])
def stop_process():
    """Stop the currently running process."""
    with process_lock:
        if current_process and current_process.poll() is None:
            current_process.terminate()
            log_queue.put("\n[STOP] 进程已终止\n")
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "没有运行中的进程"})


@app.route("/api/logs/stream")
def stream_logs():
    """Server-Sent Events endpoint for streaming logs."""
    def generate():
        while True:
            try:
                line = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'log': line})}\n\n"
            except Empty:
                yield f"data: {json.dumps({'ping': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    """Clear the log queue."""
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except Empty:
            break
    return jsonify({"success": True})


@app.route("/api/train/start", methods=["POST"])
def start_training():
    """Start journey then training loop."""
    data = request.json or {}

    character = data.get("character", "")
    if not character:
        return jsonify({"success": False, "error": "未选择角色"}), 400

    # Step 1: Start journey
    journey_cmd = [sys.executable, "-m", "starsavior_trainer.cli.start_journey", character]

    difficulty = data.get("journey_difficulty", "一般")
    journey_cmd.extend(["--difficulty", difficulty])

    seal_slot1 = data.get("seal_slot1", 1)
    journey_cmd.extend(["--seal1", str(seal_slot1)])

    seal_slot2 = data.get("seal_slot2", 1)
    journey_cmd.extend(["--seal2", str(seal_slot2)])

    card_group = data.get("support_card_group", 1)
    journey_cmd.extend(["--card-group", str(card_group)])

    friend_name = data.get("friend_name", "")
    if friend_name:
        journey_cmd.extend(["--friend", friend_name])

    # Step 2: Training loop
    train_cmd = [sys.executable, "-m", "starsavior_trainer.cli.live_loop"]

    window_title = data.get("window_title", "StarSavior")
    train_cmd.extend(["--window-title", window_title])

    interval = data.get("interval", 2.0)
    train_cmd.extend(["--interval", str(interval)])

    max_rounds = data.get("max_rounds")
    if max_rounds:
        train_cmd.extend(["--max-rounds", str(max_rounds)])

    profile = data.get("profile", "config/regions/2560x1440.json")
    train_cmd.extend(["--profile", profile])

    train_cmd.extend(["--character", character])

    build_profile = data.get("build_profile", "balanced")
    train_cmd.extend(["--build-profile", build_profile])

    classify_flag = data.get("classify_flag", "--hybrid-mode")
    if classify_flag:
        train_cmd.extend(classify_flag.split())

    if data.get("execute_clicks", False):
        train_cmd.append("--execute")

    # Run journey then training sequentially
    def run_journey_then_train():
        log_queue.put("[INFO] 第1步: 启动旅程\n")
        _run_command(journey_cmd)
        log_queue.put("\n[INFO] 第2步: 开始训练循环\n")
        _run_command(train_cmd)

    threading.Thread(target=run_journey_then_train, daemon=True).start()

    return jsonify({
        "success": True,
        "journey_command": " ".join(journey_cmd),
        "train_command": " ".join(train_cmd)
    })


@app.route("/api/journey/start", methods=["POST"])
def start_journey():
    """Start the journey flow."""
    data = request.json or {}

    character = data.get("character", "")
    if not character:
        return jsonify({"success": False, "error": "未选择角色"}), 400

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.start_journey", character]

    # Difficulty
    difficulty = data.get("difficulty", "一般")
    cmd.extend(["--difficulty", difficulty])

    # Seal slots
    seal_slot1 = data.get("seal_slot1", 1)
    cmd.extend(["--seal1", str(seal_slot1)])

    seal_slot2 = data.get("seal_slot2", 1)
    cmd.extend(["--seal2", str(seal_slot2)])

    # Support card group
    card_group = data.get("support_card_group", 1)
    cmd.extend(["--card-group", str(card_group)])

    # Friend name
    friend_name = data.get("friend_name", "")
    if friend_name:
        cmd.extend(["--friend", friend_name])

    # Run in thread
    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/capture/screenshot", methods=["POST"])
def capture_screenshot():
    """Capture a screenshot."""
    data = request.json or {}

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.capture_once"]

    window_title = data.get("window_title", "StarSavior")
    cmd.extend(["--window-title", window_title])

    output_path = data.get("output_path", "./screenshots/capture.png")
    cmd.extend(["--out", output_path])

    if data.get("timestamp", False):
        cmd.append("--timestamp")

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/capture/list-windows", methods=["POST"])
def list_windows():
    """List visible windows."""
    cmd = [sys.executable, "-m", "starsavior_trainer.cli.capture_once", "--list-windows"]

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True})


@app.route("/api/calibrate/crop-regions", methods=["POST"])
def crop_regions():
    """Crop regions from an image."""
    data = request.json or {}

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.crop_regions"]

    image_path = data.get("image_path")
    if not image_path:
        return jsonify({"success": False, "error": "需要提供 image_path"})

    cmd.extend(["--image", image_path])

    profile = data.get("profile", "config/regions/2560x1440.json")
    cmd.extend(["--profile", profile])

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/calibrate/read-regions", methods=["POST"])
def read_regions():
    """Read OCR from regions."""
    data = request.json or {}

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.read_regions"]

    image_path = data.get("image_path")
    if not image_path:
        return jsonify({"success": False, "error": "需要提供 image_path"})

    cmd.extend(["--image", image_path])

    profile = data.get("profile", "config/regions/2560x1440.json")
    cmd.extend(["--profile", profile])

    engine = data.get("engine", "paddle")
    cmd.extend(["--engine", engine])

    prefix = data.get("prefix")
    if prefix:
        cmd.extend(["--prefix", prefix])

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/offline/demo", methods=["POST"])
def offline_demo():
    """Run offline harness in demo mode."""
    data = request.json or {}

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.offline_harness", "--demo"]

    profile = data.get("profile", "config/regions/2560x1440.json")
    cmd.extend(["--profile", profile])

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/offline/manifest", methods=["POST"])
def offline_manifest():
    """Run offline harness with a manifest."""
    data = request.json or {}

    manifest_path = data.get("manifest_path")
    if not manifest_path:
        return jsonify({"success": False, "error": "需要提供 manifest_path"})

    cmd = [sys.executable, "-m", "starsavior_trainer.cli.offline_harness"]
    cmd.extend(["--manifest", manifest_path])

    if data.get("jsonl", False):
        cmd.append("--jsonl")

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True, "command": " ".join(cmd)})


@app.route("/api/tests/run", methods=["POST"])
def run_tests():
    """Run unit tests."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]

    threading.Thread(target=_run_command, args=(cmd,), daemon=True).start()

    return jsonify({"success": True})


@app.route("/api/logs/list", methods=["GET"])
def list_logs():
    """List available log files."""
    logs_dir = PROJECT_ROOT / "logs"
    if not logs_dir.exists():
        return jsonify({"files": []})

    files = []
    for log_file in sorted(logs_dir.glob("*.log"), reverse=True):
        stat = log_file.stat()
        files.append({
            "name": log_file.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })

    return jsonify({"files": files})


@app.route("/api/logs/read", methods=["GET"])
def read_log():
    """Read log file content."""
    filename = request.args.get("filename")
    if not filename:
        return jsonify({"success": False, "error": "需要提供 filename 参数"})

    logs_dir = PROJECT_ROOT / "logs"
    log_file = logs_dir / filename

    # 安全检查：防止路径遍历攻击
    if not log_file.resolve().is_relative_to(logs_dir.resolve()):
        return jsonify({"success": False, "error": "非法文件路径"})

    if not log_file.exists():
        return jsonify({"success": False, "error": "文件不存在"})

    try:
        # 读取最后 1000 行
        lines = log_file.read_text(encoding="utf-8").splitlines()
        tail_lines = lines[-1000:] if len(lines) > 1000 else lines
        return jsonify({"success": True, "content": "\n".join(tail_lines)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    print(f"Starsavior Trainer Web UI")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"访问地址: http://localhost:5000")
    print(f"按 Ctrl+C 停止服务器")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
