#!/usr/bin/env python3
"""🎨 画室自动考勤通知系统 — 入口"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("attendance")

sys.path.insert(0, str(Path(__file__).parent))


def create_app():
    from config import load_config
    from db.models import init_db
    from engine.scheduler import start_scheduler
    from fastapi import FastAPI
    from web.routes import router as web_router

    config = load_config()
    logger.info("📄 配置文件已加载")

    init_db()
    logger.info("🗄️ 数据库已初始化")

    app = FastAPI(
        title="画室考勤系统",
        description="自动拉取钉钉考勤，判定出勤状态，多渠道推送通知",
        version="2.0.0",
    )
    app.include_router(web_router)

    start_scheduler(config)
    logger.info("⏰ 定时调度器已启动")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 55)
    print("   🎨  画室自动考勤通知系统  v2.0")
    print("   " + "=" * 45)
    print()
    print("   📊 仪表盘:      http://localhost:8002")
    print("   📋 历史记录:    http://localhost:8002/history")
    print("   👤 学生统计:    http://localhost:8002/students")
    print("   📅 课表管理:    http://localhost:8002/schedule")
    print("   🔧 API 文档:    http://localhost:8002/docs")
    print()
    print("   💡 在课表管理页点击「手动触发」即可模拟出勤检查")
    print("=" * 55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
