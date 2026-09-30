"""Server酱（微信推送）通知 — Mock 版本"""

import logging

logger = logging.getLogger("attendance.notify.serverchan")


def send(key: str, title: str, content: str) -> bool:
    """通过Server酱发送微信通知"""
    # 微信有长度限制，取摘要
    summary = content[:200] + "..." if len(content) > 200 else content
    logger.info(f"📱 [Server酱/微信] 发送成功")
    logger.info(f"   内容:\n{summary}")
    print(f"\n{'='*50}")
    print(f"📨 [微信推送]")
    print(title)
    print(summary)
    print(f"{'='*50}\n")
    return True
