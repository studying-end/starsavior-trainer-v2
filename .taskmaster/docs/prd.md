# PRD — Star Savior Trainer v2（重构迁移）

> 同游戏同功能，重构自 `d:/chengfeng`（~6275 行）。架构依据见 `docs/现有项目架构分析.md`、`docs/现有项目历史坑台账.md`。
> 目标：把可复用通用框架直接迁移，游戏特定逻辑重写，并在架构上提前规避 39 个历史坑。

## 1. 目标与范围

重建 Star Savior（PC 客户端）训练自动化脚本，保持**单屏状态机**核心架构，按层迁入并在新结构中复刻既有功能。

**成功标准（验收硬约束，全部必须达成）：**
1. 一次完整的 live_loop 实跑能成功（坑台账 #38：旧项目从未有一次确认成功的完整 run，是最大风险）。
2. 全部单元测试通过（迁移旧 148 测试 + 新增）。
3. 单文件 ≤ 400 行，嵌套 ≤ 4 层（CLAUDE.md 规范）。
4. `screen_reader.py`（旧 1557 行）、`policy.py`（旧 828 行）按拆分方案落到子包，不再存在超大文件。

## 2. 核心架构契约（不可违背，代码评审硬卡点）

- **单屏状态机**：每帧识别当前画面类别，只跑匹配该画面的策略；绝不在错误画面点"看似合理"的按钮。
- **OCR/CV 只产生 Observation，绝不直接决定 Action**。识别层（classifier/screen_reader）与决策层（policy）解耦：classifier 不知道 payload 形状，policy 不读像素。
- **screens 注册表是唯一调度枢纽**：分类、决策、payload 读取三处统一走 `screens.HANDLERS`，加画面只动一处。

## 3. 技术栈

pyautogui（鼠标合成）+ PaddleOCR 2.7.3 / paddlepaddle-gpu 3.0.0b2（GPU OCR）+ OpenCV 4.5.5（HSV）+ Pillow（裁剪/缩放）+ Flask 3.0.0（Web UI）+ 原生 ctypes（Windows 窗口截图/前台切换/底层 mouse_event）。

## 4. 功能需求（按层）

### F1 — 通用框架迁移（直接搬，不改逻辑）
通用可复用代码原样迁入新包结构，附单元测试：
- `logging_setup.py`：按天文件 DEBUG + 错误独立文件 + 10MB 轮转 + 7 天清理 + UTF-8。
- `models.py` 结构：`Screen` 枚举、`Rect`(frozen, 带 center)、`Action`(click/move/scroll/pause/skip/repeat)、每画面 frozen dataclass payload（`fail_rate:int|None` 表"未选中卡未知失败率，绝不当 0% 赌博"）、`GameState`/`Observation`。
- `regions.py`：`RegionProfile` + `load_region_profile`(JSON→Rect) + `scale_region_profile`（区域配置只写一份基础分辨率，按当前截图缩放）。
- `image_regions.py`：crop_region / export_region_crops(标定) / draw_region_overlay(核对)。
- `manifest.py` + fixtures：离线回放数据结构。

### F2 — 截图与 OCR 引擎（通用）
- `capture.py`：DPI 感知 `SetProcessDpiAwareness(2)` 须在任何窗口/截图调用前；`PrintWindow+PW_RENDERFULLCONTENT(2)` 抓被遮挡/未聚焦的 Unity 硬件加速窗口（不用 ImageGrab）；客户区缩放到目标分辨率（默认 2560×1440）；`activate_window` 用 AttachThreadInput 绕过 Windows 反偷焦；全黑帧检测回退（坑台账 F 类 30-32）。
- `ocr.py`：`OcrEngine` Protocol + `NoopOcrEngine`(管线测试) + `PaddleOcrEngine`(PP-OCRv4_mobile，兼容 PaddleOCR 2.x/3.x/3.5 三种返回格式，禁 oneDNN/PIR)；`read_lines` 返回带 bbox 的行（角色列表滚动半行偏移用）。

### F3 — 视觉检测与分类（通用框架 + 游戏特定规则）
- `vision.py`：RingColorDetector / BlueButtonDetector 检测框架通用，**颜色阈值是游戏特定的，需重新标定**（旧 14 个阈值常量）。
- `classifier.py`：`classify_by_ocr`(两遍加速：先 OCR ~26 fast anchors 不命中再全量 ~54 区域)、`classify_by_blue_button`(纯颜色无 OCR)、`classify_hybrid`(OCR+蓝键兜底，**实跑默认**)。每个易混淆画面配 `_has_X_signature` 多信号消歧函数；陷阱画面（REWARD/GAME_MENU）独立 Screen 且 priority 高早检查（坑台账 A 类 1-11、G 类规避优先级 🔴）。

### F4 — 画面 payload 解析（screen_reader.py 拆分，游戏特定重写）
旧 1557 行拆为：
- `text_constants.py`：ALIASES 常量。
- `ocr_reader.py`：RegionText / RegionOcrReader(read_all/read_names/read_prefixes/read_where，带 max_area 过滤)。
- `text_utils.py`：normalize_ocr_text / contains_any_text / extract_character_name / parse_first_int(容错 o/l/i/s) / parse_rank_number(不守卫相邻字母) / parse_percent。
- `screens/*.py`：每画面一个 parser（character_select 含滚动列表 + 同名多形态匹配、blessing、relic、training 含 D-DAY 分支、rest/event/commission/shop/region_move/battle 等）。**OCR 锚点文案全部按实机重新校准**。

### F5 — 决策引擎（policy.py 拆分，游戏特定重写）
旧 828 行拆为 `policy/` 子包：
- `config.py`：PolicyConfig（所有阈值/坐标集中：min_screen_confidence=0.75、max_training_fail_rate=30、meditation_coin_threshold=60、ring_bonus、shop_whitelist、early_game_rounds=12、硬编码按钮坐标）。
- `engine.py`：TrainerPolicy 初始化 + decide 分发 + 所有 `_pending_*` 实例状态（relic/blessing/rest/commission/char_pending_confirm）。
- `training.py` / `character_select.py`(候选排序 + 双向滚动 cap=30) / `blessing.py` / `event.py`(关键词优先级 + DB→分支→关键词三级降级) / `relic_commission.py` / `shop_skill.py`。
- `event_db.py`：DEFAULT_EVENT_KEYWORDS + `_load_event_db` + `_match_event`(字符级模糊阈值 0.6)。
- **B 类规避**：所有"选 A→确认 A"两步操作用 `_pending_X` 状态记忆防翻转；列表搜索双向 + 重复点击计数（坑台账 B 类 12-16、🔴 高）。

### F6 — 鼠标执行（通用）
- `executor.py`：DryRun/PyAutoGui；`FAILSAFE=True` + 4 角急停（margin=120）；`_hover_move`/`_drag_scroll` 用底层 `mouse_event` 相对位移（pyautogui SetCursorPos 瞬移 Unity 不识别）；`repeat` 支持 ~5Hz 连点；`map_action_to_rect` 截图坐标→屏幕坐标。
- **C 类规避**：急停双保险（热键 F9 trigger_on_release + 鼠标 4 角），且在 OCR 之后、execute 之前再查一次（坑台账 C 类 17-19、🟡 中）。

### F7 — 检视器（设计模式通用，规则游戏特定）
"点开→读→点开→读"多帧循环收集选中后才显示的信息，在 live_loop 优先于 policy 调用：
- `training_inspector`（逐张点训练卡读增益，任一失败率≥阈值立即放弃其余去休息）、`commission_inspector`（读建议综合等级选 RANK+3 内最高阶）、`shop_inspector`（按效果关键词买，限购 1 件）、`blessing_inspector`（读子祝福数选最多，必须点击不能只悬停）。
- **G 类规避 #39**：解耦检视器调用顺序依赖（旧 CommissionInspector 需先经训练大厅读 character_rank，架构耦合点）。

### F8 — Screen 枚举与注册表（调度枢纽）
- `screens/base.py`：ScreenHandler Protocol（screen/priority/has_anchor/parse/decide）+ DelegatingScreenHandler(迁移期过渡，行为 1:1 零回归)。
- `screens/__init__.py`：`HANDLERS`(Screen→handler 全量映射)、`ANCHOR_HANDLERS`(按 priority 有序)，每 handler 声明 ocr_prefixes。
- **丢弃旧项目废弃半成品**：`journey_navigator.py`（已被 live_loop 状态机覆盖的废弃尝试）、旧 `logger.py`（与 logging_setup 重复）。

### F9 — CLI 主循环（live_loop）
单次迭代顺序（须严格复刻，见架构文档 §4）：急停检查 → F9 暂停 → 截图 → 缩放区域 → hybrid 分类 → UNKNOWN 处理(连续 ≤4 帧点中心推进、>4 帧 pause) → parse payload(走 HANDLERS) → 回合追踪 → 检视器优先 / policy 回落 → 重复点击防死循环 → 执行前再查急停 → activate → map_action_to_rect → execute → 智能睡眠(过场 0.35s 连点 / TRAINING_SELECT 0.5s / 其他默认 3s)。
- `round_tracker.py`：大厅无回合数靠日期变化计数，规范化失败返回 None 不前进。

### F10 — 离线回放与 Web UI
- `cli/offline_harness.py`：离线回放（demo/manifest/截图目录），无需游戏即可测识别与决策管线。
- `web/app.py`：Flask REST API + SSE 流式日志 + 全局单进程锁；`_run_command` 子进程包装 CLI；5 Tab（训练循环/截图窗口/区域标定 OCR/离线测试/单元测试）。

### F11 — 待解决项（新项目一开始就规划）
- **SKILL_SELECT 决策规则**（坑 #35：旧项目 policy 早期直接点✕退出不学技能，规则完全缺失）。
- **真实 OCR 准确率评估**（坑 #37：旧测试用假 OCR，真实准确率未评估）。
- SHOP/BATTLE/REGION_MOVE 坐标实跑核对（坑 #34）。

## 5. 非功能需求

- 代码规范：单文件 ≤ 400 行，嵌套 ≤ 4 层；外科手术式迁移（通用代码原样搬，不"顺手改进"）。
- 测试：迁移旧 148 单元测试，新增针对拆分子模块的测试；CI 可跑（NoopOcrEngine 让管线测试无需 GPU）。
- 配置资产：`config/regions/2560x1440.json`（主，330+ 区域，最游戏特定）、`config/characters.json`(name 须等于 OCR 清洗后名字)、`config/events.json`(部分标题与 OCR 不符→回退关键词)。

## 6. 历史坑规避清单（架构验收）

迁移时对照 `docs/现有项目历史坑台账.md`，下列高优先级类别作为架构评审硬卡点：
- 🔴 **A 分类误判**：从 outset 用 hybrid；每画面 `_has_X_signature`；陷阱画面独立 Screen+priority。
- 🔴 **B 死循环**：两步操作 `_pending_X` 状态机；列表双向 + 重复点击计数。
- 🔴 **D Unity 输入**：悬停/拖拽统一走 mouse_event 相对位移。
- 🟡 **C 急停**：双保险 + execute 前复查。
- 🟡 **E OCR 解析**：数字按场景写专门函数；按钮匹配用稳定前缀/独特词。
- ⚠️ **G 待解决**：SKILL_SELECT 决策、检视器解耦、真实 OCR 准确率评估。

## 7. 建议任务划分（18 个顶层任务）

1. F1 logging_setup + models + regions + image_regions + manifest 迁移
2. F2 capture 迁移（PrintWindow+DPI+全黑回退）
3. F2 ocr 迁移（PaddleOCR 多版本抽象）
4. F3 vision 迁移 + 颜色阈值重标定
5. F6 executor 迁移（急停双保险 + mouse_event）
6. F8 Screen 枚举 + screens/base ScreenHandler 协议
7. F8 screens 注册表（调度枢纽）
8. F3 classifier（hybrid + _has_X_signature 消歧）
9. F4 text_constants + ocr_reader + text_utils 文字工具层
10. F4 各画面 parser（character_select/blessing/relic/training 含 D-DAY/rest/event/commission/shop/region_move/battle）
11. config/regions 区域坐标 + config/characters + config/events
12. F5 policy/config + engine + _pending_X 状态机骨架
13. F5 policy 各决策（training/character_select 双向滚动/blessing/event/relic_commission/shop_skill）
14. F11 SKILL_SELECT 决策规则（坑 #35）
15. F7 检视器重写（解耦调用顺序 坑 #39）
16. F9 round_tracker + CLI live_loop 主循环
17. F10 CLI offline_harness + Flask Web UI
18. 单元测试迁移 + 实跑完整 run 验证（坑 #38）
