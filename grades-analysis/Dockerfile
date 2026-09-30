# 画室成绩分析系统 — 无 Django 单文件版
# 纯 Python 标准库，无第三方依赖；运行时需联网访问简道云 API
FROM python:3.11-slim

# 时区（同步时间戳、成绩月份解析用）
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    DATA_DB=/data/data.db

WORKDIR /app

# 应用文件 + 首次启动用的 seed 数据库
COPY server.py /app/server.py
COPY static/ /app/static/
COPY data.db /app/seed.db
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

EXPOSE 8081

# 数据持久卷（data.db 存在这里，重建容器不丢）
VOLUME /data

ENTRYPOINT ["/app/entrypoint.sh"]
