# Star Savior Trainer v2 — Code Wiki

> 训练自动化脚本（重构版），从 `d:/chengfeng` 重构而来。同游戏同功能，新架构契约。
> 当前阶段：迁移进度 17/18（131 测试全过）；pending T18 单测迁移 + 实跑验证。
> 本文档基于 2026-07-04 时的代码状态整理，作为代码导览/接手参考。**契约依据以 [CLAUDE.md](../CLAUDE.md) + [docs/设计方案.md](设计方案.md) 为准。**

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 整体架构](#2-整体架构)
- [3. 目录结构](#3-目录结构)
- [4. 主要模块职责](#4-主要模块职责)
- [5. 关键类与函数说明](#5-关键类与函数说明)
- [6. 依赖关系](#6-依赖关系)
- [7. 项目运行方式](#7-项目运行方式)
- [8. 核心数据流（live_loop 12 步）](#8-核心数据流live_loop-12-步)
- [9. 历史坑与规避索引](#9-历史坑与规避索引)
- [10. 扩展指引](#10-扩展指引)

---

## 1. 项目概述

### 1.1 项目本质

`Star Savior Trainer v2` 是一款针对 Unity 硬件加速窗口的**单屏状态机式训练自动化脚本**。每帧识别当前画面类别，只跑匹配该画面的策略，绝不在错误画面点"看似合理"的按钮。

**重构动机**：旧项目 `d:/chengfeng` 单文件臃肿（`screen_reader.py` 1557 行、`policy.py` 828 行），39 个历史坑反复重踩。v2 做架构化拆分 + 契约化约束，使识别层与决策层物理隔离。

### 1.2 三大不可违背契约

| # | 契约 | 含义 |
|---|------|------|
| 1 | **单屏状态机** | 每帧识别当前画面类别，只跑匹配该画面的策略；绝不在错误画面点"看似合理"的按钮 |
| 2 | **OCR/CV 只产生 Observation，绝不直接决定 Action** | 识别层（classifier/screen_reader）与决策层（policy）解耦 |
| 3 | **screens 注册表是唯一调度枢纽** | 分类、决策、payload 读取三处统一走 `screens.HANDLERS`，加画面只动一处 |

### 1.3 技术栈

- **桌面自动化**：pyautogui 0.9.54 + ctypes（Windows 窗口/输入）
- **OCR**：RapidOCR 1.4.4（ONNX Runtime GPU 1.27.0，PP-OCRv4 模型）—— 替换自原 PaddleOCR+paddlepaddle-gpu（废弃理由：2.7.3 乱码 / 3.x 撞 beta PIR 崩溃，详见 [设计方案.md §10](设计方案.md)）
- **计算机视觉**：OpenCV 4.5.5.64 + Pillow + numpy（>=1.21.2,<2.0.0）
- **Web UI**：Flask 3.0.0 + flask-cors 4.0.0
- **热键**：keyboard
- **GPU 依赖**：nvidia-cudnn-cu13 / nvidia-cublas-cu13 / nvidia-cuda-nvrtc-cu13（RapidOCR CUDA 后端）

### 1.4 目标平台

- Windows + 系统缩放 100%（DPI 感知强制设为 `SetProcessDpiAwareness(2)`）
- 游戏窗口分辨率 2560×1440（capture 时强制 scale）
- Python 3.10+

---

## 2. 整体架构

### 2.1 分层架构图

```
┌───────────────────────────────────────────────────────────────────┐
│                            入口层                                  │
│   ┌───────────────────┐    ┌───────────────────┐                 │
│   │   cli/live_loop   │    │    web/app.py     │                 │
│   │  (主循环 CLI)      │    │   (Flask UI)      │                 │
│   └─────────┬─────────┘    └─────────┬─────────┘                 │
│             │                        │                            │
│             ▼                        ▼                            │
│   ┌──────────────────────────────────────────────┐                │
│   │            web/process_manager               │                │
│   │          (子进程单例 + 日志队列)              │                │
│   └──────────────────────┬───────────────────────┘                │
└──────────────────────────┼────────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────────┐
│                          主循环层                                  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│  │ cli/pause   │ │cli/blue_parsers│ │ cli/runtime  │ │round_trkr│ │
│  │ (F11 暂停)  │ │ (payload 路由) │ │ (ocr/窗口工具)│ │(回合追踪)│ │
│  └─────────────┘ └──────────────┘ └──────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────────┐
│                       状态机决策层                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              screens/HANDLERS (21 画面注册表)               │  │
│  │   DelegatingScreenHandler(screen, decide_fn, parse_fn)     │  │
│  └────────────┬──────────────────────────────────┬───────────┘  │
│               │                                  │              │
│      ┌────────▼─────────┐              ┌─────────▼─────────┐    │
│      │  policy/engine   │◄────────────│ inspectors/* (4)   │    │
│      │ (+ 7 Mixin)      │  调用 inspector  │              │    │
│      └────────┬─────────┘              └────────────────────┘    │
└───────────────┼─────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────┐
│                         视觉识别层                                 │
│ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐  │
│ │  capture     │ │    ocr       │ │   vision    │ │ocr_reader│  │
│ │(PrintWindow) │ │(RapidOcrEng) │ │(蓝键/红字/   │ │(区域→文本│  │
│ │              │ │              │ │ 模板匹配)    │ │ 批量化)  │  │
│ └──────────────┘ └──────────────┘ └─────────────┘ └──────────┘  │
│ ┌──────────────────┐ ┌───────────────────────────────────────┐  │
│ │ classifier (3 文件)│ │   screens/* (21 parser)               │  │
│ │ hybrid 分类器     │ │   parse_X(payload 从图像/OCR 抽取)     │  │
│ └──────────────────┘ └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────┐
│                          执行层                                    │
│   ┌──────────────────────────────────────────────────┐            │
│   │  executor (PyAutoGuiExecutor / DryRunExecutor)  │            │
│   │  mouse_event hover/drag + 4 角急停              │            │
│   └──────────────────────────────────────────────────┘            │
└───────────────────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────┐
│                          数据层                                    │
│  models.py (Screen/Rect/Action/各 payload/GameState/Observation)  │
│  regions.py / text_constants.py / fixtures.py / manifest.py       │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 三层解耦的核心思想

```
识别层（classifier / screens parser）
        │ 只产出 Observation
        ▼
决策层（policy / inspectors）
        │ 只产出 Action
        ▼
执行层（executor）
        │ 真实副作用
        ▼
       游戏
```

**OCR/CV 永远不直接决定 Action。** classifier 给出 `Screen`，parser 给出 `payload`，policy 拿 payload 算分后给出 `Action`，executor 执行。任一环节出错都只在自身层修复。

---

## 3. 目录结构

```
d:\starsavior-trainer-v2\
├── CLAUDE.md                        # 项目契约 + 行为准则
├── requirements.txt
├── pyproject.toml / setup.py
├── docs/                            # 设计文档
│   ├── 迁移交接.md                  # ★ 新会话接手先读
│   ├── 新项目技术设计.md            # 架构/数据流/模块接口
│   ├── 设计方案.md                  # 13 § 非 1:1 迁移改动理由
│   ├── 变更记录.md                   # 时间线改动记录
│   ├── 现有项目架构分析.md          # 旧项目拆分方案
│   ├── 现有项目历史坑台账.md        # 39 坑 A-G 类
│   ├── 头像采集流程.md
│   └── Code-Wiki.md                 # 本文档
├── tests/                           # 131 测试
├── config/
│   └── assets/
│       ├── N.png                    # 作数头像模板（新库，纯数字命名，由 collect_head_templates 生成）
│       ├── counting_head_*.png      # 作数头像模板（旧库，含进度条，几何 113×113，仅参与定位不参与 dedup）
│       ├── non_counting_head_*.png  # 不作数头像模板（旧库 1/2 + 新库 3+，参与 dedup 不参与 count_heads 计数）
│       └── characters.json          # 角色名变体映射
├── region_profiles/                 # 区域坐标 YAML
├── logs/                            # 行为日志 + 普通日志
└── starsavior_trainer/              # ★ 主包
    ├── __init__.py
    ├── models.py                    # Screen 枚举 + Rect/Action/payload/GameState
    ├── regions.py                   # RegionProfile + scale
    ├── capture.py                   # PrintWindow 抓图
    ├── ocr.py                       # RapidOcrEngine
    ├── ocr_reader.py                # RegionOcrReader（区域→文本批量化）
    ├── vision.py                    # 颜色/蓝键/红字/模板匹配
    ├── classifier.py                # classify_hybrid 主入口
    ├── classifier_anchors.py        # anchor 区域 + _match_screen
    ├── classifier_signatures.py     # 14 个 _has_X_signature 消歧
    ├── executor.py                  # PyAutoGuiExecutor + 4 角急停
    ├── round_tracker.py             # 回合追踪
    ├── text_utils.py                # OCR 数字解析容错
    ├── text_constants.py            # 别名表
    ├── behavior.py                  # narrate() 中文行为日志
    ├── logging_setup.py             # 日志配置
    ├── manifest.py                  # 离线测试 manifest 加载
    ├── image_regions.py             # crop/draw/overlay
    ├── fixtures.py                  # demo_state / demo_observations
    ├── screens/                     # ★ 21 parser + HANDLERS 注册表
    │   ├── __init__.py              # HANDLERS + 21 _decide_X
    │   ├── base.py                  # ScreenHandler Protocol + DelegatingScreenHandler
    │   ├── training.py              # training_hub / training_select
    │   ├── simple.py                 # journey_start/dialogue/skill_select/...
    │   ├── blessing.py               # blessing_setup / blessing_choice
    │   ├── character_select.py
    │   ├── relic.py
    │   ├── rest.py
    │   ├── shop.py
    │   ├── commission.py
    │   ├── event.py
    │   ├── battle.py
    │   └── region_move.py
    ├── policy/                      # 决策层
    │   ├── engine.py                # ★ TrainerPolicy + decide 分发
    │   ├── config.py                # PolicyConfig + 按钮坐标
    │   ├── character_select.py      # CharacterSelectMixin
    │   ├── simple.py                # SimpleMixin
    │   ├── training.py               # TrainingMixin
    │   ├── blessing.py              # BlessingMixin
    │   ├── event.py                 # EventMixin
    │   ├── relic_commission.py      # RelicCommissionMixin
    │   ├── shop_skill.py            # ShopSkillMixin
    │   └── event_db.py              # 事件关键词数据库
    ├── inspectors/                  # 多帧点击收集信息再决策
    │   ├── training_inspector.py
    │   ├── commission_inspector.py
    │   ├── shop_inspector.py
    │   └── blessing_inspector.py
    ├── cli/                         # 命令行入口
    │   ├── live_loop.py             # ★ main 12 步主循环
    │   ├── pause.py                 # F11 暂停热键
    │   ├── runtime.py               # ocr/窗口/4 角急停工具
    │   ├── blue_parsers.py          # _read_screen_payload_* 路由
    │   └── offline_harness.py       # 离线测试入口
    └── web/                         # Flask Web UI
        ├── app.py                   # 17 路由
        └── process_manager.py       # 子进程单例
```

---

## 4. 主要模块职责

### 4.1 视觉识别层

#### `capture.py` — 窗口抓图

- `_set_dpi_awareness()`：模块加载时立即调 `SetProcessDpiAwareness(2)`，避免坐标系错乱
- `find_window(title_contains)`：`EnumWindows` 找游戏窗口，**标题最短优先**（避免匹配到日志子窗口）
- `activate_window(hwnd)`：`AttachThreadInput` 绕反偷焦
- `capture_window(title_contains, target_width=2560, target_height=1440)`：`PrintWindow` + `PW_RENDERFULLCONTENT=2` 抓 Unity 硬件加速窗口，缩放到固定分辨率

#### `ocr.py` — OCR 引擎封装

- `OcrEngine` Protocol：`read_text(img) -> str` / `read_lines(img) -> list[(text, bbox)]`
- `NoopOcrEngine`：测试用空实现
- `RapidOcrEngine`：模块级向 `PATH` 注入 `nvidia.cudnn` / `nvidia.cublas`；`use_cuda=True`，GPU 失败自动回退 CPU

#### `ocr_reader.py` — 区域→文本批量化（17 倍提速）

- `RegionText`：`name + text + rect`
- `_line_center_in_rect(line_bbox, rect)`：bbox 中心点是否落在区域内
- `RegionOcrReader`：**核心优化** —— `_lines` 全图 OCR 一次缓存，所有 `read_*` 共享这次结果，靠 bbox 中心点匹配各区域
- `read_all/read_names/read_prefixes/read_where/read_ocr_regions`：按 name/prefix 过滤的便捷查询

> **性能**：从逐区域 OCR（40s/帧）→ 全图 OCR + bbox 匹配（2.4s/帧），提速 17 倍。详见 [设计方案.md §13](设计方案.md)。

#### `vision.py` — CV 工具

- `RingColorDetector` / `BlueButtonDetector`：颜色掩码 + 轮廓检测
- 颜色阈值常量：`BLESSING_SLOT_FILLED_MEAN_MIN`、`BLESSING_SLOT_FILLED_RATIO_MIN` 等
- `is_blue_region(img)` / `is_blessing_slot_filled(img)` / `card_highlight_score(img)` / `bright_border_ratio(img)` / `detect_red_text(img)` / `detect_yellow_text(img)`
- `count_heads(img)`：**模板匹配法**（阈值 0.85，全图搜），用于支援卡作数头计数。**仅匹配新库 `N.png`**（`_is_head_template` 匹配 `^\d+\.png$`），自动跳过 `non_counting_head_*.png`（不作数不计数）。遗留 `counting_head_*.png` 含进度条几何不同不参与 dedup。裁剪不含进度条（`_HEAD_H_FRAC = 93/260`，111×93）。**双分数**：`loc_score`（所有模板含旧库，定位）+ `dedup_score`（仅新库 `N.png` + 新库 `non_counting_head_3+.png`，去重）。NMS 候选过滤：`_HEAD_EMPTY_STD = 40`（实测真头像 std 73-98，远 panel 噪声区 std≈25 会误判，提到 40 干净分离，见坑 #41）

#### `classifier*.py` — Hybrid 分类器（3 文件）

**入口：`classify_hybrid(reader, profile, image) -> Screen`**

```
classify_by_ocr (两遍加速)
   ├─ fast anchors (26 个)  → 命中即返回
   └─ 全量 anchor fallback
classify_by_blue_button (UNIQUE_BLUE_BUTTONS + _BOTTOM_RIGHT_BUTTONS + _SECONDARY_CHECK_REGIONS)
classify_hybrid = OCR 优先 + 蓝键 fallback + journey-origin visual 消歧 + BLESSING_CHOICE visual 消歧
```

- `classifier.py`：主入口 + `classify_by_ocr`（两遍加速）+ `classify_by_blue_button` + `classify_hybrid` + `_has_real_event_options`（坑 #2）+ `_looks_like_journey_start`（坑 #1）
- `classifier_anchors.py`：`ANCHOR_REGIONS_BY_SCREEN` / `ANCHOR_TEXT_BY_SCREEN`（21 画面）+ `_read_anchor_regions`（走 reader 缓存）+ `_match_screen` + `classify_by_filename`（离线）
- `classifier_signatures.py`：14 个 `_has_X_signature` 消歧函数（坑 A 类 1-11）+ `_region_content_density` + `classify_journey_origin_by_visual` + `journey_origin_visual_scores` + `_has_blessing_choice_visual_signature`

### 4.2 数据层

#### `models.py` — 全部数据模型

- `Screen`（Enum）：21 画面 + `UNKNOWN` + `REWARD` + `GAME_MENU`
- `Rect`（frozen dataclass）：`x1/y1/x2/y2 + .center` 属性
- `Action`（dataclass）：`kind/target/reason/confidence/scroll_clicks/repeat`
- payload 类：`TrainingChoice.fail_rate:int|None`（**None 表示未选中卡未知失败率，绝不当 0% 赌博**）/ `BlessingChoice` / `RelicChoice` / `CommissionChoice` / `ShopItem` / `EventOption` / `BattleScene` / `RestOption` 等
- `GameState`：跨帧状态（_pending_X / _needs_rest / _rest_for_mood 等）
- `Observation`：`screen + payload + image + frame_index`

#### `regions.py` — 区域配置

- `RegionProfile`：`regions: dict[str, Rect]`
- `load_region_profile(yaml_path)`
- `scale_region_profile(profile, scale_x, scale_y)`：**区域坐标只写一份**，运行时按目标分辨率缩放

#### `text_utils.py` — OCR 数字解析容错

- `normalize_ocr_text` / `contains_any_text` / `looks_like_ocr_region` / `extract_character_name`
- `parse_first_int(text)`：容错 `o→0 / l→1 / i→1 / s→5`
- `parse_rank_number(text)`：**不守卫相邻字母**（坑 #25：`RANK17A` 中的 `17A` 不被识别为 17）
- `_ocr_int_token_to_int(token)`：OCR 字符到数字的容错映射

#### `text_constants.py` — 别名表

- `ATTRIBUTE_ALIASES`（5 属性）/ `RELIC_NAME_ALIASES` / `TRAINING_NAME_ALIASES` / `REST_OPTION_ALIASES` / `SHOP_ALIASES` / `OCR_REGION_NAME_HINTS`

#### `manifest.py` — 离线测试

- `load_manifest(json_path)`：加载 `GameState + Observation` 列表
- `_parse_payload(screen, data)`：按 Screen 类型分发解析

#### `fixtures.py` — Demo 数据

- `demo_state`：默认 GameState
- `demo_observations`：20 个 demo 帧覆盖 21 画面（用于 offline_harness 演示）

#### `image_regions.py` — 图像裁剪/标注

- `crop_region(image, rect)`
- `export_region_crops(image, profile, output_dir)`
- `draw_region_overlay(image, profile)`

### 4.3 决策执行层

#### `screens/` — Parser 层（21 parser）+ HANDLERS 注册表

**`screens/__init__.py`** —— **唯一调度枢纽**（366 行）

- `HANDLERS: dict[Screen, DelegatingScreenHandler]`：21 项
- 21 个 `_decide_X` 薄包装函数：校验 payload 类型 + 调 `policy.decide_X`
- `ANCHOR_HANDLERS` + `rebuild_anchor_handlers()`：**原地替换**（`ANCHOR_HANDLERS[:] = sorted(...)` 保持对象身份）
- `_parse_event_choice_combined`：`training_direction + event_choice` 合并

**`screens/base.py`** —— 接口契约

```python
class ScreenHandler(Protocol):
    screen: Screen
    priority: int
    has_anchor: Callable[[RegionProfile], bool]
    parse: Callable[..., payload | None]
    decide: Callable[[payload, GameState], Action]

class DelegatingScreenHandler:
    def __init__(self, screen, decide_fn, priority=0,
                 anchor_fn=None, anchor_confidence=0.0,
                 parse_fn=None, parse_needs_image=False,
                 ocr_prefixes=()): ...
```

**21 个 parser 文件**（按画面拆分）：

| 文件 | parser | 坑关联 |
|------|--------|--------|
| `training.py` | `parse_training_hub`（D-DAY 评鉴战日分支 + commission_alert + shop_alert）<br>`parse_training_select`（5 卡 + ring + 失败率 None=未选中卡） | #24 |
| `simple.py` | `parse_journey_start / parse_confirm_dialog / parse_event_fast_forward_setting / parse_dialogue_scene`（arcana_center 分支）<br>`PostTrainingResult` / `parse_post_training / parse_training_direction / parse_skill_select` | — |
| `blessing.py` | `parse_blessing_setup`<br>`parse_blessing_choice`（OCR + 视觉双信号交叉验证 + 子祝福数检测） | — |
| `character_select.py` | `parse_character_select`（固定行 OCR）<br>`parse_character_select_bbox`（滚动半行偏移用 bbox 定位）<br>`_match_character_variants`（同名多形态） | — |
| `relic.py` | `parse_relic_choice`（3 卡 + 部位→属性映射 + 首轮固定首选布谷鸟 + 网格变体） | — |
| `rest.py` | `parse_rest_submenu`（冥想室检测 + 露宿/住处/冥想室三选项） | — |
| `shop.py` | `parse_shop`（每行 ShopItem + selected_effect 详情区） | — |
| `commission.py` | `parse_commission_select`（建议综合等级 + 角色综合等级；解耦不依赖先经训练大厅） | #39 |
| `event.py` | `parse_event_choice`（多选项内容检查） | #2 |
| `battle.py` | `parse_battle`（评鉴战 entry + 跳过二次确认） | #6 |
| `region_move.py` | `parse_region_move`（列车月台两步流 + 双锚点消歧） | #5 |

#### `policy/` — 决策层（9 文件）

**`policy/engine.py`** —— 主决策器

```python
class TrainerPolicy(
    CharacterSelectMixin, TrainingMixin, SimpleMixin, BlessingMixin,
    EventMixin, RelicCommissionMixin, ShopSkillMixin
):
    def __init__(self):
        self._pending_commission = None     # 两步确认状态机
        self._pending_relic = None
        self._pending_blessing = None
        self._needs_rest = False
        self._rest_for_mood = False
        self._pending_rest = None
        self._char_scroll_* = ...           # 角色选择滚动状态
        self._char_pending_confirm = None
        self._dday_trading_done = False

    def decide(self, observation) -> Action:
        # 1) confidence 检查（<min_screen_confidence 拒绝决策）
        # 2) 状态重置
        # 3) 走 HANDLERS 分发 → policy.decide_X
```

- `training_score(choice) = stat_gain + ring_value - fail_penalty + strategic_bias + early_bonus`
- `_is_iterable_of(obj, type)`

**`policy/config.py`** —— 决策配置

```python
class PolicyConfig:
    min_screen_confidence = 0.75
    max_training_fail_rate = 30
    meditation_coin_threshold = 60   # 冥想室金币阈值
    lodging_coin_threshold = 30     # 住处金币阈值
    early_game_rounds = 12
    early_ring_multiplier = 2.5
    # ring_bonus / shop_whitelist / shop_buy_effect_keywords
    # training_bias_by_profile / skill_keywords_by_profile
    # blessing_attribute_by_profile / relic_attribute_priority_by_profile
    # 硬编码按钮坐标: start_button / skip_button / reward_continue_button
    #                  skill_select_close_button / screen_center / game_menu_close_button
```

**7 个 Mixin**：

| Mixin | 文件 | 关键决策 |
|-------|------|---------|
| `CharacterSelectMixin` | `character_select.py` | 候选排序 + 双向滚动 cap=30 + `_char_pending_confirm` 两步确认 + 同名多形态 |
| `TrainingMixin` | `training.py` | `training_score` 排序 + 两步确认 + 全失败率过高回 hub `_needs_rest` |
| `SimpleMixin` | `simple.py` | `decide_journey_start/confirm_dialog/event_fast_forward_setting/dialogue`（repeat=3）<br>`decide_rest`（`_rest_for_mood` 优先住处 / 冥想室 / 住处 / 露宿 + 两步确认） |
| `BlessingMixin` | `blessing.py` | `decide_blessing_setup`（装备空槽）+ `decide_blessing_choice`（两步确认）+ `blessing_score` |
| `EventMixin` | `event.py` | `event_priority` + 三级降级（DB → 攻击/生存分支 → 关键词） |
| `RelicCommissionMixin` | `relic_commission.py` | `decide_relic`（两步确认）+ `_combo_relic_pick` + `decide_commission`（选可做最高阶） |
| `ShopSkillMixin` | `shop_skill.py` | `shop_item_worth_buying` + `choose_shop_item` + `decide_shop`（限购 1 件）+ `skill_score`（已习得 -inf） |

**`policy/event_db.py`** — 事件关键词数据库

- `DEFAULT_EVENT_KEYWORDS`（5 类关键词）
- `_load_event_db(path)` / `_match_event(text, db)`（字符级模糊阈值 0.6）/ `_event_recommended_index`

#### `executor.py` — 执行层

- `ExecutionResult`：`success + message`
- `ActionExecutor` Protocol
- `DryRunExecutor`：测试用空执行
- `PyAutoGuiExecutor`：
  - `FAILSAFE=True` + **4 角急停**（margin=120）
  - `_hover_move(target)`：**12 步 mouse_event 滑入 + 0.4s dwell** —— 模拟真悬停（Unity 不响应 `MoveTo` 直跳）
  - `_drag_scroll(target)`：`mouse_event LEFTDOWN → MOVE → LEFTUP` —— 模拟真拖拽
- `map_action_to_rect(action, capture_rect, screen_size)`：截图坐标 → 屏幕坐标映射

### 4.4 检视器（多帧收集信息）

inspector 模式：单帧 OCR 不够，需要先点击让游戏展开信息，再读，再决策。

| Inspector | 文件 | 行为 |
|-----------|------|------|
| `TrainingInspector` | `training_inspector.py` | **早期游戏**（前 20 回合）：逐张点 5 卡读 `count_heads`，max<=1 → None 休息；平局按 力量>体力>韧性>专注>保护<br>**非早期**：3 卡 inspect |
| `CommissionInspector` | `commission_inspector.py` | `rank_tolerance=3`；逐个点开读 `selected_suggested_rank`；选 ≤角色 rank+3 最高阶 |
| `ShopInspector` | `shop_inspector.py` | 限购 1 件；逐行点开读 `selected_effect`；按效果关键词买 |
| `BlessingChoiceInspector` | `blessing_inspector.py` | 同值卡按子祝福数选最多；**必须 click 不悬停** |

### 4.5 CLI 入口

#### `cli/live_loop.py` — 主循环（402 行，12 步）

详见 [§8 核心数据流](#8-核心数据流live_loop-12-步)。

#### `cli/pause.py` — F11 暂停

- `PauseController`：`_paused` 标志 + `toggle/pause/resume`
- `install_pause_hotkey(hotkey="f11")`：`keyboard.on_press` + `trigger_on_release=True`（避免按下时游戏还在响应中）

> F11 替换原 F9（避免与浏览器 F9 调试冲突），见 [memory/pause-hotkey-f11.md](../../../Users/Administrator/.claude/projects/d--starsavior-trainer-v2/memory/pause-hotkey-f11.md)。

#### `cli/runtime.py` — 运行时工具

- `_is_corner_point(point, margin=120)`：4 角急停检测
- `_mouse_at_screen_corner()`：mouse 移到角时立即抛 `pyautogui.FailSafeException`
- `_create_ocr(use_paddle=False)`：**旧名保留**，实际返回 `RapidOcrEngine`
- `_find_or_exit(title)`：找不到窗口直接 exit
- `_print_windows()`：列出所有可见窗口（调试用）

#### `cli/blue_parsers.py` — payload 读取路由（376 行）

- `_read_screen_payload_ocr(screen, reader, profile, image)`：**走 HANDLERS 注册表**；CHARACTER_SELECT 走 bbox
- `_read_screen_payload_blue(screen, reader, profile, image)`：`_BLUE_PARSERS` 9 项（shop/training_hub/training_select/rest_submenu/commission_select/relic_choice/event_choice/dialogue 等）
- 8 个 `_X_blue builder`
- `_screen_to_prefix`：**死代码保留**（NOTE 标注）

#### `cli/offline_harness.py` — 离线测试入口

```
python -m starsavior_trainer.cli.offline_harness --manifest path.json
python -m starsavior_trainer.cli.offline_harness --screenshots dir/
python -m starsavior_trainer.cli.offline_harness --demo
python -m starsavior_trainer.cli.offline_harness --jsonl file.jsonl
```

### 4.6 Web UI

#### `web/app.py` — Flask 路由（387 行，17 路由）

- `index` / `config` / `process` / `status` / `stop` / `logs` / `stream` / `clear`
- `train/start` / `journey/start`
- `capture` / `screenshot` / `list-windows`
- `calibrate` / `crop-regions` / `read-regions`
- `offline` / `demo` / `manifest` / `tests` / `run` / `logs/list` / `logs/read`

#### `web/process_manager.py` — 子进程单例

- `PROJECT_ROOT` / `REGIONS_DIR` / `CHARACTERS_FILE` 常量
- `current_process` / `process_lock` / `log_queue` 单例
- `BUILD_PROFILES`（6 个）：standard / power / support / agile / mage / tank
- `CLASSIFY_MODES`（5 个）：ocr / blue_button / hybrid / filename / anchor_only
- `_list_region_profiles()` / `_load_characters()` / `_run_command()`（**显式 close stdout** 防文件句柄泄漏）

---

## 5. 关键类与函数说明

### 5.1 核心数据类

#### `Screen`（Enum）

```python
class Screen(Enum):
    UNKNOWN = "unknown"
    JOURNEY_START = "journey_start"
    CHARACTER_SELECT = "character_select"
    TRAINING_HUB = "training_hub"
    TRAINING_SELECT = "training_select"
    BLESSING_SETUP = "blessing_setup"
    BLESSING_CHOICE = "blessing_choice"
    EVENT_CHOICE = "event_choice"
    RELIC_CHOICE = "relic_choice"
    COMMISSION_SELECT = "commission_select"
    REST_SUBMENU = "rest_submenu"
    SHOP = "shop"
    REGION_MOVE = "region_move"
    BATTLE = "battle"
    CONFIRM_DIALOG = "confirm_dialog"
    POST_TRAINING = "post_training"
    SKILL_SELECT = "skill_select"
    DIALOGUE = "dialogue"
    EVENT_FAST_FORWARD = "event_fast_forward"
    REWARD = "reward"
    GAME_MENU = "game_menu"
    TRAINING_DIRECTION = "training_direction"
```

#### `Rect`（frozen dataclass）

```python
@dataclass(frozen=True)
class Rect:
    x1: int; y1: int; x2: int; y2: int
    @property
    def center(self) -> tuple[int, int]: ...
```

#### `Action`（dataclass）

```python
@dataclass
class Action:
    kind: str                      # "click" / "scroll" / "drag" / "skip" / "wait"
    target: Rect | None            # 目标坐标
    reason: str                    # 决策理由（日志用）
    confidence: float = 1.0
    scroll_clicks: int = 0         # 滚动格数
    repeat: int = 1                # 重复次数
```

#### `GameState`（跨帧状态）

```python
@dataclass
class GameState:
    round: int = 0
    profile: str = "standard"
    # 两步确认状态机
    _pending_commission: CommissionOption | None = None
    _pending_relic: RelicOption | None = None
    _pending_blessing: BlessingOption | None = None
    _pending_rest: RestOption | None = None
    # 角色选择滚动状态
    _char_scroll_dir: str = "down"
    _char_scroll_count: int = 0
    _char_pending_confirm: dict | None = None
    # 训练失败回休息
    _needs_rest: bool = False
    _rest_for_mood: bool = False
    # D-DAY 交易完成
    _dday_trading_done: bool = False
```

#### `Observation`（一帧的全部信息）

```python
@dataclass
class Observation:
    screen: Screen
    payload: object | None         # parse_X 的返回值
    image: Image.Image | None
    frame_index: int
```

### 5.2 关键函数

#### 分类入口

```python
# classifier.py
def classify_hybrid(
    reader: RegionOcrReader,
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> tuple[Screen, float]:
    """OCR 优先 + 蓝键 fallback + journey-origin visual 消歧 + BLESSING_CHOICE visual 消歧"""
```

#### payload 读取（走注册表）

```python
# cli/blue_parsers.py
def _read_screen_payload_ocr(
    screen: Screen,
    reader: RegionOcrReader,
    profile: RegionProfile,
    image: Image.Image | None,
) -> object | None:
    """走 screens.HANDLERS[screen].parse(); CHARACTER_SELECT 走 bbox"""
```

#### 决策入口

```python
# policy/engine.py
class TrainerPolicy:
    def decide(self, observation: Observation) -> Action:
        """confidence 检查 → 状态重置 → HANDLERS[screen].decide(payload, state)"""

    def training_score(self, choice: TrainingChoice) -> float:
        """stat_gain + ring_value - fail_penalty + strategic_bias + early_bonus"""
```

#### 执行入口

```python
# executor.py
class PyAutoGuiExecutor:
    def execute(self, action: Action, capture_rect: Rect) -> ExecutionResult:
        """map_action_to_rect → click/scroll/drag → FAILSAFE 检查"""
```

#### 视觉识别（head 模板匹配）

```python
# vision.py
def _is_head_template(path: Path) -> bool:
    """新库作数模板过滤：文件名匹配 `^\d+\.png$`（如 1.png / 23.png）。
    non_counting_head_*.png 不匹配 → count_heads 不计数不作数头。
    遗留 counting_head_*.png 不匹配但保留参与定位。"""

def count_heads(img) -> int:
    """支援卡作数头计数：glob `*.png` + _is_head_template 过滤；阈值 0.85 全图搜。
    双分数：loc_score（所有模板含旧库，定位）+ dedup_score（新库 N.png + non_counting_head_3+.png，去重）。
    裁剪不含进度条（_HEAD_H_FRAC = 93/260，111×93）。
    实测：5 颗头（slot0=non_counting_head_3 不作数 + slot4=4.png + slot1/2/3=5/6/7.png）→ 返回 4。"""

def _find_head_instances(img, template) -> list:
    """NMS：改用 loc_score 局部极大值（原"相邻 y 差合并"有 bug，会漏检/重复合并）。
    候选过滤：_HEAD_EMPTY_STD = 40（std < 40 视为空槽，过滤远 panel 噪声，见坑 #41）"""
```

### 5.3 关键 Mixin 决策方法

| 方法 | 文件 | 行为概要 |
|------|------|---------|
| `decide_character_select` | `policy/character_select.py` | 候选排序 + 双向滚动 cap=30 + 两步确认 |
| `decide_training` | `policy/training.py` | `training_score` 排序 + 两步确认 + 失败回 hub |
| `decide_journey_start` | `policy/simple.py` | 点 start_button |
| `decide_confirm_dialog` | `policy/simple.py` | 点确认按钮 |
| `decide_dialogue` | `policy/simple.py` | repeat=3 点屏幕中央推进 |
| `decide_rest` | `policy/simple.py` | `_rest_for_mood` 优先级：住处 → 冥想室 → 住处 → 露宿 |
| `decide_blessing_setup` | `policy/blessing.py` | 装备空槽 |
| `decide_blessing_choice` | `policy/blessing.py` | `blessing_score` + 两步确认 |
| `decide_event` | `policy/event.py` | 三级降级：DB → 攻击/生存分支 → 关键词 |
| `decide_relic` | `policy/relic_commission.py` | 两步确认 + `_combo_relic_pick` |
| `decide_commission` | `policy/relic_commission.py` | 选可做最高阶 |
| `decide_shop` | `policy/shop_skill.py` | 按效果买，限购 1 件 |
| `decide_skill` | `policy/shop_skill.py` | `skill_score`（已习得 -inf） |

### 5.4 关键 Inspector 方法

```python
# inspectors/training_inspector.py
EARLY_GAME_HEAD_ROUNDS = 20   # 前 20 回合走早期游戏逻辑
EARLY_GAME_HEAD_ATTRS = ["力量", "体力", "韧性", "专注", "保护"]

class TrainingInspector:
    def decide(self, observation, state, executor) -> Action:
        if state.round <= EARLY_GAME_HEAD_ROUNDS:
            return self._decide_early_game(...)
        # 非早期：3 卡 inspect
```

### 5.5 行为日志

```python
# behavior.py
def narrate(msg: str) -> None:
    """中文叙述 bot 每步行为，写入 logs/behavior.log"""
```

---

## 6. 依赖关系

### 6.1 第三方依赖（requirements.txt）

```
pillow
pyautogui==0.9.54
keyboard
rapidocr-onnxruntime==1.4.4
onnxruntime-gpu==1.27.0
numpy>=1.21.2,<2.0.0
opencv-python==4.5.5.64
flask==3.0.0
flask-cors==4.0.0
```

**额外 GPU 依赖**（不写在 requirements，由 RapidOCR 自动加载）：

```
nvidia-cudnn-cu13
nvidia-cublas-cu13
nvidia-cuda-nvrtc-cu13
```

### 6.2 内部模块依赖图（关键路径）

```
                            ┌──── models.py ◄──── (所有人依赖)
                            │
                            ├──── regions.py
                            │
capture.py ──┐              │
             │              │
             ▼              │
ocr.py ────► ocr_reader.py ─┤
                            │
                            ▼
                       classifier.py ◄─── classifier_anchors.py
                            │             ◄─── classifier_signatures.py
                            │
                            ▼
                       screens/__init__.py (HANDLERS)
                            │             ▲
                            │             │ (parser 注册)
                            │             │
                       screens/*.py ──────┘
                            │
                            ▼
cli/blue_parsers.py ◄─── cli/runtime.py
        │
        ▼
cli/live_loop.py ◄─── policy/engine.py ◄─── policy/*.py (7 Mixin)
        │                  │
        │                  ▼
        │            inspectors/*.py (4)
        │
        ▼
   executor.py
        │
        ▼
     (game)
```

**关键枢纽**：

- `models.py` — 所有人依赖（数据契约）
- `regions.py` — 所有坐标相关代码依赖
- `screens/__init__.py` — 分类/决策/payload 三处统一走 HANDLERS
- `policy/engine.py` — 决策总入口

### 6.3 与旧项目（`d:/chengfeng`）的迁移映射

详见 [docs/新项目技术设计.md §迁移映射表](新项目技术设计.md)。核心改动：

| 旧文件 | 行数 | 拆分到 |
|--------|------|--------|
| `screen_reader.py` | 1557 | `screens/*` (14 parser 文件) + `classifier*` (3) + `ocr_reader.py` + `text_utils.py` |
| `policy.py` | 828 | `policy/` (9 文件) + `inspectors/` (4) |

---

## 7. 项目运行方式

### 7.1 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt

# 必须有 NVIDIA GPU + CUDA（RapidOCR GPU 后端）
# 系统缩放设为 100%（脚本会强制 DPI 感知，但仍建议系统层就设对）
```

### 7.2 区域配置

```bash
# 1. 准备区域坐标 YAML（region_profiles/下）
#    每个画面定义 anchor + 各 OCR 区域 + 按钮坐标

# 2. 校准 / 查看区域
python -m starsavior_trainer.cli.offline_harness --screenshots region_profiles/
# 或通过 Web UI 的 /calibrate 路由
```

### 7.3 主程序（CLI）

```bash
# 启动主循环
python -m starsavior_trainer.cli.live_loop

# 常用参数：
#   --profile standard|power|support|agile|mage|tank
#   --classify-mode hybrid|ocr|blue_button|filename|anchor_only
#   --region-profile path/to/yaml
#   --character name
#   --dry-run               # 不实际点击，只决策
```

**运行时热键**：

- `F11`：暂停 / 继续（`trigger_on_release=True`，避免按下时游戏还在响应）
- 鼠标移到屏幕 4 角（margin=120）：**急停**（pyautogui FAILSAFE）

### 7.4 Web UI

```bash
python -m starsavior_trainer.web.app
# 默认 http://127.0.0.1:5000
```

**主要路由**：

| 路由 | 用途 |
|------|------|
| `/` | 主页面 |
| `/process` (POST) | 启动训练子进程 |
| `/status` | 查询子进程状态 |
| `/stop` | 停止子进程 |
| `/logs/stream` | SSE 实时日志流 |
| `/capture` | 抓一张图 |
| `/screenshot` | 返回当前截图 |
| `/list-windows` | 列出可用游戏窗口 |
| `/calibrate` | 校准区域坐标 |
| `/crop-regions` | 导出区域裁剪图 |
| `/read-regions` | OCR 读取各区域文本 |
| `/offline` / `/demo` / `/manifest` | 离线测试 |
| `/tests/run` | 运行测试套件 |

### 7.5 离线测试

```bash
# demo 数据
python -m starsavior_trainer.cli.offline_harness --demo

# 指定 manifest
python -m starsavior_trainer.cli.offline_harness --manifest tests/fixtures/sample.json

# 截图目录
python -m starsavior_trainer.cli.offline_harness --screenshots tests/fixtures/

# JSONL
python -m starsavior_trainer.cli.offline_harness --jsonl tests/fixtures/sample.jsonl
```

### 7.6 单元测试

```bash
# 全部测试（131 测试）
pytest tests/

# 按模块
pytest tests/test_classifier.py
pytest tests/test_policy.py
pytest tests/test_screens.py
pytest tests/test_inspectors.py
```

### 7.7 头像采集工具

```bash
# 采集新支援卡头像模板（详见 docs/头像采集流程.md）
# 保护训练 = speed = 5 张卡最下方
python -m starsavior_trainer.tools.collect_head_templates
# 截图→裁剪（不含进度条，111×93，_HEAD_H_FRAC=93/260）→去重（阈值 0.93 > 识别阈值 0.85）→入库 config/assets/N.png
```

**两类命名 + dedup 扫描集**：

| 类型 | 命名 | 含义 | count_heads | dedup |
|------|------|------|-------------|-------|
| 作数头像 | `N.png`（`^\d+\.png$`） | 计入支援卡人头数 | ✅ 计数 | ✅ 参与去重 |
| 不作数头像 | `non_counting_head_N.png`（`^non_counting_head_\d+\.png$`） | 不计入支援卡人头数（沿用旧库风格，旧库已有 1/2，新库从 3 开始） | ❌ 不计数 | ✅ 参与去重 |
| 旧库作数 | `counting_head_*.png` | 含进度条，几何 113×113 不同 | ❌ 不计数（命名不匹配） | ❌ 不参与（几何不同） |

- `_is_non_counting_template(path)`：判断 `^non_counting_head_\d+\.png$`
- `_is_dedup_template(path)`：`_is_new_library_template(path) or _is_non_counting_template(path)`（作数 + 不作数都参与去重，避免同一颗头无论作数/不作数反复入库污染新库）
- `_find_head_instances` 和 `_is_duplicate` 用 `_is_dedup_template` 加载 dedup 模板
- 旧库 `non_counting_head_1/2.png`（旧几何 113×113）会被加载，但因尺寸 > 新窗口 111×93 在 `tpl.shape[0] > win_h` 处自动跳过

### 7.8 日志位置

```
logs/
├── starsavior_YYYYMMDD.log     # DEBUG 级，按天滚动
├── starsavior_error.log        # ERROR 级单独
├── starsavior.log              # RotatingFileHandler 10MB
└── behavior.log                # 中文行为叙述（narrate 写入）
```

7 天自动清理（`_cleanup_old_logs`）。

---

## 8. 核心数据流（live_loop 12 步）

`cli/live_loop.py:main()` 单次迭代：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 急停检查 (_mouse_at_screen_corner / FAILSAFE)                     │
│    ├─ 命中 → 抛 pyautogui.FailSafeException → 退出                    │
│    └─ 无 → 继续                                                       │
├─────────────────────────────────────────────────────────────────────┤
│ 2. F11 暂停检查 (PauseController.is_paused)                          │
│    └─ 暂停 → sleep 0.5s 循环等待恢复                                   │
├─────────────────────────────────────────────────────────────────────┤
│ 3. 截图 capture_window(title, 2560, 1440)                             │
├─────────────────────────────────────────────────────────────────────┤
│ 4. scale_region_profile(profile, scale_x, scale_y)                    │
│    └─ 区域坐标按目标分辨率缩放                                           │
├─────────────────────────────────────────────────────────────────────┤
│ 5. classify_hybrid(reader, profile, image) → (Screen, confidence)    │
│    ├─ OCR 优先 (fast anchors → 全量 fallback)                         │
│    ├─ 蓝键 fallback                                                    │
│    └─ visual 消歧 (journey-origin / BLESSING_CHOICE)                  │
├─────────────────────────────────────────────────────────────────────┤
│ 6. UNKNOWN 处理                                                       │
│    ├─ ≤4 帧 → 跳过（OCR 抖动）                                          │
│    └─ >4 帧 → 报警 + 智能睡眠                                          │
├─────────────────────────────────────────────────────────────────────┤
│ 7. parse payload (HANDLERS[screen].parse)                            │
│    └─ CHARACTER_SELECT 走 bbox（滚动半行偏移用 bbox 定位）              │
├─────────────────────────────────────────────────────────────────────┤
│ 8. round_tracker.observe_date(date_text)                              │
│    └─ "<月>月<上中下>旬" 变化时 _round+1（坑 #29 失败返 None 不前进）    │
├─────────────────────────────────────────────────────────────────────┤
│ 9. 3 个 inspector 检查（按 screen 决定是否触发）                        │
│    ├─ TrainingInspector (TRAINING_SELECT)                             │
│    ├─ CommissionInspector (COMMISSION_SELECT)                         │
│    └─ ShopInspector (SHOP)                                            │
│    └─ BlessingChoiceInspector (BLESSING_CHOICE)                       │
├─────────────────────────────────────────────────────────────────────┤
│ 10. policy.decide(observation) → Action                              │
│     ├─ confidence 检查                                                │
│     ├─ 状态重置                                                       │
│     └─ HANDLERS[screen].decide(payload, state)                        │
├─────────────────────────────────────────────────────────────────────┤
│ 11. 重复点击检查 + execute 前再查急停                                  │
│     ├─ 同一 target 连续 ≥3 次 → 报警 + 强制 UNKNOWN 重置                │
│     └─ _mouse_at_screen_corner → 急停                                  │
├─────────────────────────────────────────────────────────────────────┤
│ 12. activate_window + map_action_to_rect + execute + 智能睡眠          │
│     ├─ advance screen (_ADVANCE_SCREENS)：sleep 0.35s                  │
│     ├─ TRAINING_SELECT：sleep 0.5s                                    │
│     └─ 其他：sleep 1.0s                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. 历史坑与规避索引

旧项目 39 个历史坑，按 A-G 类别整理（详见 [docs/现有项目历史坑台账.md](现有项目历史坑台账.md)）。新项目已规避的关键坑：

| 坑号 | 类别 | 描述 | 新项目规避方式 |
|------|------|------|---------------|
| #1 | A 分类误判 | JOURNEY_START 被误判 REGION_MOVE | `_looks_like_journey_start` visual 消歧 |
| #2 | A | EVENT_CHOICE 与 DIALOGUE 共享标题 | `_has_real_event_options` 多选项检查 |
| #5 | A | 列车月台被误判 RELIC_CHOICE | 双锚点（地区移动 + 列车月台）消歧 |
| #6 | A | 评鉴战被误判 EVENT_FAST_FORWARD | `跳过战斗+评鉴战` 标题消歧 |
| #24 | E OCR | 训练卡失败率 None=未选中卡 | `TrainingChoice.fail_rate: int \| None`（None 绝不当 0% 赌博） |
| #25 | E | RANK17A 中 17A 不被识别为 17 | `parse_rank_number` 不守卫相邻字母 |
| #29 | E | 日期解析失败导致回合错跳 | `RoundTracker` 失败返 None 不前进 |
| #35 | — | SKILL_SELECT 决策未接上 | T14 接上 `decide_skill`（[设计方案 §8](设计方案.md)） |
| #39 | — | 委托依赖先经训练大厅读 character_rank | `parse_commission_select` 解耦，本界面直接读 |
| #40 | F 模板匹配 | 头像模板含进度条导致漂移 | 旧裁剪 `_HEAD_H_FRAC = 113/260` 含进度条，训练后羁绊值变化使模板漂移；新库改 `93/260`（111×93）裁剪不含进度条 + `N.png` 纯数字命名 |
| #41 | F 模板匹配 | NMS std 阈值过低导致远 panel 噪声误识别 | `_HEAD_EMPTY_STD` 原 25 过低：实测真头像 std 73-98 远高于 40，远 panel 噪声区 std≈25（如 y=1205 处 std=25.8）会被误判为头像候选；提到 40 干净分离 |

**新项目新增规避**：

- **OCR 抖动翻转**：两步确认 `_pending_X` 状态机（first set → second confirm）
- **Unity 输入特性**：`mouse_event` 12 步滑入 + 0.4s dwell（真悬停）+ LEFTDOWN/MOVE/LEFTUP（真拖拽）
- **窗口失焦**：`AttachThreadInput` 绕反偷焦
- **DPI 错乱**：模块加载即调 `SetProcessDpiAwareness(2)`
- **GPU OCR 失败**：`RapidOcrEngine` 自动回退 CPU
- **文件句柄泄漏**：`process_manager._run_command` 显式 close stdout

---

## 10. 扩展指引

### 10.1 新增一个画面

**只动一处**（契约 3）—— `screens/__init__.py`：

1. `models.py` 加 `Screen` 枚举
2. `screens/<new>.py` 写 `parse_X` 函数
3. `screens/__init__.py`：
   - `HANDLERS[Screen.X] = DelegatingScreenHandler(...)`
   - 加 `_decide_X` 薄包装
4. `policy/<new>.py` 写 `decide_X` 方法（作为 Mixin 加入 `TrainerPolicy`）
5. `classifier_anchors.py` 加 `ANCHOR_REGIONS_BY_SCREEN` + `ANCHOR_TEXT_BY_SCREEN`

### 10.2 新增一个 inspector

1. `inspectors/<new>_inspector.py` 写 `<X>Inspector` 类
2. `cli/live_loop.py` 第 9 步加触发条件

### 10.3 改动决策逻辑（非 1:1 迁移）

**必须同步更新两份文档**（项目规则）：

- [docs/变更记录.md](变更记录.md) —— **改了什么**
- [docs/设计方案.md](设计方案.md) —— **方案理由**

### 10.4 代码规范

- 单文件 ≤ 400 行（超了就拆）
- 嵌套 ≤ 4 层
- 优先 Edit 不重写整个文件
- 不做要求之外的功能 / 不抽象单次使用的代码 / 不为不可能场景写错误处理
- 不"顺手改进"相邻代码 / 不重构没坏的东西 / 匹配既有风格

### 10.5 行为准则（Karpathy）

1. **Think Before Coding** — 先思考再编码：不假设、不藏疑惑、主动摆出权衡
2. **Simplicity First** — 简洁优先：用解决问题的最少代码，不做投机性设计
3. **Surgical Changes** — 外科手术式修改：只动必须动的，只清理自己造成的残留
4. **Goal-Driven Execution** — 目标驱动执行：先定可验证的成功标准，循环验证到通过

---

## 附录：关键文档索引

| 文档 | 用途 |
|------|------|
| [CLAUDE.md](../CLAUDE.md) | 项目契约 + 行为准则（**最高优先级**） |
| [docs/迁移交接.md](迁移交接.md) | **新会话接手先读**：精确进度 + T18 待办 + 操作手册 |
| [docs/新项目技术设计.md](新项目技术设计.md) | 架构/数据流/模块接口/迁移映射/坑规避索引 |
| [docs/设计方案.md](设计方案.md) | 13 § 非 1:1 迁移改动方案理由 |
| [docs/变更记录.md](变更记录.md) | 时间线改动记录 |
| [docs/现有项目架构分析.md](现有项目架构分析.md) | 旧项目模块职责、超大文件拆分方案 |
| [docs/现有项目历史坑台账.md](现有项目历史坑台账.md) | 39 坑 A-G 类 + 规避优先级 |
| [docs/头像采集流程.md](头像采集流程.md) | collect_head_templates 工具使用流程 |
| [docs/Code-Wiki.md](Code-Wiki.md) | **本文档**：代码导览 |

---

*本文档基于 2026-07-04 代码状态整理。后续代码变更若偏离本文档描述，以代码实际行为为准；非 1:1 迁移改动须同步更新 [变更记录.md](变更记录.md) + [设计方案.md](设计方案.md)。*
