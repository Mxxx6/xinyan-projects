"""Realistic Chinese video analytics mock data generator.

Generates 50 videos with 90 days of daily stats that follow real-world patterns:
- Power-law view distribution (few viral, many modest)
- Engagement rates inversely correlated with view count
- Weekday/weekend patterns (higher on Saturday)
- Posting-hour clusters (lunch, after-work, evening)
- Realistic growth curves: initial spike → decay → occasional resurgence
"""

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.analytics import AnalyticsEngine


# ── Deterministic random for reproducibility ─────────────────────────
def _seed_hash(seed_str: str) -> int:
    return int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)


class SeededRandom:
    """A random.Random wrapper seeded deterministically from a string."""

    def __init__(self, seed: str):
        self.rng = random.Random(_seed_hash(seed))

    def randint(self, a: int, b: int) -> int:
        return self.rng.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        return self.rng.uniform(a, b)

    def choice(self, seq):
        return self.rng.choice(seq)

    def choices(self, population, weights=None, k=1):
        return self.rng.choices(population, weights=weights, k=k)

    def gauss(self, mu: float, sigma: float) -> float:
        return self.rng.gauss(mu, sigma)

    def shuffle(self, seq):
        self.rng.shuffle(seq)


# ── Content pools ────────────────────────────────────────────────────

VIDEO_TITLES = [
    # 美食类
    "2024年度爆款美食推荐，第3个绝了！",
    "在家也能做的米其林级牛排教程",
    "深夜放毒！街边摊隐藏美食大合集",
    "减脂餐也可以很好吃，一周不重样",
    "外婆教的秘制红烧肉，肥而不腻入口即化",
    "夏天必学的10款冰饮，清爽解暑",
    "全网最火空气炸锅食谱来了",
    "人均30吃到撑！大学城美食街探店",
    "重庆火锅底料做法大揭秘",
    "烘焙新手必看！零失败戚风蛋糕",
    # 时尚穿搭
    "今日穿搭分享OOTD｜早秋通勤风",
    "小个子女生穿搭指南，显高10cm！",
    "优衣库2024春夏新品试穿报告",
    "年度爱用包包合集｜百搭又实用",
    "梨形身材怎么穿？遮肉显瘦攻略",
    "古着探店｜藏在胡同里的宝藏店铺",
    # 旅游出行
    "人均2000玩转云南，7天自由行攻略",
    "此生必去的10个国内小众旅行地",
    "带父母去北京怎么玩？超详细攻略",
    "成都48小时吃货暴走路线",
    "新疆自驾游｜独库公路绝美风景",
    "周末逃离城市计划｜周边露营推荐",
    # 科技数码
    "iPhone 16 Pro Max 深度评测",
    "学生党高性价比笔记本推荐2024",
    "ChatGPT高效使用技巧，效率提升10倍",
    "智能家居入门指南，懒人必备",
    "2024最佳无线耳机横评",
    "AI绘画Midjourney进阶教程",
    # 搞笑娱乐
    "人类幼崽迷惑行为大赏",
    "当猫咪第一次看到下雪",
    "办公室整蛊同事合集，笑到肚子疼",
    "那些年爸妈的迷惑拍照技术",
    "千万不要让男朋友给你拍照",
    "演唱会抢票攻略｜亲身实测有效",
    # 知识教育
    "5分钟搞懂区块链到底是什么",
    "英语口语提升秘籍，每天只需15分钟",
    "PS大神教你一键换天空",
    "摄影构图法则，手机也能拍大片",
    "理财入门：工资5000如何攒下第一桶金",
    "历史冷知识：古代皇帝的奇葩癖好",
    # 生活日常
    "出租屋改造前后对比，房东看了都感动",
    "极简主义生活｜断舍离一年后的变化",
    "月薪6000独居生活vlog",
    "考研二战上岸经验分享｜干货满满",
    "养狗的快乐你想象不到｜金毛成长日记",
    "新手养花推荐：养不死的10种绿植",
    "副业经验分享：做自媒体一年赚了多少",
    "30岁裸辞开咖啡店是什么体验",
]


def _random_duration(rng: SeededRandom) -> int:
    """Return a realistic Douyin video duration (15/30/60s most common)."""
    return rng.choice([15, 15, 15, 30, 30, 30, 30, 60, 60, 90, 120, 180])


def _daily_growth_curve(day: int, total_days: int, rng: SeededRandom) -> float:
    """Produce a realistic daily views multiplier.

    Models: rapid initial growth → peak around day 3-7 → gradual decay
    with occasional small resurgences.
    """
    # Base: lognormal-shaped curve (rapid rise, slow fall)
    peak_day = rng.randint(2, 10)
    if day <= peak_day:
        # Growth phase
        base = (day / peak_day) ** 0.6
    else:
        # Decay phase
        decay_factor = (total_days - day) / (total_days - peak_day)
        base = 1.0 - (1.0 - decay_factor) * 0.7

    # Add some noise
    noise = rng.gauss(0, 0.15)

    # Weekend boost (days 5-6 every 7 days = Sat/Sun)
    weekend_boost = 1.0
    if day % 7 in (5, 6):
        weekend_boost = 1.2 + rng.uniform(0, 0.3)

    # Occasional viral surge (5% chance per day)
    surge = 1.0
    if rng.uniform(0, 1) < 0.05:
        surge = 2.0 + rng.uniform(0, 5.0)

    return max(0.01, base * noise * weekend_boost * surge)


# ── Helpers ──────────────────────────────────────────────────────────

def _to_iso(ct) -> Optional[str]:
    """Convert a create_time value to ISO string regardless of type."""
    if ct is None:
        return None
    if isinstance(ct, str):
        return ct
    return ct.isoformat()


class MockDataGenerator:
    """Generates and seeds realistic Chinese video analytics data."""

    NUM_VIDEOS = 50
    NUM_DAYS = 90

    def __init__(self):
        self.master_rng = SeededRandom("douyin-mock-2024-v1")

    # ── Public API (mirrors real client + returns structured data) ────

    async def get_overview(self, session: AsyncSession) -> dict:
        """Return KPI totals for the dashboard overview."""
        result = await session.execute(
            text("""
                SELECT
                    COALESCE(SUM(ds.play_count), 0) as total_plays,
                    COALESCE(SUM(ds.like_count), 0) as total_likes,
                    COALESCE(SUM(ds.comment_count), 0) as total_comments,
                    COALESCE(SUM(ds.share_count), 0) as total_shares,
                    COUNT(DISTINCT v.id) as total_videos
                FROM daily_stats ds
                JOIN videos v ON v.id = ds.video_id
            """)
        )
        row = result.fetchone()
        total_plays, total_likes, total_comments, total_shares, total_videos = row

        avg_engagement = AnalyticsEngine.engagement_rate(
            int(total_likes), int(total_comments), int(total_shares), int(total_plays)
        )

        return {
            "total_plays": int(total_plays),
            "total_likes": int(total_likes),
            "total_comments": int(total_comments),
            "total_shares": int(total_shares),
            "total_videos": int(total_videos),
            "avg_engagement_rate": round(avg_engagement, 2),
        }

    async def get_trends(self, session: AsyncSession, days: int = 30) -> list[dict]:
        """Return daily aggregated time series."""
        cutoff = date.today() - timedelta(days=days)
        result = await session.execute(
            text("""
                SELECT
                    ds.date,
                    SUM(ds.play_count) as plays,
                    SUM(ds.like_count) as likes,
                    SUM(ds.comment_count) as comments,
                    SUM(ds.share_count) as shares
                FROM daily_stats ds
                WHERE ds.date >= :cutoff
                GROUP BY ds.date
                ORDER BY ds.date ASC
            """),
            {"cutoff": cutoff},
        )
        return [
            {
                "date": str(row.date),
                "plays": int(row.plays),
                "likes": int(row.likes),
                "comments": int(row.comments),
                "shares": int(row.shares),
            }
            for row in result.fetchall()
        ]

    async def get_videos(
        self, session: AsyncSession, sort: str = "engagement", limit: int = 20
    ) -> list[dict]:
        """Return ranked video list."""
        result = await session.execute(
            text("""
                SELECT
                    v.id, v.title, v.duration, v.create_time,
                    COALESCE(SUM(ds.play_count), 0) as total_plays,
                    COALESCE(SUM(ds.like_count), 0) as total_likes,
                    COALESCE(SUM(ds.comment_count), 0) as total_comments,
                    COALESCE(SUM(ds.share_count), 0) as total_shares
                FROM videos v
                LEFT JOIN daily_stats ds ON ds.video_id = v.id
                GROUP BY v.id
                ORDER BY total_plays DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        videos = []
        for row in result.fetchall():
            total_plays = int(row.total_plays)
            total_likes = int(row.total_likes)
            total_comments = int(row.total_comments)
            total_shares = int(row.total_shares)

            engagement = AnalyticsEngine.engagement_rate(
                total_likes, total_comments, total_shares, total_plays
            )
            videos.append({
                "id": row.id,
                "title": row.title,
                "duration": row.duration,
                "create_time": _to_iso(row.create_time),
                "total_plays": total_plays,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "engagement_rate": engagement,
            })

        # Compute trend direction for each video
        for v in videos:
            # Fetch daily play counts to determine trend
            daily_result = await session.execute(
                text("""
                    SELECT play_count FROM daily_stats
                    WHERE video_id = :vid
                    ORDER BY date DESC LIMIT 14
                """),
                {"vid": v["id"]},
            )
            recent_plays = [int(r[0]) for r in daily_result.fetchall()]
            recent_plays.reverse()  # chronological order
            v["trend_direction"] = AnalyticsEngine.trend_direction(recent_plays)

        if sort == "engagement":
            videos.sort(key=lambda v: v["engagement_rate"], reverse=True)
        elif sort == "latest":
            videos.sort(key=lambda v: v.get("create_time") or "", reverse=True)

        return videos

    async def get_video_detail(self, session: AsyncSession, video_id: int):  # -> dict | None (py3.10+)
        """Return single video with daily breakdown."""
        result = await session.execute(
            text("""
                SELECT
                    v.id, v.title, v.duration, v.create_time,
                    COALESCE(SUM(ds.play_count), 0) as total_plays,
                    COALESCE(SUM(ds.like_count), 0) as total_likes,
                    COALESCE(SUM(ds.comment_count), 0) as total_comments,
                    COALESCE(SUM(ds.share_count), 0) as total_shares
                FROM videos v
                LEFT JOIN daily_stats ds ON ds.video_id = v.id
                WHERE v.id = :video_id
                GROUP BY v.id
            """),
            {"video_id": video_id},
        )
        row = result.fetchone()
        if not row:
            return None

        engagement = AnalyticsEngine.engagement_rate(
            int(row.total_likes), int(row.total_comments),
            int(row.total_shares), int(row.total_plays)
        )

        # Daily breakdown
        daily_result = await session.execute(
            text("""
                SELECT date, play_count, like_count, comment_count, share_count
                FROM daily_stats
                WHERE video_id = :video_id
                ORDER BY date
            """),
            {"video_id": video_id},
        )
        daily = [
            {
                "date": str(d.date),
                "play_count": d.play_count,
                "like_count": d.like_count,
                "comment_count": d.comment_count,
                "share_count": d.share_count,
            }
            for d in daily_result.fetchall()
        ]

        return {
            "id": row.id,
            "title": row.title,
            "duration": row.duration,
            "create_time": _to_iso(row.create_time),
            "total_plays": int(row.total_plays),
            "total_likes": int(row.total_likes),
            "total_comments": int(row.total_comments),
            "total_shares": int(row.total_shares),
            "engagement_rate": round(engagement, 2),
            "daily": daily,
        }

    async def get_hotspot(self, session: AsyncSession) -> list[dict]:
        """Return trending analysis using viral detection engine."""
        # First get all videos with recent weekly stats
        cutoff = date.today() - timedelta(days=7)
        result = await session.execute(
            text("""
                SELECT
                    v.id, v.title,
                    COALESCE(SUM(ds.play_count), 0) as play_count,
                    COALESCE(SUM(ds.like_count), 0) as like_count,
                    COALESCE(SUM(ds.comment_count), 0) as comment_count,
                    COALESCE(SUM(ds.share_count), 0) as share_count
                FROM videos v
                JOIN daily_stats ds ON ds.video_id = v.id
                WHERE ds.date >= :cutoff
                GROUP BY v.id
            """),
            {"cutoff": cutoff},
        )
        all_videos = [
            {**dict(row._mapping), "id": row.id, "title": row.title}
            for row in result.fetchall()
        ]

        # Run through viral detection engine
        viral = AnalyticsEngine.detect_viral_content(
            all_videos,
            play_threshold=5000,   # lower threshold for weekly window
            engagement_threshold=3.0,
            play_key="play_count",
        )
        return [
            {
                "video_id": v["id"],
                "title": v["title"],
                "metric": "周播放增长 + 高互动",
                "value": int(v.get("play_count", 0)),
            }
            for v in viral
        ]

    async def get_posting_hour_distribution(
        self, session: AsyncSession
    ) -> list[dict]:
        """Return engagement by posting hour (simulated)."""
        # Since we don't store posting hour, we generate a realistic distribution
        hourly_pattern = [
            2, 1, 0, 0, 0, 1, 2, 5, 8, 10, 12, 14,
            16, 14, 12, 10, 11, 15, 19, 22, 21, 18, 9, 4,
        ]
        return [
            {"hour": h, "engagement": hourly_pattern[h] + self.master_rng.randint(-1, 3)}
            for h in range(24)
        ]

    # ── Database seeding ─────────────────────────────────────────────

    async def seed_database(self, session: AsyncSession) -> None:
        """Generate 50 videos with 90 days of daily stats and insert them."""
        end_date = date.today()
        start_date = end_date - timedelta(days=self.NUM_DAYS)

        titles = list(VIDEO_TITLES)
        self.master_rng.shuffle(titles)
        titles = titles[:self.NUM_VIDEOS]

        # Assign base popularity tiers (power-law distribution)
        tiers = (
            ["viral"] * 3 +      # 3 viral videos (>1M views)
            ["hot"] * 8 +         # 8 hot videos (100K-1M)
            ["medium"] * 18 +     # 18 medium videos (10K-100K)
            ["normal"] * 21       # 21 normal videos (<10K)
        )

        for i, (title, tier) in enumerate(zip(titles, tiers)):
            video_rng = SeededRandom(f"video-{i}-{title}")

            # Base daily views by tier
            tier_base = {
                "viral": video_rng.randint(30000, 150000),
                "hot": video_rng.randint(3000, 30000),
                "medium": video_rng.randint(300, 3000),
                "normal": video_rng.randint(10, 300),
            }[tier]

            publish_offset = video_rng.randint(0, self.NUM_DAYS - 7)
            publish_date = start_date + timedelta(days=publish_offset)
            duration = _random_duration(video_rng)

            await session.execute(
                text("""
                    INSERT INTO videos (title, duration, create_time, fetched_at)
                    VALUES (:title, :duration, :create_time, :fetched_at)
                """),
                {
                    "title": title,
                    "duration": duration,
                    "create_time": datetime.combine(publish_date, datetime.min.time()),
                    "fetched_at": datetime.utcnow(),
                },
            )
            await session.flush()

            # Get the inserted video id
            result = await session.execute(text("SELECT last_insert_rowid()"))
            video_id = result.scalar()

            # Generate daily stats
            for day_offset in range(self.NUM_DAYS):
                current_date = start_date + timedelta(days=day_offset)

                # Only generate stats from publish date onward
                if current_date < publish_date:
                    continue

                days_since_publish = (current_date - publish_date).days

                growth = _daily_growth_curve(days_since_publish, self.NUM_DAYS, video_rng)
                views = int(tier_base * growth)

                # Engagement rate inversely correlated with views, 2-15%
                if views > 50000:
                    engagement_rate = video_rng.uniform(0.015, 0.05)
                elif views > 5000:
                    engagement_rate = video_rng.uniform(0.03, 0.08)
                else:
                    engagement_rate = video_rng.uniform(0.05, 0.15)

                likes = int(views * engagement_rate * video_rng.uniform(0.6, 1.0))
                comments = int(likes * video_rng.uniform(0.05, 0.2))
                shares = int(likes * video_rng.uniform(0.02, 0.15))
                downloads = int(views * video_rng.uniform(0.001, 0.02))

                await session.execute(
                    text("""
                        INSERT INTO daily_stats
                            (video_id, date, play_count, like_count, comment_count, share_count, download_count)
                        VALUES (:video_id, :date, :play_count, :like_count, :comment_count, :share_count, :download_count)
                    """),
                    {
                        "video_id": video_id,
                        "date": current_date,
                        "play_count": max(0, views),
                        "like_count": max(0, likes),
                        "comment_count": max(0, comments),
                        "share_count": max(0, shares),
                        "download_count": max(0, downloads),
                    },
                )

        # Mark database as seeded
        await session.execute(
            text("""
                INSERT INTO app_config (key, value)
                VALUES ('data_seeded', 'true')
            """),
        )
