"""Live training loop: capture -> classify -> parse -> decide -> click.

单屏状态机主循环（12 步迭代严格复刻架构文档 §4）。拆分自旧 cli/live_loop.py：
- 暂停热键 → cli/pause.py
- payload 读取（OCR/blue）→ cli/blue_parsers.py
- 急停 + OCR 工厂 + 窗口 helper → cli/runtime.py
- 本文件：常量 + main 12 步主循环

Usage:
    python -m starsavior_trainer.cli.live_loop --dry-run
    python -m starsavior_trainer.cli.live_loop --profile config/regions/2560x1440.json --use-paddle --execute
    python -m starsavior_trainer.cli.live_loop --blue-mode --execute
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("FLAGS_use_mkldnn", "0")
# Quiet noisy third-party loggers (PaddleOCR/paddle) WITHOUT muting our own
# starsavior.* logger. (Previously this was a blanket logging.disable(CRITICAL)
# that also silenced the trainer's logs.)
for _noisy in ("ppocr", "paddle", "paddlex", "PIL"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

from starsavior_trainer.capture import activate_window, capture_window, save_image
from starsavior_trainer.classifier import (
    classify_by_blue_button,
    classify_by_ocr,
    classify_hybrid,
)
from starsavior_trainer.classifier_signatures import (
    classify_journey_origin_by_visual,
    journey_origin_visual_scores,
)
from starsavior_trainer.cli.blue_parsers import (
    _read_screen_payload_blue,
    _read_screen_payload_ocr,
)
from starsavior_trainer.cli.pause import PauseController, install_pause_hotkey
from starsavior_trainer.cli.runtime import (
    _create_ocr,
    _find_or_exit,
    _is_corner_point,
    _mouse_at_screen_corner,
    _print_windows,
)
from starsavior_trainer.executor import DryRunExecutor, PyAutoGuiExecutor, map_action_to_rect
from starsavior_trainer.inspectors.commission_inspector import CommissionInspector
from starsavior_trainer.inspectors.shop_inspector import ShopInspector
from starsavior_trainer.inspectors.skill_inspector import SkillInspector
from starsavior_trainer.inspectors.training_inspector import TrainingInspector
from starsavior_trainer.logging_setup import get_logger
from starsavior_trainer.models import (
    Action,
    BlessingChoice,
    CommissionChoice,
    GameState,
    GoalDialogStatus,
    Observation,
    Rect,
    Screen,
    ShopScene,
    TrainingChoice,
    TrainingHubStatus,
)
from starsavior_trainer.ocr_reader import RegionOcrReader
from starsavior_trainer.policy.engine import TrainerPolicy, _is_iterable_of
from starsavior_trainer.regions import load_region_profile, scale_region_profile
from starsavior_trainer.round_tracker import RoundTracker
from starsavior_trainer.behavior import narrate
from starsavior_trainer.text_utils import parse_first_int
from starsavior_trainer.vision import BlueButtonDetector

logger = get_logger("live_loop")


# "Tap to continue / skip" advance screens: after acting we re-capture almost
# immediately instead of waiting the full --interval, so the loop blows through
# reward popups / dialogue / post-training quickly (the user's "keep clicking to
# advance" request) — but still classifies before every click, so we never click
# blindly into the screen that comes next.
_ADVANCE_SCREENS = frozenset({Screen.DIALOGUE, Screen.POST_TRAINING, Screen.REWARD})
_ADVANCE_SLEEP = 0.35
# TRAINING_SELECT: the inspector clicks 力量/体力/韧性 in quick succession on the
# SAME screen (no transition) — it only needs the preview gain to render, not the
# full --interval. Use a short re-capture sleep so picking a training is snappy.
_TRAINING_SELECT_SLEEP = 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description="Starsavior live training loop.")
    parser.add_argument("--profile", default="config/regions/2560x1440.json", help="Region profile path.")
    parser.add_argument("--window-title", default="StarSavior", help="Game window title substring.")
    parser.add_argument("--execute", action="store_true", help="Execute clicks (default: dry-run).")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between loop iterations (default 0.5).")
    parser.add_argument("--max-iterations", type=int, default=0, help="Max iterations (0 = unlimited).")
    parser.add_argument("--use-paddle", action="store_true", help="Use real OCR (RapidOCR; default: noop). 旧名保留兼容 web UI。")
    parser.add_argument("--ocr-engine", choices=("auto", "gpu", "cpu"), default="auto", help="OCR engine: auto (default, GPU 优先回退 CPU) / gpu (强制 GPU) / cpu (强制 CPU).")
    parser.add_argument("--blue-mode", action="store_true", help="Blue-button detection only (no OCR at all).")
    parser.add_argument("--hybrid-mode", action="store_true", help="Blue-button classification + OCR payload reading.")
    parser.add_argument("--list-windows", action="store_true", help="List windows and exit.")
    parser.add_argument("--verbose", action="store_true", help="Print OCR/color results for each region.")
    parser.add_argument("--debug", action="store_true", help="调试模式：每帧详细日志(识别payload+决策)。正常模式不加载该日志系统，零开销。")
    parser.add_argument("--character", default=None, help="Desired character name (Chinese), e.g. 克莱儿.")
    parser.add_argument(
        "--variant",
        default="",
        help="角色形态(同名多形态时区分): 留空=普通, ANOTHER=第二形态, COSMIC=系列。例: --variant COSMIC (罗莎莉亚).",
    )
    parser.add_argument(
        "--build-profile",
        default="balanced",
        help="Build profile: balanced, power_focus, focus_focus, durability_focus, stamina_tank, protection_focus.",
    )
    args = parser.parse_args()

    if args.list_windows:
        _print_windows()
        return

    # Find window first
    window = _find_or_exit(args.window_title)
    base_profile = load_region_profile(args.profile)
    profile = base_profile
    policy = TrainerPolicy()
    training_inspector = TrainingInspector(max_fail_rate=policy.config.max_training_fail_rate)
    shop_inspector = ShopInspector()
    commission_inspector = CommissionInspector()
    skill_inspector = SkillInspector()
    state = GameState(desired_character=args.character, desired_variant=args.variant, build_profile=args.build_profile)
    # 启动时按 desired_character 查 config/characters.json 填入 character_class
    # (刺客/术师/游侠/突击者/辅助/坦克), 供 decide_relic 选属性优先级组用。
    # 不存在/未指定角色 → character_class=None → decide_relic 默认 ATTACK 组。
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
    print(f"character_class={state.character_class or '(unknown)'}")
    round_tracker = RoundTracker()
    executor = PyAutoGuiExecutor() if args.execute else DryRunExecutor()
    # --debug 模式才加载详细日志系统（正常模式不 import，零开销）。详见 debug_log.py。
    debug_log = None
    if args.debug:
        from starsavior_trainer import debug_log as _debug_log
        debug_log = _debug_log
        print("[调试模式] 每帧详细日志已启用（识别 payload + 决策 Action）")
    ocr = _create_ocr(args.use_paddle, args.ocr_engine)
    blue_detector = BlueButtonDetector() if (args.blue_mode or args.hybrid_mode) else None

    if args.hybrid_mode:
        mode_label = "hybrid"
        args.use_paddle = True  # Hybrid mode needs real OCR
        ocr = _create_ocr(True, args.ocr_engine)
    elif args.blue_mode:
        mode_label = "blue-button"
    elif args.use_paddle:
        mode_label = "rapid"
    else:
        mode_label = "noop"
    print(f"profile={base_profile.name} resolution={base_profile.resolution[0]}x{base_profile.resolution[1]} regions={len(base_profile.regions)}")
    print(f"mode={mode_label} execute={'yes' if args.execute else 'dry-run'}")
    print(f"character={args.character or '(auto)'} build_profile={args.build_profile}")
    print("build=journey-visual-guard-20260520a")
    print(f"game window: {window.title} ({window.rect.width}x{window.rect.height})")

    # F9 pause hotkey: lets the operator stop the bot's actions mid-run and
    # reclaim control without killing the process. Falls back gracefully (warns
    # and runs unpaused) if the hotkey can't be registered. (F12 is avoided — it's
    # Steam's screenshot key and gets swallowed before our hook sees it.)
    pause = PauseController()
    install_pause_hotkey(pause, key="f11")

    iteration = 0
    consecutive_character_confirms = 0
    last_character_click_target = None
    consecutive_unknown = 0
    was_paused = False
    try:
        while args.max_iterations == 0 or iteration < args.max_iterations:
            # Mouse-corner emergency stop, checked FIRST every iteration. The most
            # reliable "reclaim control" path: move the mouse into any screen
            # corner and the bot exits cleanly. Beats both the keyboard hotkey
            # (swallowed by a focused admin/Steam window) and pyautogui's
            # exact-pixel FAILSAFE (needs a precise landing pixel at the exact
            # moment pyautogui is called) — this polls a whole corner region at
            # the top of the loop, independent of focus/privilege/timing.
            if args.execute and _mouse_at_screen_corner():
                print("\n[急停] 鼠标移到屏幕角落，已停止 bot，控制权交还。")
                return
            # While paused, do nothing but idle: no capture, no decision, no
            # click. Print once per second so it's clear the bot is waiting.
            if pause.paused:
                was_paused = True
                print("已暂停，按F9继续")
                time.sleep(1.0)
                continue
            if was_paused:
                print("已恢复")
                was_paused = False

            iteration += 1

            # Capture via PrintWindow (inside capture_window): works even when the
            # game is covered/unfocused, so we no longer hide the console or steal
            # the focus just to grab a frame (dry-run is fully non-invasive now).
            screenshot, client_window = capture_window(args.window_title)
            profile = scale_region_profile(base_profile, screenshot.size)
            reader = RegionOcrReader(profile, ocr)

            print(f"\n--- iteration {iteration} ---")

            # Classify screen
            if args.hybrid_mode:
                observation = classify_hybrid(screenshot, profile, reader)
            elif args.blue_mode:
                observation = classify_by_blue_button(screenshot, profile)
            elif args.use_paddle:
                # Default with real OCR: use hybrid (OCR + visual). Pure
                # classify_by_ocr CANNOT tell apart the journey-origin screens that
                # share the "旅程起点" title — character_select / blessing_setup /
                # journey_start — and always resolves to character_select. That made
                # the bot treat the blessing-setup screen as character select and
                # scroll forever looking for the runner (the "stuck on blessing"
                # freeze). Hybrid disambiguates them by visual content.
                observation = classify_hybrid(screenshot, profile, reader)
            else:
                observation = classify_by_ocr(screenshot, profile, reader)

            logger.info(f"classified screen={observation.screen.value} confidence={observation.confidence:.2f}")
            narrate(f"[识别] 画面={observation.screen.value} 置信度={observation.confidence:.2f}")
            if observation.screen in (Screen.CHARACTER_SELECT, Screen.BLESSING_SETUP):
                character_score, blessing_score = journey_origin_visual_scores(screenshot, profile)
                visual_screen = classify_journey_origin_by_visual(screenshot, profile)
                print(
                    "  journey_visual="
                    f"{visual_screen.value if visual_screen else 'unknown'} "
                    f"character_score={character_score:.2f} blessing_score={blessing_score:.2f}"
                )

            if observation.screen == Screen.UNKNOWN:
                # §22.11 回合数兜底: 第15/30回合(N/45)必定是地区移动。UNKNOWN 时若回合数
                # 命中 region_move_rounds, 尝试 parse_region_move —— 成功则按 REGION_MOVE 决策,
                # 避免 region_move 分类失败时误点中心推进(错过地区移动)。
                # 架构合规: 不在 classifier 强制分类(OCR 只产 Observation), 在 live_loop 用
                # 回合数+region 信息兜底(同 GOAL_DIALOG 回合校准模式)。
                if state.current_round in policy.config.region_move_rounds:
                    from starsavior_trainer.screens.region_move import parse_region_move
                    region_texts = reader.read_prefixes(
                        screenshot,
                        ("region_move_anchor_title", "region_move_station_title",
                         "region_move_destination_1", "region_move_destination_1_name",
                         "region_move_destination_2", "region_move_destination_2_name",
                         "region_move_go_button"),
                    )
                    region_payload = parse_region_move(region_texts, profile)
                    if region_payload is not None and region_payload.is_region_move:
                        observation = Observation(
                            screen=Screen.REGION_MOVE,
                            confidence=0.7,
                            payload=region_payload,
                        )
                        print(f"  [回合兜底] 第{state.current_round}回合 UNKNOWN → 强制 REGION_MOVE")
                    else:
                        unknown_path = Path("screenshots/live_unknown_latest.png")
                        save_image(screenshot, unknown_path)
                        consecutive_unknown += 1
                        print(f"  [回合兜底] 第{state.current_round}回合但非 region_move, 按 UNKNOWN 处理")
                else:
                    unknown_path = Path("screenshots/live_unknown_latest.png")
                    save_image(screenshot, unknown_path)
                    consecutive_unknown += 1
                # Most unknown frames are transition/display screens (loading splash,
                # reward display, dialogue) that either auto-advance or just need a
                # click to continue. Click the screen centre to push through; only
                # pause once it persists, so we never click blindly forever.
                if args.execute and consecutive_unknown <= 4:
                    activate_window(client_window.hwnd)
                    cx = client_window.rect.x + client_window.rect.width // 2
                    cy = client_window.rect.y + client_window.rect.height // 2
                    executor.execute(Action("click", Rect(cx, cy, 1, 1), "unknown: click centre to advance"))
                    print(f"  unknown screen, click centre to advance ({consecutive_unknown})")
                else:
                    print(f"  unknown screen, pausing (consecutive={consecutive_unknown})")
                time.sleep(args.interval)
                continue
            consecutive_unknown = 0

            # Parse payload
            if args.blue_mode:
                payload = _read_screen_payload_blue(observation.screen, screenshot, profile, blue_detector, args.verbose)
            elif args.hybrid_mode:
                payload = _read_screen_payload_ocr(observation.screen, screenshot, profile, reader, args.verbose)
            else:
                payload = _read_screen_payload_ocr(observation.screen, screenshot, profile, reader, args.verbose)

            if payload is not None:
                observation = Observation(screen=observation.screen, confidence=observation.confidence, payload=payload)
                if isinstance(payload, BlessingChoice):
                    print(
                        "  blessing_options="
                        + ", ".join(
                            f"{option.name}:value={option.value}:sub={option.sub_blessing_count}"
                            for option in payload.options
                        )
                        + f" detail_sub={payload.detail_sub_blessing_count}"
                    )
            elif args.verbose:
                print("  (no payload parsed)")

            # Diagnostic: the intro_story skip target (top-right) can collide with a
            # HUD screen's menu button — save the frame whenever we classify
            # intro_story so a mis-classified HUD-dialogue can be inspected offline.
            if observation.screen == Screen.DIALOGUE and getattr(observation.payload, "variant", "") == "intro_story":
                save_image(screenshot, Path("screenshots/live_intro_story_latest.png"))

            # Round tracking: the hub shows no turn counter, only a date — count
            # date changes as rounds (drives the early-game training bias). Reset
            # when a new journey is being set up (initial / character select).
            if observation.screen in (Screen.INITIAL, Screen.CHARACTER_SELECT):
                round_tracker.reset()
                policy._needs_goal_round = True  # §22.9 旅程首次必读 N/45 校准
                policy._skill_done = False  # §22.13 新旅程 → 重置潜质学习标志
            if observation.screen == Screen.TRAINING_HUB and isinstance(observation.payload, TrainingHubStatus):
                prev_round = round_tracker.current_round
                round_tracker.observe_date(observation.payload.turn_label)
                # §22.9: 日期变化(回合+1)→ 标记需要读目标弹窗 N/45 校准(日期计数不准)。
                if round_tracker.current_round != prev_round:
                    policy._needs_goal_round = True
                    policy._skill_done = False  # §22.13 新回合 → 可再学潜质(重置防死循环标志)
                # 从大厅 "RANK 21" 读角色综合等级 → 委托选阶用(选建议等级≤它的最高阶)。
                rank_num = parse_first_int(observation.payload.rank_label or "")
                if rank_num is not None:
                    state = replace(state, character_rank=rank_num)
            # §22.9: 目标弹窗 → 读 N/45 用绝对回合数校准 round_tracker(比日期计数准)。
            if (
                observation.screen == Screen.GOAL_DIALOG
                and isinstance(observation.payload, GoalDialogStatus)
                and observation.payload.round is not None
            ):
                round_tracker.set_round(observation.payload.round)
                print(f"  [回合校准] 目标弹窗 N/45={observation.payload.round}")
            state = replace(state, current_round=round_tracker.current_round)
            print(f"  current_round={round_tracker.current_round}")
            if debug_log:
                debug_log.dump_observation(observation)

            # Decide
            action = None
            # BLESSING_CHOICE goes through the policy (decide_blessing_choice): pick the
            # highest-value blessing, same-value → topmost, two-step confirm. The old
            # click-to-read-sub inspector looped in-game (sub count flickers, candidate
            # list OCR jitters), so it's retired — see 协作守则 / commit.
            # Training: heads are random each turn, so inspect 力量/体力/韧性 (click
            # each to reveal its +N gain) and pick whichever gives the most — a
            # fixed bias can't know this turn's best. Mirrors the blessing inspector.
            if observation.screen == Screen.TRAINING_SELECT and _is_iterable_of(observation.payload, TrainingChoice):
                action = training_inspector.decide(observation.payload, state, image=screenshot, policy=policy)
                if action is not None:
                    print(f"  training_inspector_records={training_inspector.records} pending={training_inspector.pending}")
            elif observation.screen != Screen.TRAINING_SELECT:
                training_inspector.reset()
            # Journey Trading: item effects only show when an item is selected, so
            # the inspector clicks each row to read its effect, then buys by effect
            # (回体力/潜质点退还) — mirrors the training inspector.
            if observation.screen == Screen.SHOP and isinstance(observation.payload, ShopScene):
                action = shop_inspector.decide(observation.payload, policy, image=screenshot)
                if action is not None:
                    print(
                        f"  shop_inspector effects={shop_inspector.effects} "
                        f"pending={shop_inspector.pending_index} bought={shop_inspector.bought_effects} "
                        f"selected_effect={observation.payload.selected_effect!r}"
                    )
            elif observation.screen != Screen.SHOP:
                shop_inspector.reset()
            # §22.13 Skill select: SkillInspector 接管(扫库→贪心→习得循环)。
            # 自己 OCR 识别潜质行(状态标签锚点), 不走 parse_skill_select。
            if observation.screen == Screen.SKILL_SELECT:
                # 读潜质点数(skill_select_potential_points region)
                pp_rect = profile.regions.get("skill_select_potential_points")
                potential_points = None
                if pp_rect is not None:
                    pp_rt = reader.read_names(screenshot, ("skill_select_potential_points",))
                    if pp_rt:
                        potential_points = parse_first_int(pp_rt[0].text)
                close_btn = profile.regions.get("skill_select_close_button")

                def _read_skill_rows_live():
                    """读当前帧可见潜质行 → [(name, price, status, target, y), ...]

                    target 用行 name_cy 匹配最接近的 skill_select_option_N_button region。
                    """
                    from starsavior_trainer import skill_reader
                    lines = skill_reader.read_skill_lines(screenshot, reader.ocr)
                    out = []
                    for ln in lines:
                        # target: 直接用 OCR 检测到的"习得/升级"按钮 bbox(准确),
                        # 不再用 option_N_button region 匹配(后者 x 偏右会点错位置)。
                        target = None
                        if ln.button_rect is not None:
                            x1, y1, x2, y2 = ln.button_rect
                            target = Rect(x1, y1, x2 - x1, y2 - y1)
                        out.append((ln.name, ln.price, ln.status, target, ln.name_cy, ln.level))
                    return out

                def _scroll_skill():
                    """上滑看下方潜质"""
                    from starsavior_trainer import skill_reader
                    skill_reader.drag_scroll_up()

                action = skill_inspector.decide(
                    potential_points, policy,
                    read_rows=_read_skill_rows_live, scroll=_scroll_skill,
                    close_button=close_btn,
                )
                if action is not None:
                    print(f"  skill_inspector phase={skill_inspector._phase} learned={skill_inspector.learned} points={potential_points}")
            elif observation.screen != Screen.SKILL_SELECT:
                skill_inspector.reset()
            # Commission: the list shows only tier names; the suggested rank shows
            # only in the detail once a commission is selected, so inspect each by
            # clicking it, read its 建议综合等级, then accept the highest tier whose
            # suggested rank ≤ character rank. Mirrors the training inspector. Falls
            # back to the policy (returns None) when the character rank is unknown.
            if observation.screen == Screen.COMMISSION_SELECT and isinstance(observation.payload, CommissionChoice):
                action = commission_inspector.decide(observation.payload, state)
                if action is not None:
                    print(
                        f"  commission_inspector_records={commission_inspector.records} "
                        f"pending={commission_inspector.pending} "
                        f"char_rank={observation.payload.character_rank} "
                        f"suggested={observation.payload.selected_suggested_rank}"
                    )
            elif observation.screen != Screen.COMMISSION_SELECT:
                commission_inspector.reset()
            if action is None:
                action = policy.decide(state, observation)
            if observation.screen == Screen.CHARACTER_SELECT and action.kind == "click":
                character_path = Path("screenshots/live_character_select_latest.png")
                save_image(screenshot, character_path)
                # Only a *repeated identical* click means we're genuinely stuck.
                # The normal flow clicks two different targets — select the
                # character row, then the 选择 confirm button — which is progress,
                # not a loop, so it must not be blocked.
                if action.target == last_character_click_target:
                    consecutive_character_confirms += 1
                else:
                    consecutive_character_confirms = 1
                    last_character_click_target = action.target
                if consecutive_character_confirms >= 3:
                    action = Action("pause", None, f"repeated identical character click blocked, saved {character_path}")
            else:
                consecutive_character_confirms = 0
                last_character_click_target = None
            logger.info(f"decision: {action.kind} target={action.target} reason={action.reason}")
            narrate(f"[决策] {action.kind} → {action.target} | 理由: {action.reason}")
            if debug_log:
                debug_log.dump_decision(action)
            screen_action = map_action_to_rect(action, screenshot.size, client_window.rect)
            if action.target is not None:
                print(f"  screen_target={screen_action.target}")

            # Execute. Activate the game first so the synthetic click/scroll lands
            # on it: Unity ignores input while inactive, and the mouse-wheel message
            # is routed to the focused window. Only when actually executing, so
            # dry-run / diagnosis stays non-invasive.
            if args.execute and action.kind in ("click", "move", "scroll"):
                # Emergency stop, checked AGAIN right before we move the mouse: the
                # top-of-loop check can be "beaten" because execute's moveTo yanks
                # the cursor back to a game target, so a corner-slam during the
                # (multi-second) OCR phase would be overwritten before the next
                # top check sees it. Checking here — the last moment before we grab
                # the mouse — catches a corner-slam from any point in the iteration.
                if _mouse_at_screen_corner():
                    print("\n[急停] 鼠标移到屏幕角落，已停止 bot，控制权交还。")
                    return
                activate_window(client_window.hwnd)
            result = executor.execute(screen_action)
            logger.info(f"executed: {result.kind} point={result.point} executed={result.executed}")
            narrate(f"[执行] {result.kind} @ {result.point} ({'真点' if result.executed else 'dry-run'})")

            # Advance screens (reward / dialogue / post-training) re-capture fast so
            # we don't crawl one click per --interval through them.
            if observation.screen in _ADVANCE_SCREENS:
                time.sleep(_ADVANCE_SLEEP)
            elif observation.screen == Screen.TRAINING_SELECT:
                time.sleep(min(_TRAINING_SELECT_SLEEP, args.interval))
            else:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nstopped by user")
    except RuntimeError as exc:
        print(f"\nerror: {exc}")
    except Exception as exc:
        # pyautogui FAILSAFE: operator slammed the mouse into a screen corner to
        # abort. This is the reliable "reclaim control" path (the keyboard hotkey
        # can be swallowed by a focused admin/Steam window). Exit cleanly instead
        # of dumping a traceback.
        if type(exc).__name__ == "FailSafeException":
            print("\n[FAILSAFE] 鼠标移到屏幕角落，已紧急停止 bot。控制权交还。")
            return
        raise


if __name__ == "__main__":
    main()
