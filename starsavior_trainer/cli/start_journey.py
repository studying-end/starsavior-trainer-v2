"""旅程启动脚本 — 从游戏主界面进入训练大厅的前置流程。

复用单屏状态机（capture→classify→parse→decide→execute），遇到 TRAINING_HUB 即成功
退出。不带训练循环 inspector / round_tracker / UNKNOWN 兜底（启动流程用不上）。

参数与 web/app.py 调用约定一致：character（必填）+ --difficulty/--seal1/--seal2/
--card-group/--friend。其中 character/--variant/--build-profile 有效；其余参数 v2
当前未实现（_decide_initial 不选难度，blessing_setup 只点空槽不选具体刻印，
journey_start 不选卡组），接收并打印提示。

Usage:
    python -m starsavior_trainer.cli.start_journey 克莱儿 --execute
    python -m starsavior_trainer.cli.start_journey 克莱儿 --difficulty 困难 --seal1 1 --seal2 1 --card-group 1 --friend 好友名 --execute
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("FLAGS_use_mkldnn", "0")
for _noisy in ("ppocr", "paddle", "paddlex", "PIL"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

from starsavior_trainer.capture import activate_window, capture_window
from starsavior_trainer.classifier import (
    classify_by_blue_button,
    classify_by_ocr,
    classify_hybrid,
)
from starsavior_trainer.cli.blue_parsers import (
    _read_screen_payload_blue,
    _read_screen_payload_ocr,
)
from starsavior_trainer.cli.pause import PauseController, install_pause_hotkey
from starsavior_trainer.cli.runtime import (
    _create_ocr,
    _find_or_exit,
    _print_windows,
    pause_requested,
    stop_requested,
)
from starsavior_trainer.executor import DryRunExecutor, PyAutoGuiExecutor, map_action_to_rect
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import Action, GameState, Observation, Rect, Screen
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.policy.engine import TrainerPolicy
from starsavior_trainer.regions import load_region_profile, scale_region_profile

logger = get_logger("start_journey")

# 启动流程最多跑多少步（防止无限循环）
_MAX_STEPS = 200
# 连续 UNKNOWN 多少步后放弃
_MAX_CONSECUTIVE_UNKNOWN = 10


def main() -> int:
    parser = argparse.ArgumentParser(description="Starsavior 旅程启动脚本（从主界面到训练大厅）。")
    parser.add_argument("character", help="目标角色名（中文），如 克莱儿")
    parser.add_argument("--variant", default="", help="角色形态（同名多形态时区分）")
    parser.add_argument("--build-profile", default="balanced", help="Build profile")
    # web/app.py 调用约定参数（v2 当前未实现，接收并提示）
    parser.add_argument("--difficulty", default="一般", help="难度（v2 未实现难度选择，使用游戏默认）")
    parser.add_argument("--seal1", type=int, default=1, help="刻印槽1位置（v2 未实现具体刻印选择）")
    parser.add_argument("--seal2", type=int, default=1, help="刻印槽2位置（v2 未实现具体刻印选择）")
    parser.add_argument("--card-group", type=int, default=1, help="支援卡组（v2 未实现卡组选择）")
    parser.add_argument("--friend", default="", help="好友名（v2 未实现好友卡匹配）")
    # 与 live_loop 一致的参数
    parser.add_argument("--window-title", default="StarSavior", help="游戏窗口标题子串")
    parser.add_argument("--profile", default="config/regions/2560x1440.json", help="Region profile 路径")
    parser.add_argument("--execute", action="store_true", help="真点（默认 dry-run）")
    parser.add_argument("--interval", type=float, default=0.5, help="循环间隔秒")
    parser.add_argument("--max-iterations", type=int, default=_MAX_STEPS, help="最大步数")
    parser.add_argument("--use-paddle", action="store_true", help="使用 RapidOCR（旧名兼容）")
    parser.add_argument("--ocr-engine", choices=("auto", "gpu", "cpu"), default="auto", help="OCR 引擎")
    parser.add_argument("--blue-mode", action="store_true", help="纯蓝键分类（无 OCR）")
    parser.add_argument("--hybrid-mode", action="store_true", help="蓝键分类 + OCR payload")
    parser.add_argument("--list-windows", action="store_true", help="列出窗口并退出")
    parser.add_argument("--verbose", action="store_true", help="打印 OCR/颜色详情")
    args = parser.parse_args()

    if args.list_windows:
        _print_windows()
        return 0

    # 加载角色配置（填 character_class，与 live_loop 一致逻辑）
    state = GameState(
        desired_character=args.character,
        desired_variant=args.variant,
        build_profile=args.build_profile,
    )
    if args.character:
        try:
            import json as _json
            _char_file = Path(__file__).resolve().parent.parent.parent / "config" / "characters.json"
            _data = _json.loads(_char_file.read_text(encoding="utf-8"))
            for _entry in _data.get("characters", []):
                if str(_entry.get("name", "")).strip() == args.character and str(_entry.get("variant", "")).strip() == (args.variant or ""):
                    state = replace(state, character_class=str(_entry.get("class", "")).strip() or None)
                    break
        except (OSError, _json.JSONDecodeError):
            pass

    # 打印启动信息
    print("=== 旅程启动 ===")
    print(f"角色: {args.character} (variant={args.variant or '普通'}, class={state.character_class or 'unknown'})")
    print(f"build_profile: {args.build_profile}")
    # 未实现参数提示
    unimplemented = []
    if args.difficulty != "一般":
        unimplemented.append(f"--difficulty={args.difficulty}")
    if args.seal1 != 1:
        unimplemented.append(f"--seal1={args.seal1}")
    if args.seal2 != 1:
        unimplemented.append(f"--seal2={args.seal2}")
    if args.card_group != 1:
        unimplemented.append(f"--card-group={args.card_group}")
    if args.friend:
        unimplemented.append(f"--friend={args.friend}")
    if unimplemented:
        print(f"[提示] v2 当前未实现以下参数（使用游戏默认）: {', '.join(unimplemented)}")
    print(f"mode={'execute' if args.execute else 'dry-run'} interval={args.interval}")

    # 初始化
    window = _find_or_exit(args.window_title)
    base_profile = load_region_profile(args.profile)
    policy = TrainerPolicy()
    executor = PyAutoGuiExecutor() if args.execute else DryRunExecutor()
    ocr = _create_ocr(args.use_paddle, args.ocr_engine)
    blue_detector = None
    if args.hybrid_mode:
        mode_label = "hybrid"
        args.use_paddle = True
        ocr = _create_ocr(True, args.ocr_engine)
    elif args.blue_mode:
        mode_label = "blue-button"
        from starsavior_trainer.vision import BlueButtonDetector
        blue_detector = BlueButtonDetector()
    elif args.use_paddle:
        mode_label = "rapid"
    else:
        mode_label = "noop"
    print(f"profile={base_profile.name} regions={len(base_profile.regions)} mode={mode_label}")
    print(f"game window: {window.title} ({window.rect.width}x{window.rect.height})")
    if not args.execute:
        print("[提示] 旅程启动需要真点，当前 dry-run 模式（不点击）。加 --execute 真点。")

    pause = PauseController()
    install_pause_hotkey(pause, key="f11")
    print("[控制] 急停: 创建 stop.flag 文件 / Ctrl+C | 暂停: 创建 pause.flag 文件 / F11")

    # 主循环（精简版 live_loop，无 inspector / round_tracker / UNKNOWN 兜底）
    # 急停只走 Ctrl+C（KeyboardInterrupt）。原鼠标角落检测在点击角落区按钮后误判，已移除。
    iteration = 0
    consecutive_unknown = 0
    was_paused = False
    try:
        while iteration < args.max_iterations:
            if stop_requested():
                print("\n[急停] 检测到 stop.flag 文件，已停止 bot。")
                return 1
            if pause.paused or pause_requested():
                was_paused = True
                print("已暂停（F11 或 pause.flag，删除 pause.flag / 再按 F11 恢复）")
                time.sleep(1.0)
                continue
            if was_paused:
                print("已恢复")
                was_paused = False

            iteration += 1
            screenshot, client_window = capture_window(args.window_title)
            profile = scale_region_profile(base_profile, screenshot.size)
            reader = RegionOcrReader(profile, ocr)

            print(f"\n--- step {iteration}/{args.max_iterations} ---")

            # Classify
            if args.hybrid_mode or args.use_paddle:
                observation = classify_hybrid(screenshot, profile, reader)
            elif args.blue_mode:
                observation = classify_by_blue_button(screenshot, profile)
            else:
                observation = classify_by_ocr(screenshot, profile, reader)

            logger.info(f"screen={observation.screen.value} confidence={observation.confidence:.2f}")
            print(f"  screen={observation.screen.value} confidence={observation.confidence:.2f}")

            # 成功条件：到达训练大厅
            if observation.screen == Screen.TRAINING_HUB:
                print(f"\n=== 旅程启动完成（{iteration} 步）===")
                return 0

            # UNKNOWN 处理：点中心推进（与 live_loop 一致），连续超阈值则放弃
            if observation.screen == Screen.UNKNOWN:
                consecutive_unknown += 1
                print(f"  unknown screen (consecutive={consecutive_unknown})")
                if consecutive_unknown >= _MAX_CONSECUTIVE_UNKNOWN:
                    print(f"\n[失败] 连续 {_MAX_CONSECUTIVE_UNKNOWN} 次 UNKNOWN，放弃。")
                    return 1
                if args.execute:
                    activate_window(client_window.hwnd)
                    cx = client_window.rect.x + client_window.rect.width // 2
                    cy = client_window.rect.y + client_window.rect.height // 2
                    executor.execute(Action("click", Rect(cx, cy, 1, 1), "unknown: click centre"))
                time.sleep(args.interval)
                continue
            consecutive_unknown = 0

            # Parse payload
            if args.blue_mode:
                payload = _read_screen_payload_blue(observation.screen, screenshot, profile, blue_detector, args.verbose)
            else:
                payload = _read_screen_payload_ocr(observation.screen, screenshot, profile, reader, args.verbose)
            if payload is not None:
                observation = Observation(screen=observation.screen, confidence=observation.confidence, payload=payload)

            # Decide
            action = policy.decide(state, observation)
            logger.info(f"decision: {action.kind} target={action.target} reason={action.reason}")
            print(f"  action={action.kind} target={action.target} reason={action.reason}")

            # Execute
            screen_action = map_action_to_rect(action, screenshot.size, client_window.rect)
            if args.execute and action.kind in ("click", "move", "scroll"):
                activate_window(client_window.hwnd)
            executor.execute(screen_action)
            time.sleep(args.interval)

        print(f"\n[失败] 达到最大步数 {args.max_iterations}，未到达训练大厅。")
        return 1

    except KeyboardInterrupt:
        print("\n[急停] Ctrl+C 已停止 bot，控制权交还。")
        return 1
    except RuntimeError as exc:
        print(f"\n错误: {exc}")
        return 1
    except Exception as exc:
        if type(exc).__name__ == "FailSafeException":
            print("\n[FAILSAFE] 鼠标移到屏幕角落，已紧急停止。")
            return 1
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
        sys.exit(1)
