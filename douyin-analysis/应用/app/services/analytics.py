"""Analytics engine — computes engagement rates, trends, and rankings.

All functions are pure: they take data in, return computed results.
This makes them usable with both mock data and real API data.
"""

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


class AnalyticsEngine:
    """Computes advanced metrics on video data."""

    @staticmethod
    def engagement_rate(likes: int, comments: int, shares: int, views: int) -> float:
        """Standard engagement rate formula.

        (likes + comments + shares) / views * 100
        Returns 0.0 if views is 0.
        """
        if views <= 0:
            return 0.0
        return round((likes + comments + shares) / views * 100, 2)

    @staticmethod
    def rolling_average(values: list[float], window: int = 7) -> list[float]:
        """Compute 7-day rolling average for trend smoothing."""
        if len(values) < window:
            return [sum(values) / len(values)] * len(values) if values else []
        s = pd.Series(values)
        return s.rolling(window=window, min_periods=1, center=True).mean().tolist()

    @staticmethod
    def day_over_day_growth(today: int, yesterday: int) -> float:
        """Compute day-over-day growth rate as a percentage."""
        if yesterday <= 0:
            return 0.0
        return round((today - yesterday) / yesterday * 100, 2)

    @staticmethod
    def trend_direction(
        recent_values: list[float], threshold: float = 5.0
    ) -> str:
        """Determine if a metric is trending up, down, or stable.

        Compares the average of the most recent 3 values vs the 3 prior.
        """
        if len(recent_values) < 6:
            return "stable"
        recent = recent_values[-3:]
        prior = recent_values[-6:-3]
        recent_avg = sum(recent) / len(recent) if recent else 0
        prior_avg = sum(prior) / len(prior) if prior else 1
        if prior_avg == 0:
            return "up" if recent_avg > 0 else "stable"
        change = (recent_avg - prior_avg) / prior_avg * 100
        if change > threshold:
            return "up"
        elif change < -threshold:
            return "down"
        return "stable"

    @staticmethod
    def compute_engagement_rate_list(
        records: list[dict],
        like_key: str = "like_count",
        comment_key: str = "comment_count",
        share_key: str = "share_count",
        play_key: str = "play_count",
    ) -> list[float]:
        """Add engagement_rate to a list of stat records."""
        rates = []
        for r in records:
            total = r.get(like_key, 0) + r.get(comment_key, 0) + r.get(share_key, 0)
            plays = r.get(play_key, 1)
            rates.append(round(total / plays * 100, 2) if plays > 0 else 0.0)
        return rates

    @staticmethod
    def top_performing_videos(
        videos: list[dict],
        metric: str = "play_count",
        top_n: int = 10,
    ) -> list[dict]:
        """Sort videos by a metric and return the top N."""
        return sorted(videos, key=lambda v: v.get(metric, 0), reverse=True)[:top_n]

    @staticmethod
    def posting_hour_effectiveness(
        posts: list[dict],
        hour_key: str = "hour",
        engagement_key: str = "engagement",
    ) -> dict[int, float]:
        """Aggregate average engagement by posting hour.

        Args:
            posts: list of {hour: int, engagement: float} dicts
        Returns:
            dict mapping hour (0-23) to average engagement
        """
        hours = {h: [] for h in range(24)}
        for p in posts:
            h = p.get(hour_key, 0)
            if 0 <= h <= 23:
                hours[h].append(p.get(engagement_key, 0))
        return {h: (sum(vals) / len(vals) if vals else 0) for h, vals in hours.items()}

    @staticmethod
    def detect_viral_content(
        videos: list[dict],
        play_threshold: int = 100000,
        engagement_threshold: float = 5.0,
        play_key: str = "play_count",
        like_key: str = "like_count",
        comment_key: str = "comment_count",
        share_key: str = "share_count",
    ) -> list[dict]:
        """Detect potentially viral videos based on thresholds."""
        viral = []
        for v in videos:
            plays = v.get(play_key, 0)
            eng = AnalyticsEngine.engagement_rate(
                v.get(like_key, 0),
                v.get(comment_key, 0),
                v.get(share_key, 0),
                plays,
            )
            if plays >= play_threshold and eng >= engagement_threshold:
                viral.append({**v, "computed_engagement": eng})
        return sorted(viral, key=lambda v: v["computed_engagement"], reverse=True)
