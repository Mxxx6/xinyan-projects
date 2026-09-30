"""钉钉群机器人通知"""

import logging
import httpx

logger = logging.getLogger("attendance.notify.dingtalk")


def send(webhook_url: str, title: str, content: str) -> bool:
    """发送钉钉群机器人 Markdown 消息"""
    try:
        body = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": "画室考勤\n" + content,
            },
        }
        resp = httpx.post(webhook_url, json=body, timeout=15.0)
        data = resp.json()
        if data.get("errcode") == 0:
            logger.info(f"🤖 [钉钉机器人] 发送成功")
            return True
        else:
            logger.error(f"🤖 [钉钉机器人] 发送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"🤖 [钉钉机器人] 异常: {e}")
        return False
