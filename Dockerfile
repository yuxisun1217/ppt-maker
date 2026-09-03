# syntax=docker/dockerfile:1
# 会议串场 PPT 生成器 — Web 版镜像（FastAPI 后端 + 静态前端一体）
# 构建：docker build -t pptmaker-web .
# 使用：docker compose up -d --build（见 docker-compose.yml）

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先复制依赖清单并安装（利用镜像层缓存；后续只改代码不重装依赖）
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# 上传文件、生成结果与运行日志（数据库表在 Postgres，文件落此目录）
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/web/login.html', timeout=5)" || exit 1

# Postgres 时先执行 alembic 迁移；SQLite 时由应用启动逻辑 init_db() 建表。
# 注意：登录会话与后台任务均在进程内实现，必须保持单 worker（勿加 --workers）
CMD ["sh", "-c", "case \"$DATABASE_URL\" in postgres*) alembic upgrade head;; esac && exec uvicorn main_web:app --host 0.0.0.0 --port 8000"]
