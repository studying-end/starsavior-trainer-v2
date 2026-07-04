"""极其详细的单帧运行日志（dry-run，不点击）。复用 debug_log 模块的 dump 逻辑。

对当前游戏帧（或 --image 截图）跑 capture→classify→parse→decide，输出识别+payload+决策。
单帧离线诊断用；live_loop 运行时详细日志用 `--debug` flag（每帧 dump，见 debug_log.py）。

用法:
  python -m scripts.detailed_frame_log                       # 实时截当前 StarSavior 帧
  python -m scripts.detailed_frame_log --image screenshots/flash_check.png
  python -m scripts.detailed_frame_log --build stamina_tank
"""
from __future__ import annotations

import argparse
import sys

from PIL import Image

from starsavior_trainer.capture import capture_window
from starsavior_trainer.classifier import classify_hybrid
from starsavior_trainer.cli.blue_parsers import _read_screen_payload_ocr
from starsavior_trainer.debug_log import _r, dump_payload
from starsavior_trainer.models import GameState, Observation
from starsavior_trainer.ocr import RapidOcrEngine
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.policy.engine import TrainerPolicy
from starsavior_trainer.regions import load_region_profile, scale_region_profile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser(description="极其详细的单帧运行日志（dry-run，不点击）")
    ap.add_argument("--window-title", default="StarSavior")
    ap.add_argument("--image", help="用指定截图而非实时截屏")
    ap.add_argument("--profile", default="config/regions/2560x1440.json")
    ap.add_argument("--build", default="balanced")
    ap.add_argument("--save", help="保存当前帧到此路径")
    args = ap.parse_args()

    print("=" * 64)
    if args.image:
        screenshot = Image.open(args.image)
        print(f"=== 截图来源: 文件 {args.image} ({screenshot.size[0]}x{screenshot.size[1]}) ===")
    else:
        screenshot, window = capture_window(args.window_title)
        print(f"=== 截图来源: 实时窗口 {window.title!r} ({screenshot.size[0]}x{screenshot.size[1]}) ===")
    if args.save:
        screenshot.save(args.save)
        print(f"  已保存帧到 {args.save}")

    profile = scale_region_profile(load_region_profile(args.profile), screenshot.size)
    reader = RegionOcrReader(profile, RapidOcrEngine())

    print("=== 第1步 识别画面（classify_hybrid）===")
    obs = classify_hybrid(screenshot, profile, reader)
    print(f"  → 画面={obs.screen.value}  置信度={obs.confidence:.2f}")

    print("=== 第2步 解析画面元素（parse payload）===")
    payload = _read_screen_payload_ocr(obs.screen, screenshot, profile, reader, verbose=False)
    dump_payload(payload)
    obs = Observation(screen=obs.screen, confidence=obs.confidence, payload=payload)

    print("=== 第3步 决策（policy.decide）===")
    state = GameState(build_profile=args.build)
    action = TrainerPolicy().decide(state, obs)
    target = _r(action.target) if hasattr(action.target, "x") else repr(action.target)
    repeat = f" ×{action.repeat}" if getattr(action, "repeat", 1) and action.repeat > 1 else ""
    print(f"  → 动作={action.kind}  目标={target}{repeat}  理由={action.reason}")

    print("=" * 64)
    print(f"➡ 最终选择: {action.kind}  |  {action.reason}")
    print("=" * 64)


if __name__ == "__main__":
    main()
