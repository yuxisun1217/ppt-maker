# 备份与恢复手册

适用于 Docker 部署（阿里云 ECS + docker compose）。仓库内脚本：
`deploy/backup.sh`（随版本管理，`git pull` 后即为最新）。

## 一、需要备份什么

| 数据 | 位置 | 丢失后果 |
|------|------|---------|
| PostgreSQL 数据 | `postgres_data` 卷 | 用户、任务记录、共享 Key 密文全部丢失 |
| 应用文件 | `web_data` 卷 | 上传照片、生成的 PPT、`data/encryption.key`（丢失则共享 Key 密文永久无法解密） |
| 环境变量 | `/opt/ppt-maker/.env` | 数据库密码 + `ENCRYPTION_KEY`，恢复时必需 |

备份三者的组合才可完整恢复；任一缺失都会导致部分数据无法找回。

## 二、日常备份

### 1. 手动执行

```bash
cd /opt/ppt-maker
./deploy/backup.sh
```

输出三份文件到 `/opt/ppt-backups/`（默认）：

```
db_2026-09-03-0317.sql.gz     # PostgreSQL 逻辑导出
web_data_2026-09-03-0317.tgz  # web_data 卷打包
env_2026-09-03-0317           # .env 副本
```

默认保留最近 14 份，自动清理更早的。可调整：

```bash
BACKUP_DIR=/data/backups KEEP=30 ./deploy/backup.sh
```

### 2. 定时任务（cron）

```bash
crontab -e
```

追加一行（每天凌晨 3:17 执行，日志落盘）：

```
17 3 * * * /opt/ppt-maker/deploy/backup.sh >> /var/log/ppt-backup.log 2>&1
```

说明：

- `pg_dump` 为事务一致性快照，备份期间**无需停止服务**；
- `web_data` 卷打包同样在线完成（照片/PPT 写入后不再变动）；
- 首次执行会拉取 `alpine` 镜像（约 3MB），之后秒级完成；
- 数据库体积小（几 MB），每日全量备份足够，无需增量策略。

### 3. 异地备份（强烈建议）

服务器磁盘故障时本地备份一并丢失，至少保留一份离线副本：

**方式 A：同步到阿里云 OSS**

```bash
# 下载并配置 ossutil 后（https://help.aliyun.com/zh/oss/developer-reference/install-ossutil）
ossutil64 cp -r /opt/ppt-backups oss://<你的桶>/ppt-backups/ --update
```

把这条命令追加到同一 cron 行（`&&` 连接）即可每日自动同步。

**方式 B：每周手动拉回本地电脑**

```bash
scp -r root@<ECS公网IP>:/opt/ppt-backups .
```

### 4. 补充保险：阿里云磁盘自动快照

ECS 控制台 → 快照 → 自动快照策略：对整个数据盘每日快照，
保留 7 天。与逻辑备份互为兜底（快照粗粒度、恢复快但不可单表导出）。

## 三、恢复步骤

恢复前先确认 compose 环境就绪：`cd /opt/ppt-maker`。

### 1. 恢复数据库

```bash
gunzip -c /opt/ppt-backups/db_YYYY-MM-DD-HHMM.sql.gz \
  | docker compose exec -T postgres psql -U pptmaker pptmaker
```

> 若目标库已有数据，先清空再导入（`--clean` 方式）：
> `gunzip -c ... | docker compose exec -T postgres psql -U pptmaker -d postgres`
> 然后 `DROP DATABASE pptmaker; CREATE DATABASE pptmaker;` 再按上面命令导入。
> 全新部署（数据卷已删除）时直接导入即可。

### 2. 恢复应用文件卷

```bash
docker run --rm -v ppt-maker_web_data:/data -v /opt/ppt-backups:/backup alpine \
  tar xzf /backup/web_data_YYYY-MM-DD-HHMM.tgz -C /data
```

> 卷名以 `docker volume ls` 实际输出为准（脚本自动探测逻辑见
> `deploy/backup.sh`，此处假设 compose 项目名为 `ppt-maker`）。

### 3. 恢复 .env 并启动

```bash
cp /opt/ppt-backups/env_YYYY-MM-DD-HHMM /opt/ppt-maker/.env
cd /opt/ppt-maker && docker compose up -d
```

### 4. 恢复后验证

1. 浏览器打开 `http://<ECS公网IP>:8000`，用原账号登录成功；
2. 「用户管理」页确认共享 API Key 仍可正常读取（验证 `ENCRYPTION_KEY`
   与数据库密文匹配）；
3. 上传一次文件并下载，确认 `web_data` 卷路径正常。

## 四、注意事项

- **务必做一次恢复演练**：备份的价值以验证为准。建议部署后模拟一次：
  `docker compose down` → 删除 `ppt-maker_postgres_data` 卷 → 按第三节
  完整恢复 → 确认登录/共享 Key/上传可用。确认无误后再用于生产数据。
- **`ENCRYPTION_KEY` 是命门**：它同时存在于 `.env` 与
  `web_data/data/encryption.key`。两者备份齐全 + 数据库密文 = 可恢复；
  三者缺一不可。定期检查备份文件里这三样都在。
- 容器内为 UTC 时区，`pg_dump` 内容与时区无关；恢复无额外步骤。
- 备份脚本依赖 compose 栈处于运行状态；服务停机期间手动备份可改用：
  `docker run --rm -v ppt-maker_postgres_data:/pgdata alpine tar czf pg.tgz -C /pgdata .`
  （物理级备份，仅限容器完全停止时使用）。
