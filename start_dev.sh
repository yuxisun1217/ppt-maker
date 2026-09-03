#!/usr/bin/env bash
# ============================================================
# 本地开发一键启动脚本（Windows Git Bash / macOS / Linux）
#   ./start_dev.sh
# 首次运行自动完成：创建虚拟环境 → 安装依赖 → 生成 .env →
# 以热重载模式启动开发服务器（http://127.0.0.1:8000）
# ============================================================
set -e
cd "$(dirname "$0")"

# 1. 定位 Python
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "错误：未找到 Python，请先安装 Python 3.10+ 并加入 PATH" >&2
  exit 1
fi

# 2. 虚拟环境
if [ ! -d .venv ]; then
  echo "[1/4] 创建虚拟环境 .venv"
  "$PY" -m venv .venv
fi
# 激活（Windows: Scripts/；macOS/Linux: bin/）
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate

# 3. 依赖
echo "[2/4] 安装依赖（首次较慢，请耐心等待）"
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

# 4. 生成 .env（默认 SQLite 本地库，无需修改即可运行）
echo "[3/4] 检查 .env"
if [ ! -f .env ]; then
  cp env.example .env
  echo "      已从 env.example 生成 .env（SQLite 本地库）"
else
  echo "      .env 已存在，跳过"
fi

# 5. 启动（热重载；数据库表由应用启动时自动创建）
echo "[4/4] 启动开发服务器 http://127.0.0.1:8000 （Ctrl+C 退出）"
exec python -m uvicorn main_web:app --host 127.0.0.1 --port 8000 --reload
