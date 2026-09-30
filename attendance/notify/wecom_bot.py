"""企业微信机器人通知 — Mock 版本"""

import logging

logger = logging.getLogger("attendance.notify.wecom")


def send(webhook_url: str, title: str, content: str) -> bool:
    """发送企业微信机器人消息（Markdown格式）"""
    logger.info(f"💬 [企业微信机器人] 发送成功")
    logger.info(f"   内容:\n{content}")
    print(f"\n{'='*50}")
    print(f"📨 [企业微信消息]")
    print(content)
    print(f"{'='*50}\n")
    return True
