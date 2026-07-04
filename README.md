# Star Savior Trainer v2

Star Savior 训练自动化脚本（重构版）。重构自 `d:/chengfeng`，同游戏同功能。

## 状态：标准骨架（2026-06-27）

目录结构 + 占位模块已就位，**代码尚未迁入**。迁移与实现按 Task Master 开发计划推进。

## 架构契约
- **单屏状态机**：每帧识别画面，只跑匹配策略
- **OCR/CV 只产 Observation，绝不直接产 Action**
- **screens 注册表是唯一调度枢纽**

详见 [docs/现有项目架构分析.md](docs/现有项目架构分析.md) 与 [docs/现有项目历史坑台账.md](docs/现有项目历史坑台账.md)。

## 继续开发（新会话开场）
本仓库用 Task Master 管理开发计划。开**本目录**的会话（自动加载 CLAUDE.md），第一句：

> 继续 starsavior-trainer-v2 开发，看 Task Master 下一个任务。

## 技术栈
pyautogui · PaddleOCR(GPU) · OpenCV · Pillow · Flask · ctypes

## 目录结构
```
starsavior_trainer/
├── capture/ocr/vision/executor/regions/image_regions  # 通用框架（待迁入）
├── models.py manifest.py logging_setup.py              # 数据/回放/日志
├── screens/    # 画面处理器 + 注册表（调度枢纽）
├── policy/     # 决策引擎（由 policy.py 拆分）
├── inspectors/ # 检视器（多帧点击收集信息）
├── cli/        # 命令行入口
└── web/        # Flask Web UI
docs/           # 架构存档（迁移依据）
config/regions/ # 区域坐标配置（游戏特定）
```
