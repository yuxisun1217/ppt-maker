# 技术规范

## 技术栈

| 层 | 技术 | 版本要求 |
|----|------|---------|
| GUI | tkinter + ttk | Python 内置 |
| 数据库 | SQLite (sqlite3) | Python 内置 |
| PPT 生成 | python-pptx | >= 1.0.2 |
| 格式转换 | pywin32 (Word COM) | DOCX → PDF |
| DOCX 解析 | python-docx | 提取内嵌图片 |
| PPTX 解析 | python-pptx | 直接提取文字+图片 |
| PDF 解析 | PyPDF2 | >= 3.0.0 |
| OCR | pytesseract + Tesseract-OCR 5.4 | 日程图片文字全图提取（海报式图片布局检测模型不可靠） |
| AI 集成 | DeepSeek API（仅文本） | 不支持 Vision，图片经 OCR 转文字后处理 |
| AI 集成 | DeepSeek API | chat/completions |
| 图片处理 | Pillow | >= 11.0.0 |

## 项目结构

```
d:\ppt_maker\
├── CLAUDE.md                    # 项目指引
├── main.py                      # 入口
├── requirements.txt             # 依赖
├── docs/                        # 项目文档
│   ├── requirements.md
│   ├── tech_spec.md
│   ├── design_spec.md
│   └── implementation_plan.md
├── dev_logs/                    # 开发日志（每日自动生成）
├── database/
│   └── db.py                    # SQLite 操作
├── extractors/
│   ├── speaker_extractor.py     # 演讲者提取
│   └── agenda_extractor.py      # 日程识别
├── ppt_generator.py             # PPT 生成
├── ui/
│   ├── login_window.py          # 登录/注册
│   └── main_window.py           # 主界面
└── utils/
    ├── convert_to_pdf.py        # DOCX/PPTX → PDF
    └── deepseek_client.py       # DeepSeek API
```

## 数据流

```
DOCX ──→ Word COM ──→ PDF ──→ DeepSeek Vision ──┐
PPTX ──→ python-pptx(文字+图片提取) ──→ DeepSeek text ──┼──→ Speaker 对象
PDF  ──→ DeepSeek Vision ──────────────────────────┘
```
说明：DOCX 先转 PDF 再视觉识别；PPTX 用 python-pptx 直接提取（COM 不可靠）；PDF 直接视觉识别。

## 数据库 Schema

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    api_key       TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE speakers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    photo_path TEXT DEFAULT '',
    bio        TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

密码使用 SHA256 + 16 字节随机 salt 哈希。

## API 规范

### DeepSeek API
- Endpoint: `https://api.deepseek.com/chat/completions`
- Model: `deepseek-chat`（支持 vision）
- 图片格式：Base64 Data URL（`data:image/png;base64,...`）
- Response format: `json_object`

### 关键约束
- API Key 从当前登录用户获取，不硬编码
- 每次调用设置 `temperature=0.1` 保证输出稳定性
- 超时时间 120s
