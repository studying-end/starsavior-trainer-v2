"""采集训练选择画面中支援卡人头模板。

从头像面板 (training_select_heads_panel) 的固定槽位裁剪头像 → 与现有模板库
去重 → 保存新头像至 config/assets/（新库命名 N.png，不含进度条）。

== 头像位置原理（实机标定 2026-07-03）==
头像不在训练卡 (training_select_card_*) 上，而在画面顶部右侧的头像面板内。
面板内有若干**固定槽位**纵向排列（间距约 109px），每回合不同槽位填入不同角色
头像（阵容每回合变）。槽位几何（2560x1440 下，相对 heads_panel [1600,130,950,260]）：
  - x 偏移 ≈ 210（面板内），即全图 x≈1810
  - 首槽 y≈153（面板内 y≈23），槽间距 109
  - 头像尺寸 ≈ 111x113
采集即遍历这些槽位，裁出每个非空槽的头像，去重后入库。不依赖任何参考图——
槽位是固定 UI 几何，去重靠与现有模板 matchTemplate。
裁剪窗口高度 93px（排除下方羁绊进度条，原 113px 含进度条会导致模板随羁绊值变化而漂移）。

用法：
    python -m starsavior_trainer.tools.collect_head_templates --window-title "StarSavior"

    或者传入已有截图：
    python -m starsavior_trainer.tools.collect_head_templates --image screenshots/training_select.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image

# ── 项目模块 ──────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # tools/../.. = project root


def _import_project_modules():
    """Lazy import starsavior_trainer modules (after ensuring project root is on sys.path)."""
    import sys
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
    import starsavior_trainer.image_regions as ir
    import starsavior_trainer.regions as reg
    import starsavior_trainer.capture as cap
    return ir, reg, cap


def _is_new_library_template(path: Path) -> bool:
    """判断文件名是否为**作数**头像模板（纯数字 .png，如 1.png、10.png）。

    这些模板会被 count_heads 扫描计数。
    """
    return path.suffix == ".png" and path.stem.isdigit()


def _is_non_counting_template(path: Path) -> bool:
    """判断文件名是否为**不作数**头像模板（non_counting_head_N.png）。

    沿用旧库 non_counting_head_*.png 命名风格（旧库已有 1/2，新库从 3 开始）。
    count_heads 跳过这些模板（_is_head_template 仅匹配 ^\\d+\\.png$）；
    collect_head_templates 的 dedup 仍会扫描它们，避免同一颗不作数头反复入库。
    旧库 non_counting_head_1/2.png 是旧几何（113×113 含进度条），dedup 加载时
    因尺寸 > 新窗口 111×93 自动跳过；新库 non_counting_head_3+.png 是新几何（111×93）。
    """
    import re
    return bool(re.match(r"^non_counting_head_\d+\.png$", path.name))


def _is_dedup_template(path: Path) -> bool:
    """判断是否参与去重比对（作数 N.png + 不作数 non_counting_head_N.png）。

    dedup 同时扫这两种模板，避免同一颗头（无论作数/不作数）反复入库污染新库。
    旧库 counting_head_*.png 不参与（含进度条，几何不同）。
    """
    return _is_new_library_template(path) or _is_non_counting_template(path)


def _existing_template_ids(assets_dir: Path) -> set[int]:
    """返回新库模板文件的序号集合（纯数字 .png），如 {1, 2, 3}。"""
    ids: set[int] = set()
    for f in assets_dir.glob("*.png"):
        if _is_new_library_template(f):
            try:
                ids.add(int(f.stem))
            except ValueError:
                continue
    return ids


def _next_template_id(assets_dir: Path) -> int:
    """返回下一个可用的序号（新库纯数字命名）。"""
    ids = _existing_template_ids(assets_dir)
    return max(ids) + 1 if ids else 1


def _template_match_score(template: Image.Image, candidate: Image.Image) -> float:
    """用 OpenCV TM_CCOEFF_NORMED 比较两张图，返回最大匹配分。"""
    import cv2
    import numpy as np

    tpl = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2BGR)
    src = cv2.cvtColor(np.array(candidate.convert("RGB")), cv2.COLOR_RGB2BGR)

    # 如果模板比候选图大，缩放模板
    if tpl.shape[0] > src.shape[0] or tpl.shape[1] > src.shape[1]:
        return 0.0

    res = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
    return float(res.max())


def _is_duplicate(candidate: Image.Image, assets_dir: Path, threshold: float = 0.80) -> tuple[bool, str | None]:
    """检查 candidate 是否与 assets_dir 下某模板重复。

    返回 (是否重复, 匹配到的模板文件名或 None)。
    §22.26 阈值改 0.80（原 0.85 漏拦同脸 0.83（= count_heads 识别阈值）——原 0.93 严于识别阈值导致
    [0.85,0.93) 区间的"准重复"模板被入库，count_heads 用这些准重复模板匹配时
    也 >0.85 → 同一颗头被计多次。0.85 确保去重灵敏度 >= 识别灵敏度，不漏入库。
    比对**作数**模板（N.png）+ **不作数**模板（non_counting_head_N.png）——避免同一颗
    不作数头反复入库污染新库。旧库 counting_head_*.png 不参与（含进度条，几何不同）。
    旧库 non_counting_head_1/2.png（旧几何 113×113）会被加载，但因尺寸 > 候选 111×93
    在 _template_match_score 内自动跳过（返回 0.0）。
    """
    for f in sorted(assets_dir.glob("*.png")):
        if not _is_dedup_template(f):
            continue
        try:
            tpl = Image.open(f)
            score = _template_match_score(tpl, candidate)
            if score > threshold:
                return True, f.name
        except Exception:
            continue
    return False, None


# ── 头像列几何（相对 heads_panel，2560x1440 标定）────────────────────────
# 头像不在训练卡上，而在画面顶部右侧的头像面板内纵向排列成一条"头像列"。
# 列 x 固定（≈面板内 x=210），y 离散（每回合哪些槽位填头像、填什么角色都变，
# 故不能假设固定 y 槽位——必须沿列扫描）。几何按面板尺寸比例表达，分辨率变化
# 时随 panel_rect 缩放。标定基准：2560x1440 下 heads_panel=[1600,130,950,260]。
_HEAD_PANEL_BASE_W = 950
_HEAD_PANEL_BASE_H = 260
_HEAD_COL_X_FRAC = 210 / 950        # 头像列 x 占面板宽比例（→ 全图 x≈1810）
_HEAD_W_FRAC = 111 / 950            # 头像宽占面板宽比例
_HEAD_H_FRAC = 93 / 260             # 头像高占面板高比例（缩减以排除下方羁绊进度条，原 113/260）
_HEAD_EMPTY_STD = 40                # 窗口灰度 std 低于此值视为无头像（空槽/背景）。原 25 过低，远 panel 噪声区（std≈25）会误判为头像候选；提到 40 排除屏幕底部误识别
_HEAD_SLIDE_STEP = 5                # 沿列滑窗的 y 步长（px）
_HEAD_NMS_DY = 60                   # 相邻窗口 y 差小于此值合并为同一头像（NMS）


def _find_head_instances(image: Image.Image, panel_rect, assets_dir: Path,
                         match_threshold: float) -> list:
    """沿头像列扫描，返回精确定位的头像实例列表。

    头像列 x 固定、y 离散（每回合变），故用 111x93 窗口沿列滑动（步长 5），
    保留 std≥_HEAD_EMPTY_STD(40) 的窗口。对每个窗口计算两个分数：
      - loc_score: 与**所有模板（旧库+新库）**的最大匹配分，用于定位头像位置
        （旧库含进度条，但 matchTemplate 仍能定位头像大致位置，分数 0.5-0.9）
      - dedup_score: 与**作数 N.png + 不作数 non_counting_head_N.png**的最大匹配分，
        用于去重判断（避免同一颗头无论作数/不作数反复入库）
    在 loc_score 曲线上找**局部极大值**（间距 > _HEAD_NMS_DY）作为头像候选——
    这避免了"按相邻 y 差合并"的陷阱（滑窗步长 5 < NMS 阈值 60 会导致全列合并成 1 组）。
    每个候选的 dedup_score >= match_threshold 判为重复（跳过），否则为新头像。

    返回 [(slot_idx, Rect, is_dup, matched_file, dedup_score), ...]。
    """
    import cv2
    import numpy as np
    from starsavior_trainer.models import Rect

    win_w = max(round(_HEAD_W_FRAC * panel_rect.width), 1)
    win_h = max(round(_HEAD_H_FRAC * panel_rect.height), 1)
    col_x = panel_rect.x + round(_HEAD_COL_X_FRAC * panel_rect.width)
    y_start = panel_rect.y
    # §22.23 限制扫描范围到头像面板区域 + 余量，不扫全图。
    # 原全图扫描(y=130..1347)覆盖训练卡区域(y=338-1041)，训练卡 UI 元素 std>=40
    # 且 loc_score>0.3 → 误判为新头像入库（5张卡却入库10+个模板）。
    # 头像在面板 y=130-390 内，+100px 余量覆盖边缘，不扫到训练卡区域。
    y_end = min(panel_rect.y + panel_rect.height + 100, image.size[1] - win_h)

    # 预读模板：loc_templates 用于定位（旧库+新库），dedup_templates 用于去重（仅新库）
    loc_templates: list[tuple[str, object]] = []
    dedup_templates: list[tuple[str, object]] = []
    for f in sorted(assets_dir.glob("*.png")):
        try:
            tpl = cv2.imread(str(f), cv2.IMREAD_COLOR)
            if tpl is None or tpl.shape[0] > win_h or tpl.shape[1] > win_w:
                continue
            loc_templates.append((f.name, tpl))
            if _is_dedup_template(f):
                dedup_templates.append((f.name, tpl))
        except Exception:
            continue

    search = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    iw, ih = image.size
    # 沿列扫描，记录每个 y 的 loc_score 和 dedup_score
    windows: list[tuple[int, float, float, float, str]] = []  # (y, std, loc_score, dedup_score, dedup_name)
    y = y_start
    while y <= y_end:
        if col_x + win_w > iw or y + win_h > ih:
            break
        win = search[y:y + win_h, col_x:col_x + win_w]
        std = float(win.std())
        if std >= _HEAD_EMPTY_STD:
            # loc_score: 所有模板最大分（用于定位）
            loc_score = 0.0
            for _, tpl in loc_templates:
                mx = float(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED).max())
                if mx > loc_score:
                    loc_score = mx
            # dedup_score: 新库模板最大分（用于去重）
            dedup_score = 0.0
            dedup_name = ""
            for name, tpl in dedup_templates:
                mx = float(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED).max())
                if mx > dedup_score:
                    dedup_score = mx
                    dedup_name = name
            windows.append((y, std, loc_score, dedup_score, dedup_name))
        y += _HEAD_SLIDE_STEP

    # NMS: 在 loc_score 曲线上找局部极大值（间距 > _HEAD_NMS_DY）
    # 局部极大值 = loc_score 比前后窗口都高，且 > 0.6（§22.23 提高 0.3→0.6：
    # 0.3 太低，训练卡 UI 元素也能达到 → 误判为头像候选。真正头像 loc_score > 0.7）
    # 相邻峰值 y 差 <= _HEAD_NMS_DY 时保留更高分的（真正的 NMS）
    windows.sort()
    peaks: list[tuple[int, float, float, float, str]] = []
    for i, win in enumerate(windows):
        y, std, loc_score, dedup_score, dedup_name = win
        prev_loc = windows[i - 1][2] if i > 0 else -1.0
        next_loc = windows[i + 1][2] if i < len(windows) - 1 else -1.0
        if loc_score >= prev_loc and loc_score > next_loc and loc_score > 0.6:
            if not peaks or y - peaks[-1][0] > _HEAD_NMS_DY:
                peaks.append(win)
            elif loc_score > peaks[-1][2]:
                peaks[-1] = win  # 替换为更高分的窗口

    instances = []
    for slot_idx, (y, std, loc_score, dedup_score, dedup_name) in enumerate(peaks):
        rect = Rect(col_x, y, win_w, win_h)
        is_dup = dedup_score >= match_threshold
        instances.append((slot_idx, rect, is_dup, dedup_name if is_dup else None, dedup_score))
    return instances


def auto_collect_new_heads(image: Image.Image, panel_rect, match_threshold: float = 0.80) -> int:
    """自动采集新人头入库（live_loop 内调用）。

    沿头像列扫描，对未命中现有模板的新头像自动裁剪并保存为 config/assets/{N}.png。
    下一帧 count_heads 即生效（动态扫描模板目录）。

    Args:
        image: 训练选择画面截图（2560x1440）
        panel_rect: training_select_heads_panel 矩形
        match_threshold: 去重阈值（§22.26 改 0.80（<识别0.85），拦同脸 0.83（11.png=nc5 漏拦））

    Returns:
        新入库的头像数量
    """
    assets_dir = _PROJECT_ROOT / "config" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out_dir = _PROJECT_ROOT / "screenshots" / "head_crops"
    out_dir.mkdir(parents=True, exist_ok=True)

    instances = _find_head_instances(image, panel_rect, assets_dir, match_threshold)
    new_saved = 0
    for slot_idx, rect, is_dup, score, dedup_name in instances:
        if is_dup:
            continue
        from starsavior_trainer.image_regions import crop_region
        head_img = crop_region(image, rect)
        head_img.save(out_dir / f"slot{slot_idx}.png")
        next_id = _next_template_id(assets_dir)
        head_img.save(assets_dir / f"{next_id}.png")
        print(f"[自动入库] 新头像 #{next_id} 槽{slot_idx} y={rect.y}")
        new_saved += 1
    return new_saved


def main() -> None:
    parser = argparse.ArgumentParser(description="采集训练选择画面中的支援卡人头模板")
    parser.add_argument("--window-title", default="Star Savior",
                        help="游戏窗口标题（用于自动截图）")
    parser.add_argument("--image", help="已有的训练选择画面截图（如提供则跳过截图步骤）")
    parser.add_argument("--profile", default="config/regions/2560x1440.json",
                        help="区域配置 JSON 文件路径（相对于项目根）")
    parser.add_argument("--out-dir", default="screenshots/head_crops",
                        help="裁剪预览输出目录")
    parser.add_argument("--dry-run", action="store_true",
                        help="只裁剪预览不保存到模板库")
    parser.add_argument("--match-threshold", type=float, default=0.80,
                        help="去重模板匹配阈值（§22.26 改 0.80（<识别0.85），拦同脸 0.83）")
    parser.add_argument("--resize-crop", type=int, default=None,
                        help="裁剪后统一缩放到此尺寸（如 64，可选）")
    args = parser.parse_args()

    # ── 加载项目模块 ──
    ir, reg, cap = _import_project_modules()

    # ── 获取截图 ──
    if args.image:
        print(f"[采集] 使用已有截图: {args.image}")
        screenshot = Image.open(args.image)
    else:
        print(f"[采集] 正在截取游戏窗口 (标题包含: {args.window_title!r})...")
        screenshot, winfo = cap.capture_window(args.window_title)
        print(f"[采集] 截图成功: 窗口={winfo.title!r} {screenshot.size}")

    # ── 加载区域配置 ──
    profile_path = _PROJECT_ROOT / args.profile
    print(f"[采集] 加载区域配置: {profile_path}")
    profile = reg.load_region_profile(str(profile_path))
    profile = reg.scale_region_profile(profile, screenshot.size)
    print(f"[采集] 区域配置: {profile.name} {profile.resolution}, "
          f"实际截图尺寸: {screenshot.size}")

    # ── 头像面板 ──
    panel_rect = profile.regions.get("training_select_heads_panel")
    if panel_rect is None:
        raise RuntimeError(
            "区域配置缺少 training_select_heads_panel —— 无法定位头像面板。"
            " 确认画面是训练选择且区域配置含此 key。"
        )
    print(f"[采集] 头像面板: x={panel_rect.x} y={panel_rect.y} "
          f"w={panel_rect.width} h={panel_rect.height}")

    # ── 准备输出目录（裁剪预览） ──
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 准备模板库目录 ──
    assets_dir = _PROJECT_ROOT / "config" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # ── 沿头像列扫描实例 ──
    print(f"\n[采集] 开始扫描头像列 (x≈{panel_rect.x + round(_HEAD_COL_X_FRAC * panel_rect.width)})...")
    instances = _find_head_instances(screenshot, panel_rect, assets_dir, args.match_threshold)
    print(f"[采集] 发现 {len(instances)} 个头像实例")

    new_saved = 0
    skipped_dup = 0

    for slot_idx, rect, is_dup, matched_file, score in instances:
        # 1. 裁出头像（位置已由滑窗精确定位）
        head_img = ir.crop_region(screenshot, rect)

        # 2. 已知头像（去重命中）→ 跳过
        if is_dup:
            print(f"  [跳过] 槽{slot_idx} y={rect.y}: 已知头像 ({matched_file}, {score:.2f})")
            skipped_dup += 1
            continue

        # 3. 可选统一缩放
        if args.resize_crop:
            head_img = head_img.resize((args.resize_crop, args.resize_crop), Image.LANCZOS)

        # 4. 保存裁剪预览
        preview_path = out_dir / f"slot{slot_idx}.png"
        head_img.save(preview_path)

        # 5. 保存新模板（去重已在 _find_head_instances 内判定，此处为最终入库）
        if args.dry_run:
            print(f"  [预览] 槽{slot_idx} y={rect.y}: 新头像 (dry-run, 不保存) → {preview_path}")
            continue

        next_id = _next_template_id(assets_dir)
        save_path = assets_dir / f"{next_id}.png"
        head_img.save(save_path)
        print(f"  [保存] 槽{slot_idx} y={rect.y}: 新头像 #{next_id} → {save_path}")
        new_saved += 1

    # ── 汇总 ──
    print(f"\n[采集] 完成!")
    print(f"  现有模板: {len([f for f in assets_dir.glob('*.png') if _is_new_library_template(f)])} 个新库头像")
    print(f"  本次新增: {new_saved}")
    print(f"  跳过(重复): {skipped_dup}")
    print(f"  裁剪预览: {out_dir.resolve()}")
    if new_saved > 0:
        print(f"  提示: 新模板下一帧即生效 (count_heads 运行时动态扫描模板目录, 无需重启)")


if __name__ == "__main__":
    main()
