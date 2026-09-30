"""Pydantic request / response schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Video ────────────────────────────────────────────────────────────

class VideoOut(BaseModel):
    id: int
    title: str
    cover_url: str
    duration: int
    create_time: Optional[datetime] = None
    total_plays: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    engagement_rate: float = 0.0

    model_config = {"from_attributes": True}


class VideoRanking(BaseModel):
    id: int
    title: str
    total_plays: int
    total_likes: int
    total_comments: int
    total_shares: int
    engagement_rate: float
    trend_direction: str = "stable"  # up, down, stable


# ── Daily Stats ──────────────────────────────────────────────────────

class DailyStatsOut(BaseModel):
    date: date
    play_count: int
    like_count: int
    comment_count: int
    share_count: int

    model_config = {"from_attributes": True}


# ── Overview / Aggregate ─────────────────────────────────────────────

class OverviewOut(BaseModel):
    total_plays: int
    total_likes: int
    total_comments: int
    total_shares: int
    total_videos: int
    avg_engagement_rate: float


class TrendPoint(BaseModel):
    date: str  # "YYYY-MM-DD"
    plays: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


class EngagementBreakdown(BaseModel):
    likes: int = 0
    comments: int = 0
    shares: int = 0


class HotspotItem(BaseModel):
    video_id: int
    title: str
    metric: str  # what's hot about it
    value: float


# ── Settings ─────────────────────────────────────────────────────────

class SettingsIn(BaseModel):
    demo_mode: bool = True
    client_key: str = ""
    client_secret: str = ""


class SettingsOut(BaseModel):
    demo_mode: bool
    client_key_configured: bool
    cache_status: str = "未初始化"
    last_fetched: Optional[datetime] = None


# ── Common ───────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    success: bool
    message: str
