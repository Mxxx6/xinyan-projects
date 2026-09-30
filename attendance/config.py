"""配置管理 — 单例模式，启动时加载，避免重复读文件"""

import yaml
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger("attendance.config")

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_lock = Lock()
_config: Optional[dict] = None


def load_config() -> dict:
    """加载配置（首次调用读文件，后续返回缓存）"""
    global _config
    if _config is None:
        with _lock:
            if _config is None:
                with open(_CONFIG_PATH) as f:
                    _config = yaml.safe_load(f)
                logger.info(f"📄 配置已加载: {_CONFIG_PATH}")
    return _config


def reload_config() -> dict:
    """强制重新加载配置"""
    global _config
    with _lock:
        with open(_CONFIG_PATH) as f:
            _config = yaml.safe_load(f)
    logger.info("🔄 配置已重新加载")
    return _config
