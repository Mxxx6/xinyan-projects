#!/bin/sh
set -e

DB="${DATA_DB:-/data/data.db}"

# 首次启动：把镜像内置的 seed 数据库复制到持久卷。
# 之后数据只存在于卷里，重建/升级容器都不会覆盖。
if [ ! -f "$DB" ]; then
    echo "[entrypoint] 首次启动，初始化数据库到 $DB"
    mkdir -p "$(dirname "$DB")"
    cp /app/seed.db "$DB"
fi

echo "[entrypoint] 启动服务，数据库: $DB"
exec python3 /app/server.py 8081
