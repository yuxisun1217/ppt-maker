# CLAUDE.md — 会议串场 PPT 生成器

## 项目概述
Web 应用（FastAPI 后端 + 单文件前端），根据会议日程图片和演讲者资料文件
（DOCX/PDF/PPTX），通过 OCR + DeepSeek AI 提取结构化数据，自动生成中英双语
会议串场 PPT。桌面版（main.py/ui/）已移除，仓库仅保留 Web 版。

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| README | [README.md](README.md) | 项目简介、Web 版部署与运行说明 |
| 产品需求 | [docs/PRD.md](docs/PRD.md) | 产品定位、功能需求（P0-P2）、业务规则 |
| 开发需求 | [docs/requirements.md](docs/requirements.md) | 功能需求、输入输出规格 |
| 技术规范 | [docs/tech_spec.md](docs/tech_spec.md) | 技术栈、项目结构、DB Schema、API 规范 |
| 设计规范 | [docs/design_spec.md](docs/design_spec.md) | UI 配色、组件规范、PPT 输出规范 |
| 执行步骤 | [docs/implementation_plan.md](docs/implementation_plan.md) | 分阶段开发计划 + Checkpoint |
| 开发日志 | [dev_logs/](dev_logs/) | 每日开发记录 |

## 工作说明

### 开发前
1. 阅读 `docs/implementation_plan.md` 确认当前阶段
2. 检查上一次的 `dev_logs/` 了解进度和遗留问题
3. 明确本轮要完成的具体任务

### 开发中
1. 按 Phase 顺序推进，完成一个 Checkpoint 验证后再进入下一个
2. 不要一次性修改过多文件，保持每轮改动范围可控
3. 新增依赖时同步更新 `requirements.txt`
4. 发现设计偏离时更新对应的 docs 文件

### 开发后
1. 在 `dev_logs/YYYY-MM-DD.md` 记录当日工作
2. 更新 `docs/implementation_plan.md` 中的 checkbox 状态
3. 如有架构变更，同步更新 `docs/tech_spec.md`

### 关键约束
- PPT 生成用 python-pptx 固定代码，不用 AI 生成内容
- 密码用 SHA256+Salt 哈希，不存明文
- DeepSeek API Key 由用户提供，关联到用户账号
- 16:9 和超宽屏各维护独立的布局参数表
- 参考模板：`资料/322串场-中英.pptx`（超宽屏）、`资料/串场-0314-重庆-主会场.pptx`（16:9）
