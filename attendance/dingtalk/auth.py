"""钉钉 access_token 管理 — 对接开放平台 OAuth2 API"""

import time
import logging
import httpx
from threading import Lock

logger = logging.getLogger("attendance.dingtalk.auth")

# Token 缓存
_token_cache: dict = {"token": "", "expires_at": 0}
_lock = Lock()

TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"


def get_access_token(app_key: str, app_secret: str) -> str:
    """
    获取钉钉 access_token。
    - 首次调用通过 API 获取
    - 后续调用返回缓存（过期前5分钟自动刷新）
    """
    with _lock:
        now = time.time()
        if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
            return _token_cache["token"]

    logger.info("🔑 获取钉钉 access_token...")

    try:
        resp = httpx.post(
            TOKEN_URL,
            json={"appKey": app_key, "appSecret": app_secret},
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )
        logger.info(f"   HTTP {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            token = data.get("accessToken", "")
            expires = data.get("expireIn", 7200)

            with _lock:
                _token_cache["token"] = token
                _token_cache["expires_at"] = time.time() + expires

            logger.info(f"   ✅ Token 获取成功 (有效期 {expires}s)")
            return token
        else:
            logger.error(f"   ❌ Token 获取失败: {resp.status_code} {resp.text[:300]}")
            raise RuntimeError(f"钉钉Token获取失败 HTTP {resp.status_code}: {resp.text[:200]}")

    except httpx.RequestError as e:
        logger.error(f"   ❌ 网络请求失败: {e}")
        raise RuntimeError(f"无法连接钉钉API: {e}")
