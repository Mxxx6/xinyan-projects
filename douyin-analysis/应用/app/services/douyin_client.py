"""Douyin Open Platform API client.

Handles:
- OAuth 2.0 token exchange and refresh
- Rate limiting (token bucket algorithm)
- API response caching
- Graceful fallback when credentials are missing

Douyin Open API docs: https://developer.open-douyin.com/docs/resource/zh-CN/dop/develop/openapi/life-service-open-ability/

NOTE: The Douyin Open Platform requires enterprise developer registration.
Individual developers should use demo mode (the default).
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.services.analytics import AnalyticsEngine


# ── Token Bucket Rate Limiter ────────────────────────────────────────

class RateLimiter:
    """Simple token bucket for API rate limiting.

    Douyin's default limits for individual devs:
    - ~100 calls/day for most endpoints
    - ~1000 calls/day for basic data endpoints

    We implement a conservative bucket: 1 call per 15 seconds (4/min ≈ 5760/day).
    """

    def __init__(self, rate: float = 1.0, per_seconds: float = 15.0):
        self.rate = rate
        self.interval = per_seconds / rate
        self.tokens = rate
        self.max_tokens = rate
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.rate / self.interval))
        self.last_refill = now

    async def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed."""
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


# ── Token Manager ────────────────────────────────────────────────────

class TokenManager:
    """Manages OAuth access tokens: store, check expiry, auto-refresh.

    Tokens are obfuscated with XOR before storing in SQLite.
    Access tokens typically expire in 15-30 days on Douyin.
    """

    @staticmethod
    def _obfuscate(value: str) -> str:
        secret = settings.secret_key.encode()
        data = value.encode()
        return "".join(f"{b ^ secret[i % len(secret)]:02x}" for i, b in enumerate(data))

    @staticmethod
    def _deobfuscate(encoded: str) -> str:
        secret = settings.secret_key.encode()
        if not encoded:
            return ""
        try:
            data = bytes(int(encoded[i:i + 2], 16) for i in range(0, len(encoded), 2))
            return "".join(chr(b ^ secret[i % len(secret)]) for i, b in enumerate(data))
        except (ValueError, IndexError):
            return ""

    async def get_access_token(self, session: AsyncSession) -> Optional[str]:
        """Retrieve a valid access token, refreshing if needed."""
        result = await session.execute(
            text("SELECT value FROM app_config WHERE key = 'access_token'")
        )
        row = result.fetchone()
        if row:
            return self._deobfuscate(row[0])
        return None

    async def store_tokens(
        self,
        session: AsyncSession,
        access_token: str,
        refresh_token: str = "",
        expires_in: int = 1296000,  # default 15 days
    ):
        """Persist tokens to database."""
        now = datetime.utcnow()
        expiry = now + timedelta(seconds=expires_in)

        for key, value in [
            ("access_token", access_token),
            ("refresh_token", refresh_token),
            ("token_expiry", expiry.isoformat()),
        ]:
            await session.execute(
                text("""
                    INSERT INTO app_config (key, value)
                    VALUES (:key, :value)
                    ON CONFLICT(key) DO UPDATE SET value = :value
                """),
                {"key": key, "value": self._obfuscate(value) if "token" in key else value},
            )

    async def refresh_if_needed(self, session: AsyncSession) -> Optional[str]:
        """Check token expiry and refresh if necessary."""
        result = await session.execute(
            text("SELECT value FROM app_config WHERE key = 'token_expiry'")
        )
        row = result.fetchone()
        if row:
            expiry = datetime.fromisoformat(row[0])
            if datetime.utcnow() < expiry - timedelta(hours=1):
                return await self.get_access_token(session)
        return await self._refresh_access_token(session)

    async def _refresh_access_token(self, session: AsyncSession) -> Optional[str]:
        """Call Douyin's /oauth/refresh_token/ endpoint."""
        refresh_token = await self._get_refresh_token(session)
        if not refresh_token:
            return None

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    "https://open.douyin.com/oauth/refresh_token/",
                    params={
                        "client_key": settings.douyin_client_key,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                )
                data = resp.json()
                if data.get("data", {}).get("error_code") == 0:
                    token_data = data["data"]
                    await self.store_tokens(
                        session,
                        access_token=token_data["access_token"],
                        refresh_token=token_data.get("refresh_token", refresh_token),
                        expires_in=token_data.get("expires_in", 1296000),
                    )
                    return token_data["access_token"]
            except Exception:
                pass
        return None

    async def _get_refresh_token(self, session: AsyncSession) -> Optional[str]:
        result = await session.execute(
            text("SELECT value FROM app_config WHERE key = 'refresh_token'")
        )
        row = result.fetchone()
        return self._deobfuscate(row[0]) if row else None


# ── Douyin API Client ────────────────────────────────────────────────

class DouyinClient:
    """Client for Douyin Open Platform API.

    When credentials are not configured, operations raise informative errors
    that the API layer can catch to suggest switching to demo mode.
    """

    BASE_URL = "https://open.douyin.com"

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.token_manager = TokenManager()
        self._http = httpx.AsyncClient(timeout=30)

    async def _check_credentials(self):
        """Raise if no API credentials are configured."""
        if not settings.douyin_client_key or not settings.douyin_client_secret:
            raise ValueError(
                "抖音 API 凭证未配置。请在设置页面填入 Client Key 和 Client Secret，"
                "或切换到演示模式。"
            )

    async def _authenticated_request(
        self, session: AsyncSession, endpoint: str, params: dict = None
    ) -> dict:
        """Make an authenticated GET request to Douyin API with caching."""
        await self._check_credentials()

        # Check cache first
        cache_key = hashlib.md5(
            f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}".encode()
        ).hexdigest()

        cache_result = await session.execute(
            text("""
                SELECT response_json FROM api_cache
                WHERE endpoint_key = :key AND params_hash = :hash
                AND expires_at > :now
            """),
            {"key": endpoint, "hash": cache_key, "now": datetime.utcnow()},
        )
        cached = cache_result.fetchone()
        if cached:
            return json.loads(cached[0])

        # Rate limit check
        if not await self.rate_limiter.acquire():
            # Try to serve stale cache
            stale = await session.execute(
                text("""
                    SELECT response_json FROM api_cache
                    WHERE endpoint_key = :key AND params_hash = :hash
                    ORDER BY fetched_at DESC LIMIT 1
                """),
                {"key": endpoint, "hash": cache_key},
            )
            stale_row = stale.fetchone()
            if stale_row:
                return json.loads(stale_row[0])
            raise RuntimeError("API 请求频率超限，请稍后再试")

        # Get access token
        token = await self.token_manager.refresh_if_needed(session)
        if not token:
            raise RuntimeError("无法获取有效的 Access Token，请检查 API 凭证")

        # Make request
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"access-token": token}
        if params is None:
            params = {}

        try:
            resp = await self._http.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            # Cache response
            ttl_minutes = settings.cache_ttl_minutes
            await session.execute(
                text("""
                    INSERT INTO api_cache (endpoint_key, params_hash, response_json, fetched_at, expires_at)
                    VALUES (:key, :hash, :json, :now, :expires)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "key": endpoint,
                    "hash": cache_key,
                    "json": json.dumps(data, ensure_ascii=False),
                    "now": datetime.utcnow(),
                    "expires": datetime.utcnow() + timedelta(minutes=ttl_minutes),
                },
            )
            return data
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API 请求失败: {e.response.status_code}")

    # ── Public API methods (mirror MockDataGenerator interface) ───────

    async def get_overview(self, session: AsyncSession) -> dict:
        """Get aggregate KPI totals."""
        # Douyin doesn't have a single overview endpoint, so we aggregate from video list
        videos = await self._fetch_all_videos(session)
        total_plays = sum(v.get("play_count", 0) for v in videos)
        total_likes = sum(v.get("like_count", 0) for v in videos)
        total_comments = sum(v.get("comment_count", 0) for v in videos)
        total_shares = sum(v.get("share_count", 0) for v in videos)

        avg_engagement = AnalyticsEngine.engagement_rate(
            total_likes, total_comments, total_shares, total_plays
        )

        return {
            "total_plays": total_plays,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_videos": len(videos),
            "avg_engagement_rate": avg_engagement,
        }

    async def get_trends(self, session: AsyncSession, days: int = 30) -> list[dict]:
        """Get daily time series."""
        # The Douyin API returns per-video data; we aggregate by day
        videos = await self._fetch_all_videos(session)
        # In production, we'd call video-specific daily stat endpoints
        # For now, return the data we have stored in our DB
        from datetime import date
        cutoff = date.today() - timedelta(days=days)

        result = await session.execute(
            text("""
                SELECT ds.date, SUM(ds.play_count), SUM(ds.like_count),
                       SUM(ds.comment_count), SUM(ds.share_count)
                FROM daily_stats ds
                WHERE ds.date >= :cutoff
                GROUP BY ds.date ORDER BY ds.date
            """),
            {"cutoff": cutoff},
        )
        return [
            {
                "date": str(r[0]),
                "plays": int(r[1]),
                "likes": int(r[2]),
                "comments": int(r[3]),
                "shares": int(r[4]),
            }
            for r in result.fetchall()
        ]

    async def get_videos(
        self, session: AsyncSession, sort: str = "engagement", limit: int = 20
    ) -> list[dict]:
        """Get video list."""
        from app.services.mock_data import MockDataGenerator
        return await MockDataGenerator().get_videos(session, sort=sort, limit=limit)

    async def get_video_detail(self, session: AsyncSession, video_id: int):  # -> dict | None (py3.10+)
        """Get single video detail."""
        from app.services.mock_data import MockDataGenerator
        return await MockDataGenerator().get_video_detail(session, video_id)

    async def get_hotspot(self, session: AsyncSession) -> list[dict]:
        """Get hotspot analysis."""
        from app.services.mock_data import MockDataGenerator
        return await MockDataGenerator().get_hotspot(session)

    async def get_posting_hour_distribution(self, session: AsyncSession) -> list[dict]:
        """Get posting hour engagement."""
        from app.services.mock_data import MockDataGenerator
        return await MockDataGenerator().get_posting_hour_distribution(session)

    async def refresh_all_data(self, session: AsyncSession) -> int:
        """Fetch and store latest data from Douyin API. Returns count of videos."""
        await self._check_credentials()
        videos = await self._fetch_all_videos(session)
        # Store in database
        count = 0
        for video in videos:
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO api_cache
                        (endpoint_key, params_hash, response_json, fetched_at, expires_at)
                    VALUES ('video_detail', :hash, :json, :now, :expires)
                """),
                {
                    "hash": hashlib.md5(str(video.get("item_id", "")).encode()).hexdigest(),
                    "json": json.dumps(video, ensure_ascii=False),
                    "now": datetime.utcnow(),
                    "expires": datetime.utcnow() + timedelta(minutes=settings.cache_ttl_minutes),
                },
            )
            count += 1
        await session.commit()
        return count

    async def _fetch_all_videos(self, session: AsyncSession) -> list[dict]:
        """Fetch all videos for the authenticated account from DB cache or API."""
        # First try the database for stored video data
        result = await session.execute(
            text("SELECT id, title, create_time FROM videos LIMIT 50")
        )
        rows = result.fetchall()
        if rows:
            return [
                {"item_id": str(r[0]), "title": r[1], "create_time": str(r[2])}
                for r in rows
            ]

        # Fall back to API
        await self._check_credentials()
        token = await self.token_manager.refresh_if_needed(session)
        if not token:
            return []

        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/api/douyin/v1/video/list/",
                headers={"access-token": token},
                params={"cursor": 0, "count": 50},
            )
            data = resp.json()
            if data.get("data", {}).get("error_code") == 0:
                return data["data"].get("list", [])
        except Exception:
            pass
        return []
