# 月考成绩分析系统

无框架单文件服务（Python 标准库 `http.server` + `sqlite3`），一条命令启动，同时提供前端页面与 JSON 接口，实时从简道云拉取成绩数据，支持综合排名、联考总览、趋势分析等可视化。

## 技术栈

Python 3 标准库 · 简道云 API · ECharts

## 快速开始

1. 配置简道云：
   ```bash
   cp .env.example .env   # 填入 JDY_API_KEY / JDY_APP_ID / JDY_ARCHIVE_ENTRY_ID / JDY_EXAM_ENTRY_ID
   ```
2. 启动：`python3 server.py 8081`
3. 打开 `http://localhost:8081`

或使用 Docker：
```bash
docker compose up -d
```

## 目录结构

```
grades-analysis/
├── server.py            单文件服务（接口 + 简道云拉取 + Excel 导入）
├── static/              前端页面（index.html / app.js / echarts）
├── Dockerfile / docker-compose.yml
└── .env.example         简道云配置模板
```

## 隐私

简道云凭据通过环境变量注入（`.env.example` 为模板，`.env` 不入库）。
