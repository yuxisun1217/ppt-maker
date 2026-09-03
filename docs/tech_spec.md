# 技术规范

## 技术栈

| 层 | 技术 | 版本要求 |
|----|------|---------|
| Web 后端 | FastAPI + uvicorn（单 worker） | >= 0.115 / >= 0.30 |
| Web 前端 | 原生 HTML/JS + Tailwind（单文件，web/ 目录） | |
| 数据库 | SQLAlchemy 2.0 ORM（SQLite 开发 / PostgreSQL 生产，Alembic 迁移） | |
| PPT 生成 | python-pptx | >= 1.0.2 |
| DOCX 解析 | python-docx | 提取文字与内嵌图片 |
| PPTX 解析 | python-pptx | 直接提取文字+图片 |
| PDF 解析 | PyPDF2 | >= 3.0.0 |
| OCR | OCR.space API | 日程图片文字全图提取 |
| AI 集成 | DeepSeek API（仅文本） | 图片经 OCR 转文字后处理 |
| 图片处理 | Pillow / OpenCV（人脸检测裁剪） | >= 11.0.0 / >= 4.8 |

## 项目结构

```
d:\ppt_maker\ppt_maker\
├── CLAUDE.md                    # 项目指引
├── main_web.py                  # Web 后端入口（FastAPI，API + 静态前端一体）
├── requirements.txt             # 依赖（Windows/Linux 通用）
├── Dockerfile / docker-compose.yml / start_dev.sh / env.example  # 部署与本地启动
├── alembic/                     # 数据库迁移
├── web/                         # 前端页面（login / admin / settings / web_prototype）
├── docs/                        # 项目文档
├── dev_logs/                    # 开发日志（每日记录）
├── database/
│   ├── db.py                    # 数据访问层（SQLAlchemy）
│   └── models.py                # ORM 模型：User/Speaker/Task/Upload/SystemSetting
├── extractors/
│   ├── speaker_extractor.py     # 演讲者提取（含人脸检测裁剪）
│   └── agenda_extractor.py      # 日程识别
├── ppt_generator.py             # PPT 生成（固定布局代码）
├── tasks.py                     # 后台生成任务（进程内）
└── utils/
    ├── crypto.py                # 共享 Key Fernet 加解密
    ├── deepseek_client.py       # DeepSeek API
    └── ppt_template_extractor.py # 模板背景图提取
```

## 数据流

```
日程图片 ──→ OCR.space ──→ DeepSeek 结构化 ──→ 解析结果（前端可编辑）
DOCX ──→ python-docx（文字+图片提取）──→ DeepSeek ──→ 演讲者数据 ──→ ppt_generator ──→ PPTX
PPTX ──→ python-pptx（文字+图片提取）──→ DeepSeek ──→ 演讲者数据
PDF  ──→ PyPDF2 ──→ DeepSeek ──→ 演讲者数据
```
说明：日程图片经 OCR 转文字后由 DeepSeek 结构化；演讲者资料按格式用
对应库直接提取文字/图片，无需 PDF 中间转换。

## 数据库 Schema

ORM 层为 SQLAlchemy 2.0（`database/models.py`），开发/测试用 SQLite（`app_data.db`），
生产支持 PostgreSQL。连接串由 `.env` 的 `DATABASE_URL` 配置（见 `.env.example`）。
迁移用 Alembic（`alembic upgrade head`）；SQLite 开发库由 `init_db()` 自动建表并回填新增列。

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    api_key       TEXT DEFAULT '',
    ocr_api_key   TEXT DEFAULT '',
    created_at    TIMESTAMP DEFAULT now(),
    updated_at    TIMESTAMP DEFAULT now()
);

CREATE TABLE speakers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    photo_path  TEXT DEFAULT '',
    bio         TEXT DEFAULT '',
    bio_en      TEXT DEFAULT '',
    institution TEXT DEFAULT '',
    title       TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT now(),
    updated_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE tasks (          -- Web 生成任务
    id          TEXT PRIMARY KEY,        -- 32位hex UUID
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    task_status TEXT DEFAULT 'pending',  -- pending/running/done/failed
    progress    INTEGER DEFAULT 0,
    message     TEXT DEFAULT '',
    options     TEXT,                    -- JSON（不含 api_key 等敏感字段）
    pptx_path   TEXT,
    error       TEXT,
    created_at  TIMESTAMP DEFAULT now(),
    updated_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE uploads (        -- Web 上传文件记录
    id          TEXT PRIMARY KEY,        -- 32位hex UUID
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    filename    TEXT DEFAULT '',
    path        TEXT NOT NULL,
    size        INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT now(),
    updated_at  TIMESTAMP DEFAULT now()
);
```

密码使用 SHA256 + 16 字节随机 salt 哈希。

## API 规范

### DeepSeek API
- Endpoint: `https://api.deepseek.com/chat/completions`
- Model: `deepseek-chat`（纯文本；V4 API 不支持 image_url 输入，日程图片走 OCR.space）
- Response format: `json_object`

### Web 端点（main_web.py，除登录/注册外均需会话登录）

| 端点 | 说明 |
|------|------|
| `POST /api/upload` | 多文件上传（multipart，字段 `files`），返回 `{files: [{file_id, filename, size}]}` |
| `POST /api/template/background` | 上传 .pptx 模版，提取首页/内容页背景图 |
| `POST /api/parse` | AI 解析日程/演讲者（同步 `def`，跑在线程池）。body：`agenda_file_id` + `speaker_file_ids` + 可选 `api_key`/`ocr_api_key`（账号已配置时优先）。返回 `{agenda: [...], speakers: [{name,title,institution,bio,bio_en,photo}]}`，演讲者照片落盘 web_uploads 并登记 uploads 表，`photo` 为 `{file_id, filename, preview, original_file_id, original_filename}` 或 null；照片经头部特写裁剪时，`original_file_id` 指向裁剪前的完整照片（未裁剪为空） |
| `GET /api/upload/{file_id}` | 下载上传文件（照片等）。校验归属：`user_id != 当前用户` → 403；未知 id / 文件已清理 → 404 |
| `POST /api/generate` | 创建生成任务。body 在原有字段外新增可选 `agenda_items` / `speakers`（编辑后的数据，`photo_file_id` 指向照片上传）；提供后对应步骤跳过 AI 提取、无需 api_key |
| `GET /api/status/{task_id}` | 任务进度；`options` 含编辑后的日程/演讲者数据（api_key/ocr_api_key 已剥离） |
| `GET /api/download/{task_id}` | 下载生成的 PPTX |

- `/api/status` 与 `/api/download` 校验任务归属：`task.user_id != 当前用户` → 403
- `/api/parse` 与 `/api/generate` 的 Key 覆盖规则一致：账号已配置优先，回退请求携带的 Key
- 解析失败统一 400：`日程解析失败: {e}` / `演讲者解析失败（{文件名}）: {e}`

### 关键约束
- API Key 从当前登录用户获取，不硬编码
- 每次调用设置 `temperature=0.1` 保证输出稳定性
- 超时时间 120s
