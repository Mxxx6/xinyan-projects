"""SQLAlchemy async engine, session factory, and ORM models."""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    ForeignKey,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# ── Async engine & session ──────────────────────────────────────────
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for table creation (no async create_all in SQLAlchemy)
sync_engine = create_engine(
    settings.database_url.replace("sqlite+aiosqlite", "sqlite"), echo=False
)


# ── ORM Models ───────────────────────────────────────────────────────

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    douyin_id = Column(String(64), unique=True, nullable=True, comment="Douyin item_id")
    title = Column(String(512), nullable=False, comment="Video title")
    cover_url = Column(String(1024), default="")
    share_url = Column(String(1024), default="")
    duration = Column(Integer, default=0, comment="Video duration in seconds")
    create_time = Column(DateTime, default=datetime.utcnow, comment="Publish time on Douyin")
    fetched_at = Column(DateTime, default=datetime.utcnow)


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    date = Column(Date, nullable=False)
    play_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)


class ApiCache(Base):
    __tablename__ = "api_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_key = Column(String(256), nullable=False)
    params_hash = Column(String(64), nullable=False)
    response_json = Column(Text, default="{}")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False)
    value = Column(Text, default="")


async def init_db():
    """Create all tables on startup."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, Base.metadata.create_all, sync_engine)


async def get_session() -> AsyncSession:
    """Dependency: yield an async database session."""
    async with async_session() as session:
        yield session
