"""通知分发器 — 注册表模式，消除重复代码"""

import logging

from .dingtalk_bot import send as send_dingtalk
from .wecom_bot import send as send_wecom
from .serverchan import send as send_serverchan

logger = logging.getLogger("attendance.notify.dispatcher")

# 渠道注册表: { channel_key: (send_func, config_key, channel_name) }
_CHANNELS = [
    (send_dingtalk,  "dingtalk_webhook",   "钉钉群机器人"),
    (send_wecom,     "wecom_webhook",      "企业微信机器人"),
    (send_serverchan,"serverchan_key",     "Server酱(微信)"),
]

# Mock 模式下用来占位的假凭证
MOCK_MARKER = "mock"


def dispatch_all(class_name: str, report: str, notify_config: dict):
    """遍历所有渠道发送通知。凭证含 'mock' 时打印到控制台。"""
    title = f"📋 {class_name} 出勤报告"

    for send_func, config_key, channel_name in _CHANNELS:
        credential = notify_config.get(config_key, "")
        is_mock = not credential or MOCK_MARKER in credential

        try:
            if is_mock:
                send_func("mock", title, report)
            else:
                send_func(credential, title, report)
            logger.info(f"✅ [{channel_name}] 发送成功")
        except Exception as e:
            logger.error(f"❌ [{channel_name}] 发送失败: {e}")

    logger.info(f"📤 {class_name} 通知分发完成")
