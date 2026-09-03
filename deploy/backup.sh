#!/usr/bin/env bash
# ============================================================
# 会议串场 PPT 生成器 — 每日备份脚本（在仓库根目录执行）
#   ./deploy/backup.sh                手动执行
#   BACKUP_DIR=/opt/ppt-backups ./deploy/backup.sh   自定义目标目录
#   BACKUP_DIR=... KEEP=30 ./deploy/backup.sh        自定义保留份数
# 备份内容：
#   1) PostgreSQL 逻辑导出（pg_dump 一致性快照，无需停服务）
#   2) web_data 卷打包（上传照片 / 生成的 PPT / data/encryption.key）
#   3) .env（数据库密码 + ENCRYPTION_KEY，恢复必需）
# 默认保留最近 KEEP=14 份。详细备份/恢复说明见 docs/backup_restore.md
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."   # 仓库根（含 docker-compose.yml）

STAMP=$(date +%F-%H%M)
DEST="${BACKUP_DIR:-/opt/ppt-backups}"
KEEP="${KEEP:-14}"
mkdir -p "$DEST"

echo "[$(date '+%F %T')] 备份开始 -> $DEST"

# 1. 数据库逻辑导出
docker compose exec -T postgres pg_dump -U pptmaker pptmaker > "$DEST/db_$STAMP.sql"
gzip "$DEST/db_$STAMP.sql"
echo "  db_$STAMP.sql.gz done"

# 2. 应用文件卷打包（自动探测 web 容器挂载在 /app/data 的卷名）
WEB_CTR=$(docker compose ps -q web)
if [ -z "$WEB_CTR" ]; then
  echo "错误：web 容器未运行，跳过文件备份" >&2
else
  VOL=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' "$WEB_CTR")
  if [ -z "$VOL" ]; then
    echo "错误：未找到 web 容器的 /app/data 卷，跳过文件备份" >&2
  else
    docker run --rm -v "$VOL":/data -v "$DEST":/backup alpine \
      tar czf "/backup/web_data_$STAMP.tgz" -C /data .
    echo "  web_data_$STAMP.tgz done (卷 $VOL)"
  fi
fi

# 3. .env（含数据库密码与加密密钥）
if [ -f .env ]; then
  cp .env "$DEST/env_$STAMP"
  echo "  env_$STAMP done"
else
  echo "警告：未找到 .env，跳过" >&2
fi

# 4. 清理旧备份（各保留最近 KEEP 份）
cleanup() {
  local pattern="$1"
  ls -1t "$DEST"/$pattern 2>/dev/null | tail -n "+$((KEEP + 1))" | xargs -r rm -f
}
cleanup 'db_*.sql.gz'
cleanup 'web_data_*.tgz'
cleanup 'env_*'

echo "[$(date '+%F %T')] 备份完成"
