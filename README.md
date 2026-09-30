# 个人项目作品集（Portfolio）

本仓库整理我在美术培训行业信息化建设中独立完成 / 深度参与的几个项目，覆盖数据抓取、数据分析、自动化系统与可视化看板。所有项目中的真实密钥、学生数据、成绩数据等敏感信息均已移除，统一改用环境变量或 `*.example` 配置模板注入。

## 项目一览

| 项目 | 目录 | 技术栈 | 简介 |
|------|------|--------|------|
| 抖音 / 视频号内容分析工具包 | `douyin-analysis/` | Python · FastAPI · 爬虫 · OCR · ASR · ECharts | 美术赛道爆款内容抓取 + 五因子归因分析 + PDF 选题报告生成 |
| 画室自动考勤通知系统 | `attendance/` | Python · FastAPI · APScheduler · 钉钉 Open API · 简道云 | 上课后自动拉取钉钉打卡，比对课表与名单，多渠道推送出勤状态 |
| 月考成绩分析系统 | `grades-analysis/` | Python 标准库 · 简道云 · ECharts | 无框架单文件服务，实时拉取简道云成绩，排名 / 联考 / 趋势可视化 |
| 技能商店爬虫 | `skill-store-crawler/` | Python · httpx | 技能商店 API 爬取与数据管理示例 |

## 隐私说明

- 钉钉 AppKey/AppSecret、简道云 API Key、机器人 Webhook 等一律通过环境变量或 `*.example` 配置模板注入，仓库内不含真实值。
- 学生名单、考勤记录、成绩 Excel、抓取原始数据、已生成 PDF 报告等均未纳入仓库（见 `.gitignore`）。
- 若发现历史版本中仍有残留的敏感信息，请立即到对应平台 [rotate 密钥](https://open.dingtalk.com) 并反馈。

## 运行

各子项目相互独立，具体见各自目录下的 README：

- [`douyin-analysis/README.md`](douyin-analysis/README.md)
- [`attendance/README.md`](attendance/README.md)
- [`grades-analysis/README.md`](grades-analysis/README.md)
- [`skill-store-crawler/README.md`](skill-store-crawler/README.md)
