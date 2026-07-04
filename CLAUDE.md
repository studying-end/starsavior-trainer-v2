# 项目：Star Savior Trainer v2

训练自动化脚本（重构版），**重构自 `d:/chengfeng`** —— 同游戏同功能。架构依据见 `docs/`。

## 核心架构契约（不可违背）
- **单屏状态机**：每帧识别当前画面类别，只跑匹配该画面的策略；绝不在错误画面点"看似合理"的按钮。
- **OCR/CV 只产生 Observation，绝不直接决定 Action**。识别层（classifier/screen_reader）与决策层（policy）解耦。
- **screens 注册表是唯一调度枢纽**：分类、决策、payload 读取三处统一走 `screens.HANDLERS`，加画面只动一处。

## 技术栈
pyautogui + RapidOCR(ONNX Runtime GPU，PP-OCRv4) + OpenCV + Pillow + Flask + ctypes(Windows 窗口/输入)。注：原 PaddleOCR+paddlepaddle-gpu 方案在实机验证中废弃（2.7.3 乱码 / 3.x 撞 beta PIR 崩溃），见 docs/设计方案.md §10。

## 当前阶段（2026-06-28）
**迁移进度 17/18**（131 测试全过）：通用框架 + 数据层 + screens 21 parser + policy 决策（mixin）+ classifier（3 文件）+ handler 注册（**决策链路闭环**）+ 4 检视器 + round_tracker + cli live_loop（拆 pause/blue_parsers/runtime/live_loop 4 文件）+ SKILL_SELECT 决策 + Web UI（offline_harness + Flask app/process_manager）全部就位。
- **新会话接手先读 [docs/迁移交接.md](docs/迁移交接.md)** —— 精确进度 + T18 待办 + 操作手册 + import 关系。
- 当前 in-progress：无。pending：T18（单测迁移 + 实跑验证，next_task 指向 —— 最终任务）。T16 + T14 + T17 已完成。
- 新会话第一句：`继续 starsavior-trainer-v2 开发，看 Task Master 下一个任务`（next_task 指向 T18）。
- `.taskmaster/config.json` LLM provider 已设 claude-code；若 `expand_task`/`parse_prd` 报 `PERPLEXITY_API_KEY` 缺失，重启 MCP 让 config 生效。

## 关键文档
- `docs/迁移交接.md` — **新会话接手先读**：精确进度 + T18 待办 + 操作手册
- `docs/新项目技术设计.md` — 新项目分层/数据流/模块接口/迁移映射/坑规避索引（**T2 起开发依据**）
- `docs/变更记录.md` + `docs/设计方案.md` — **非 1:1 迁移的改动**：变更记录（改了什么）+ 设计方案（方案/理由），每次新增/优化/修改都更新
- `docs/现有项目架构分析.md` — 旧项目模块职责、数据流、超大文件拆分方案、可复用/重写清单
- `docs/现有项目历史坑台账.md` — 39 个历史坑 + 新项目规避优先级（务必先读，避免重踩）

---

# 通用
- 优先选择编辑而非重写整个文件
- 输出追求简洁，但推理过程必须详尽
- 任务完成后最多 5 行变更摘要
- 不要复述题目、科普背景
- 除非被编辑过，不要重复读已读文件
- 未经要求，禁止生成额外说明文档
- **非 1:1 迁移（新增/优化/修改逻辑·结构·文案）须同步更新 `docs/变更记录.md`（改了什么）+ `docs/设计方案.md`（方案理由）；纯搬迁不记录**

# 代码规范
- 单文件不超过 400 行，超了就拆
- 嵌套不超过 4 层

---

# 行为准则（Karpathy）
> 降低 LLM 常见编码错误的行为规范。倾向"稳妥"而非"求快"。琐碎任务可凭判断取舍。

## 1. Think Before Coding — 先思考再编码
**不假设、不藏疑惑、主动摆出权衡。** 实现前：
- 明确说出你的假设；不确定就问。
- 存在多种解读时，全部列出，不要默默选一个。
- 存在更简单的方案时要说出来；必要时反驳需求。
- 有不清楚的地方，停下来，指出困惑，再问。

## 2. Simplicity First — 简洁优先
**用解决问题的最少代码，不做任何投机性设计。**
- 不做要求之外的功能。单次使用的代码不抽象。
- 不做未被要求的"灵活性""可配置性"。不为不可能的场景写错误处理。
- 若 200 行能压成 50 行，就重写。
- 自问："资深工程师会说这过度复杂吗？"若是，就简化。

## 3. Surgical Changes — 外科手术式修改
**只动必须动的，只清理自己造成的残留。**
- 不"顺手改进"相邻代码/注释/格式。不重构没坏的东西。匹配既有风格。
- 发现无关死代码，提一句不要删。你的改动产生的孤立项要清除；既有死代码除非被要求不动。
- 检验标准：每一行改动都能直接追溯到用户的请求。

## 4. Goal-Driven Execution — 目标驱动执行
**先定可验证的成功标准，循环验证到通过。** 把任务转成可验证目标：
- "加校验" → 为非法输入写测试再让其通过
- "修 bug" → 写复现测试再让其通过
- "重构 X" → 确保改前改后测试都通过

多步任务先给简短计划：`1. [步骤] → 验证：[检查]`。强成功标准让你能独立循环推进。
