# 画室自动考勤通知系统 — 实施方案

## 背景

画室使用钉钉考勤打卡 + 刷脸机记录学生出勤。目前每节课需要手动打开钉钉导出 Excel 核对迟到/缺勤，流程繁琐。

**目标**：上课 5 分钟后，系统自动拉取钉钉考勤数据，对比课表和学生名单，自动推送出勤状态（正常/迟到/缺勤）到微信/钉钉群/网页。

## 核心流程

```
课表定时触发 ──→ 调用钉钉API拉取打卡记录 ──→ 匹配学生名单 ──→ 判定出勤状态 ──→ 多渠道推送通知
     │                    │                      │                │                │
  固定课表           考勤打卡模块            钉钉通讯录        规则引擎        微信/钉钉/Web
```

## 技术选型

| 层面 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 工作目录已有 Python 生态 |
| Web框架 | FastAPI | 轻量、异步、自带API文档 |
| 定时调度 | APScheduler | 支持cron表达式，进程内调度 |
| 数据库 | SQLite | 零配置，单机够用，存课表+历史记录 |
| 前端 | 极简HTML + HTMX | 不需要Node.js构建链 |
| 推送 | 钉钉机器人 + 企业微信机器人 + Server酱(微信) | 三条渠道覆盖 |

## 项目结构

```
./attendance/
├── config.yaml              # 课表、API密钥、通知配置
├── main.py                  # FastAPI 入口 + APScheduler 启动
├── dingtalk/
│   ├── __init__.py
│   ├── auth.py              # 钉钉 access_token 管理
│   ├── attendance.py        # 拉取考勤打卡记录
│   └── contacts.py          # 拉取钉钉通讯录（学生名单）
├── engine/
│   ├── __init__.py
│   ├── scheduler.py         # 定时任务管理（课表触发）
│   ├── matcher.py           # 学生-打卡记录匹配
│   └── rules.py             # 出勤状态判定（正常/迟到/缺勤/请假）
├── notify/
│   ├── __init__.py
│   ├── dingtalk_bot.py      # 钉钉群机器人推送
│   ├── wecom_bot.py         # 企业微信机器人推送
│   └── serverchan.py        # Server酱（个人微信推送）
├── web/
│   ├── __init__.py
│   ├── routes.py            # API路由 + 页面路由
│   └── templates/
│       ├── index.html       # 仪表盘：今日出勤概览
│       ├── history.html     # 历史记录查询
│       └── schedule.html    # 课表管理
├── db/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy/SQLite 模型
│   └── init_db.py           # 建库脚本
└── requirements.txt
```

## 各模块设计

### 1. config.yaml — 统一配置

```yaml
dingtalk:
  corp_id: "xxx"
  app_key: "xxx"
  app_secret: "xxx"
  agent_id: 123456

schedule:
  - name: "周六素描班"
    weekday: 6          # 0=周一, 6=周日
    time: "09:00"
    duration_minutes: 180
    notify_after_minutes: 5   # 上课后5分钟触发
  - name: "周日色彩班"
    weekday: 7
    time: "14:00"
    duration_minutes: 180
    notify_after_minutes: 5

rules:
  late_grace_minutes: 5       # 迟到X分钟内算迟到，超过算缺勤
  on_time_before_minutes: 0   # 上课前X分钟内打卡算准时

notify:
  dingtalk_webhook: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
  serverchan_key: "SCTxxx"
```

### 2. 钉钉对接 (dingtalk/)

**auth.py** — 通过 app_key + app_secret 获取 access_token，缓存到过期前5分钟自动刷新。

**attendance.py** — 调用钉钉开放平台API：
- `POST /v1.0/attendance/result/list` — 按时间段拉取打卡结果
- 返回：userId, checkInTime, checkOutTime, 等等

**contacts.py** — 调用通讯录API：
- `GET /topapi/v2/user/list` — 按部门拉取学生列表
- 学生按钉钉部门标签分组 → 对应班级

### 3. 匹配引擎 (engine/)

**scheduler.py** — APScheduler 管理定时任务：
- 启动时从 config.yaml 读取课表
- 为每节课注册 cron 任务：`上课时间 + 5分钟`
- 支持动态添加/删除任务（通过Web管理界面）

**matcher.py** — 学生-打卡匹配：
- 从钉钉通讯录获取该班学生 userId 列表
- 从钉钉考勤获取该时间段打卡记录
- 做 join：每个学生对应一条打卡记录（或 null）

**rules.py** — 状态判定逻辑：
```
if 无打卡记录 → 缺勤
elif 打卡时间 ≤ 上课时间 → 正常
elif 打卡时间 - 上课时间 ≤ late_grace_minutes → 迟到
else → 缺勤（迟到太久）
```

### 4. 通知推送 (notify/)

每条渠道独立模块，统一接口 `send(attendance_report)`：
- **钉钉群机器人**：Markdown 格式消息，@相关老师
- **企业微信机器人**：Markdown 格式消息
- **Server酱**：微信推送，简洁文本

报告格式示例：
```
📋 周六素描班 出勤报告 (07/20 09:05)
━━━━━━━━━━━━━━━━━━━━
✅ 正常 8人：张三、李四、王五...
⚠️ 迟到 2人：赵六(09:07)、钱七(09:12)
❌ 缺勤 1人：孙八
━━━━━━━━━━━━━━━━━━━━
出勤率：80% (8/10)
```

### 5. Web管理界面 (web/)

极简仪表盘，用 HTMX 实现无刷交互：
- **首页仪表盘**：今日课程 + 最近出勤状态卡片
- **历史记录**：按日期/班级筛选查看过往出勤
- **课表管理**：增删改课表（写回 config.yaml）
- **手动触发**：立即检查某节课出勤

### 6. 数据库 (db/)

SQLite 三张表：

```sql
-- 出勤记录
attendance_records:
  id, class_name, student_name, student_user_id,
  class_date, class_start_time, check_in_time,
  status(正常/迟到/缺勤), created_at

-- 课表（与config.yaml双向同步）
schedules:
  id, name, weekday, time, duration_minutes,
  notify_after_minutes, enabled

-- 通知日志
notify_logs:
  id, channel, recipients, content, sent_at, success
```

## 实施步骤

### 第一步：基础框架搭建
- 创建项目目录结构
- 编写 requirements.txt（FastAPI, APScheduler, httpx, PyYAML, Jinja2）
- 编写 config.yaml 模板
- 编写 main.py 骨架（FastAPI启动 + APScheduler初始化）

### 第二步：钉钉API对接
- 实现 auth.py（token获取与缓存）
- 实现 contacts.py（获取学生通讯录）
- 实现 attendance.py（获取考勤记录）
- 编写测试脚本验证API连通性

### 第三步：核心引擎
- 实现 rules.py（状态判定）
- 实现 matcher.py（学生-打卡匹配）
- 实现 scheduler.py（定时任务管理）

### 第四步：通知推送
- 实现三条推送渠道
- 实现消息模板格式化

### 第五步：Web界面
- 实现数据库模型
- 实现仪表盘页面
- 实现历史查询页面
- 实现课表管理页面（含手动触发按钮）

### 第六步：集成测试 & 部署
- 端到端测试完整流程
- 编写 README 部署说明
- 可选：Docker 化、systemd 服务配置

## 前置条件（需要你准备）

1. **钉钉开发者账号**：在 [open.dingtalk.com](https://open.dingtalk.com) 创建企业内部应用，获取 app_key、app_secret
2. **钉钉应用权限**：申请以下接口权限 —
   - 考勤结果读取 (`attendance.result.list`)
   - 通讯录用户读取 (`topapi.v2.user.list`)
3. **通知渠道**：
   - 钉钉群机器人 webhook 地址
   - 企业微信机器人 webhook 地址（可选）
   - Server酱 key（可选，用于微信推送，[sct.ftqq.com](https://sct.ftqq.com)）
4. **学生分班**：确认钉钉通讯录里学生是如何按班级分组的（部门？标签？）

## 验证方式

1. 配置好 config.yaml 后运行 `python main.py`
2. 浏览器打开 `http://localhost:8000` 查看仪表盘
3. 在课表管理页点击「手动触发」立即测试一节课程的出勤检查
4. 确认钉钉群/微信收到出勤报告消息
5. 观察定时任务是否按时自动触发
