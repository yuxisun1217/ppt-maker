# 会议串场 PPT 生成器

根据会议日程图片和演讲者资料文件（DOCX/PDF/PPTX），通过 DeepSeek AI 提取
结构化数据，自动生成中英双语会议串场 PPT。

本仓库为 **Web 版**：FastAPI 后端 + 单文件前端，账号登录、文件上传、AI 解析编辑、生成下载。
（早期桌面版 `main.py`/`ui/` 已移除，共享同一套提取与生成管线。）

## 功能特性

- 日程图片 OCR + DeepSeek 结构化解析（环节、时间、演讲者、主持）
- 演讲者资料批量解析：姓名、医院、中文/英文履历、照片自动提取
- 照片智能裁剪（多级联人脸检测投票；合照与不确定情况保守保留原图）
- 解析结果在线编辑，生成时直接使用编辑后的数据
- 中英双语 / 纯中文两种语言模式；16:9 与超宽屏两套布局
- 账号体系：注册 / 登录 / 管理员用户管理，DeepSeek API Key 按账号隔离存储
- 共享 API Key：管理员可配置全站共享的 DeepSeek / OCR Key（加密落库），
  用户未配置个人 Key 时自动使用；仅管理员可见、可修改
- 后台生成任务：进度查询、完成后下载 PPTX

## 目录结构

```
main_web.py            Web 后端（FastAPI，API + 静态前端一体）
web/                   前端页面（login/admin/settings/web_prototype.html）
ppt_generator.py       PPT 生成（固定布局代码，非 AI 生成）
extractors/            日程/演讲者/模板背景提取
database/              SQLAlchemy 数据层（SQLite 开发 / PostgreSQL 生产）
tasks.py               后台生成任务
Dockerfile             Web 版镜像
docker-compose.yml     Web + PostgreSQL + Redis 编排
start_dev.sh           本地开发一键启动
env.example            环境变量模板（复制为 .env）
docs/                  产品需求、技术规范、设计规范、执行计划
```

## 快速开始（本地开发）

前置要求：Python 3.10+（Windows 建议使用 Git Bash 运行脚本）。

```bash
./start_dev.sh
```

脚本会自动完成：创建虚拟环境 `.venv` → 安装依赖（Windows/Linux 通用）→
从 `env.example` 生成 `.env`（默认 SQLite 本地库）→
以热重载模式启动服务。

浏览器打开 <http://127.0.0.1:8000>，首次使用先注册账号（第一位注册的用户
会被自动设为管理员；「账户设置」中填入 DeepSeek API Key 后即可使用）。

### 手动启动

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows；macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env                  # 首次
uvicorn main_web:app --host 127.0.0.1 --port 8000 --reload
```

## Docker 部署

前置要求：Docker（含 Compose 插件）。

```bash
# 1.（可选）修改生产密码
#    编辑 .env（不存在则从 env.example 复制），设置 POSTGRES_PASSWORD

# 2. 构建并启动（Web + PostgreSQL + Redis）
docker compose up -d --build

# 3. 查看日志 / 状态
docker compose logs -f web
docker compose ps
```

浏览器打开 <http://localhost:8000> 注册账号即可使用。

说明：

- 容器内使用 **PostgreSQL**（`DATABASE_URL` 由 compose 自动注入，
  优先级高于本地 `.env`），启动时自动执行 alembic 迁移；
- `web_data` 卷持久化上传文件、生成的 PPT 与运行日志，删除容器不丢数据；
- **Redis** 已随 compose 启动但当前版本尚未使用（登录会话与后台任务均在
  进程内实现），预留用于后续接入任务队列；
- 镜像健康检查请求 `/web/login.html`，`docker compose ps` 中 `healthy`
  即为就绪。

## 环境变量

完整模板见 [`env.example`](env.example)，复制为 `.env` 后按需修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///app_data.db` | SQLAlchemy 连接串；生产建议 `postgresql+psycopg2://user:pass@host:5432/db` |
| `POSTGRES_PASSWORD` | `pptmaker`（compose 兜底） | compose 中 PostgreSQL 初始密码 |
| `REDIS_URL` | `redis://redis:6379/0` | 预留，当前版本未使用 |
| `ENCRYPTION_KEY` | 自动生成并落盘 `data/encryption.key` | 共享 API Key 的数据库加密密钥（Fernet）；生产建议显式配置并备份 |

## 数据与持久化

| 数据 | 本地开发 | Docker 部署 |
|------|----------|-------------|
| 数据库（用户/任务/上传记录） | `app_data.db`（SQLite） | PostgreSQL（`postgres_data` 卷） |
| 上传文件 | `data/web_uploads/` | `web_data` 卷内同路径 |
| 生成的 PPT | `data/web_output/` | `web_data` 卷内同路径 |
| 运行日志 | `logs/` | `web_data` 卷内同路径 |

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/register` `/api/login` `/api/logout` | 注册 / 登录 / 退出（Cookie 会话） |
| GET | `/api/me` | 当前用户信息 |
| POST | `/api/account/keys` | 更新本人 DeepSeek / OCR API Key |
| GET/PUT | `/api/settings/shared-keys` | 共享 API Key 读取/更新（仅管理员，密文落库，两项必填） |
| GET | `/api/settings/shared-keys-status` | 共享 Key 配置状态（任何登录用户，仅返回是否已配置） |
| GET/POST | `/api/users` | 用户列表 / 创建用户（管理员） |
| DELETE | `/api/users/{id}` | 删除用户（管理员） |
| POST | `/api/users/{id}/password` `/api/users/{id}/admin` | 重置密码 / 设置管理员 |
| POST | `/api/upload` | 上传文件（日程/演讲者资料/照片/背景图） |
| POST | `/api/parse` | AI 解析日程与演讲者资料，返回可编辑结果 |
| POST | `/api/generate` | 提交生成任务（可携带编辑后的数据） |
| GET | `/api/status/{task_id}` | 查询生成进度 |
| GET | `/api/download/{task_id}` | 下载生成的 PPTX |
| POST | `/api/template/background` | 从模板 PPTX 提取背景图 |
| GET | `/` `/web/*` | 前端页面（`/` 跳转登录页） |

## 注意事项

- **必须保持单 worker**：登录会话（内存）与后台生成任务均在进程内实现，
  多 worker/多实例部署会导致会话失效与任务丢失；水平扩展需先接入
  Redis + 外部任务队列。
- **DeepSeek API Key 由用户提供**，关联到账号存储（`users.api_key`），
  解析/生成时服务端按账号读取，不在前端持久化。
- **共享 API Key**（管理员在「用户管理」页配置）：全体用户共享使用，
  Key 解析优先级为 账号个人 Key > 请求携带 > 共享 Key；
  共享 Key 经 Fernet 加密后存储于 `system_settings` 表（密文），
  仅管理员可通过接口读取明文；任务记录不落任何明文 Key。
  共享 DeepSeek 与 OCR.space Key **均为必填**——任一缺失时，
  所有用户登录后会在页面上收到橙色警告提示（请管理员配置）。
- 密码使用 SHA256+盐 哈希存储，不保存明文。
- 生成 PPT 使用固定布局代码（python-pptx），内容不依赖 AI 二次生成。

## 相关文档

| 文档 | 说明 |
|------|------|
| [docs/PRD.md](docs/PRD.md) | 产品定位、功能需求、业务规则 |
| [docs/requirements.md](docs/requirements.md) | 功能需求、输入输出规格 |
| [docs/tech_spec.md](docs/tech_spec.md) | 技术栈、DB Schema、API 规范 |
| [docs/design_spec.md](docs/design_spec.md) | UI 配色、组件与 PPT 输出规范 |
| [docs/implementation_plan.md](docs/implementation_plan.md) | 分阶段开发计划与 Checkpoint |
| [dev_logs/](dev_logs/) | 每日开发记录 |
