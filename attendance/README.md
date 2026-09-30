# 画室自动考勤通知系统

上课后自动拉取钉钉考勤打卡记录，对比课表与学生名单，判定「正常 / 迟到 / 缺勤」，并通过钉钉群机器人、企业微信机器人、Server酱（微信）多渠道推送。完整实施方案见 [attendance-plan.md](attendance-plan.md)。

## 技术栈

Python 3.10+ · FastAPI · APScheduler · SQLite · 钉钉 Open API · 简道云 · HTMX

## 快速开始

1. 安装依赖：`pip install -r requirements.txt`
2. 配置钉钉凭据与课表：
   ```bash
   cp config.example.yaml config.yaml   # 填入 corp_id / app_key / app_secret / agent_id / webhook
   ```
3. 配置简道云（供 `check_jdy.py` / `check_sy.py` / `cross_check.py` / `dingtalk/jiandaoyun.py` 使用）：
   ```bash
   cp .env.example .env                  # 填入 JDY_API_KEY / JDY_APP_ID / JDY_ENTRY_ID
   ```
4. 启动：`python main.py`

## 目录结构

```
attendance/
├── main.py            入口
├── config.py          配置加载
├── dingtalk/          钉钉认证 / 考勤 / 通讯录 / 简道云
├── engine/            调度 / 规则 / 匹配
├── notify/            多渠道路由与推送
├── web/               FastAPI 路由 + 前端模板
└── check_*.py         简道云请假核查等工具脚本
```

## 隐私

真实密钥通过 `config.yaml`（不入库）与 `.env`（不入库）注入，模板见 `config.example.yaml` / `.env.example`。
