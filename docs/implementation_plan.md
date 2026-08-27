# 执行步骤

## 开发原则
- 每个阶段独立可验证，完成一个再进入下一个
- 每个阶段末尾有明确的检查点（Checkpoint）
- 每日开发结束后更新 dev_logs/

## Phase 1：基础设施（预计 1 轮）

### 1.1 环境初始化
- [x] 安装依赖：`python-docx`, `pywin32`, `PyPDF2`
- [x] 创建 `requirements.txt`
- [x] 创建项目包结构（`__init__.py`）

### 1.2 数据库层 `database/db.py`
- [x] `init_db()` — 自动建表
- [x] `create_user()` — 注册（密码加盐哈希）
- [x] `authenticate()` — 登录验证
- [x] `get_user()` — 获取用户信息
- [x] `update_api_key()` — 更新 API Key

**Checkpoint**: 数据库 CRUD 测试全部通过 ✅

### 1.3 工具层
- [x] `utils/convert_to_pdf.py` — DOCX → PDF（Word COM）。PPTX 不转 PDF，改用 python-pptx 直接提取。
- [x] `utils/deepseek_client.py` — DeepSeek API 封装（vision + text）


**Checkpoint**: 用测试文件验证转换和 API 调用

---

## Phase 2：数据提取（预计 1 轮）

### 2.1 演讲者提取 `extractors/speaker_extractor.py`
- [ ] 统一管道：文件 → PDF → DeepSeek Vision → Speaker 对象
- [ ] 内嵌图片提取（python-docx / python-pptx）
- [ ] 照片与 Speaker 关联存储

### 2.2 日程提取 `extractors/agenda_extractor.py`
- [ ] 图片 → DeepSeek Vision → List[AgendaItem]
- [ ] JSON 解析 + 错误处理

**Checkpoint**: 用 `资料/` 中真实文件验证提取结果准确性

---

## Phase 3：PPT 生成（预计 1-2 轮）

### 3.1 布局参数表 `ppt_generator.py`
- [ ] 定义 16:9 布局参数字典
- [ ] 定义超宽屏布局参数字典
- [ ] 每种页面类型（分隔页/履历页/内容页/过渡页）的坐标+字号

### 3.2 生成逻辑
- [ ] `add_background()` — 设置背景图
- [ ] `make_cover_slide()` — 封面
- [ ] `make_countdown_slides()` — 开场提醒（固定文案）
- [ ] `make_session_group()` — 环节组（分隔+履历+内容+过渡）
- [ ] `make_closing_slides()` — 总结
- [ ] `generate_ppt()` — 主入口

**Checkpoint**: 用模拟数据生成 PPT，对比参考模板格式

---

## Phase 4：用户界面（预计 1-2 轮）

### 4.1 登录系统 `ui/login_window.py`
- [ ] LoginWindow 类：用户名/密码/登录按钮
- [ ] RegisterWindow 类：注册表单 + API Key 输入
- [ ] 登录成功返回 user 对象

### 4.2 主界面 `ui/main_window.py`
- [ ] 演讲者资料区：文件选择 + 已识别列表
- [ ] 会议日程区：图片选择 + 识别结果表格（可编辑）
- [ ] 模板图片区：首页图/内容页图选择
- [ ] PPT 设置区：尺寸选择
- [ ] 一键生成按钮 + 进度回调

**Checkpoint**: 完整 UI 走通，所有交互正常

---

## Phase 5：集成与入口（预计 1 轮）

### 5.1 `main.py`
- [ ] 初始化数据库
- [ ] 启动登录窗口
- [ ] 登录成功打开主窗口

### 5.2 端到端测试
- [ ] 使用 `资料/` 中真实文件测试完整流程
- [ ] 对比生成 PPT 与参考模板
- [ ] 修复发现的问题

---

## Phase 6：Web 后端（进行中）

### 6.1 后端骨架
- [x] `main_web.py` — FastAPI + CORS + 上传/生成/状态/下载端点
- [x] `requirements_web.txt` — fastapi / uvicorn / python-multipart
- [x] `web/web_prototype.html` — 前端原型（待接入 API）

### 6.2 核心逻辑迁移
- [x] extractors 支持 bytes 输入（保持本地路径兼容）
- [x] `tasks.py` — BackgroundTasks 任务层 + 进度上报 + 日志
- [x] `main_web.py` 接入真实生成管线
- [x] 上传清单持久化（manifest.json）

### 6.3 待办
- [x] 任务表/上传表迁移到 DB（SQLAlchemy ORM + Alembic，SQLite/PostgreSQL）
- [x] Web 用户认证（Cookie 会话 + api_key 服务端按账号读取 + 管理员账户管理）
- [x] 前端原型接入 API 调用
- [x] 真实端到端验证（真 Key 全流程）

### 6.4 前端对接（web/web_prototype.html 单文件 SPA）
- [x] 文件上传（拖拽/点击，日程/演讲者/首页背景/内容页背景）→ `/api/upload`
- [x] 生成提交（Fetch JSON）→ `/api/generate`，轮询 `/api/status`（2s，页面不阻塞）
- [x] 完成后自动下载 + 结果卡片；失败显示错误横幅（可一键重试）
- [x] 错误处理与 toast 提示；API Key / OCR Key / 后端地址存 localStorage
- [x] 左侧历史记录改为本机真实记录（localStorage，可重新下载/删除/搜索/清空）
- [x] 后端连通性检测徽标（页面加载时自动探测）
- [x] 后端静态托管前端：`GET /` 重定向到 `/web/web_prototype.html`（StaticFiles）
- [x] 账户设置独立为 `web/settings.html`（API Key / OCR Key / 后端地址 + 连通性检测），主页右上角「账户设置」跳转进入
- [x] 登录/注册页 `web/login.html`：`GET /` 先进入登录页，已登录自动跳主页；首个注册账户自动成为管理员
- [x] 会话认证：httpOnly Cookie（内存态，服务重启需重新登录）；上传/生成/状态/下载均需登录
- [x] 生成时 api_key 服务端按账号读取（账号已配置时优先，回退请求携带的 Key）；设置页 Key 同步保存到账户
- [x] 管理员用户管理页 `web/admin.html`：账户列表、新建、重置密码、授予/取消管理员、删除（主页对管理员显示入口）
- [x] 背景槽位支持上传 .pptx 模版：`POST /api/template/background` 提取首页/内容页背景（`extractors/ppt_background.py`，zip+xml 固定代码），两槽位自动填充，图片直传方式保留
- [x] 步骤 2 资料解析与编辑：手动「解析资料」按钮 → `POST /api/parse`（AI 解析日程/演讲者，可编辑卡片增删改、更换照片）；生成时携带编辑后数据（`/api/generate` 可选 `agenda_items`/`speakers`）跳过 AI 提取、无需 Key；文件变更/重置时解析结果失效

---

## 每日开发日志规范

每天工作结束后在 `dev_logs/YYYY-MM-DD.md` 记录：
```markdown
# YYYY-MM-DD

## 完成事项
- [x] xxx

## 待办事项
- [ ] xxx

## 遇到的问题
- xxx
```
