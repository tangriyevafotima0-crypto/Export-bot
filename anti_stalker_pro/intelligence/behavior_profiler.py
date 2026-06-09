"""Behavior profiling module for activity heatmaps and obsession detection.

Builds 7x24 activity heatmaps, detects obsession patterns with
confidence scores, and estimates personality traits from timing data.
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import OnlineEvent, StoryView, TrackedUser

logger = get_logger(__name__)


class BehaviorProfiler:
    """Profiles user behavior through heatmaps and pattern detection.

    Builds activity intensity matrices, identifies obsession patterns,
    and estimates personality traits based on behavioral timing.
    """

    def __init__(self) -> None:
        """Initialize the BehaviorProfiler with settings."""
        self._settings = get_settings()

    async def build_heatmap(self, user_id: int) -> list[list[float]]:
        """Build a 7x24 activity intensity heatmap for a user.

        Creates a matrix where rows represent days of the week (Monday=0)
        and columns represent hours (0-23). Values represent normalized
        activity intensity.

        Args:
            user_id: The Telegram user ID to build heatmap for.

        Returns:
            list[list[float]]: 7x24 matrix of activity intensity values
                normalized to [0.0, 1.0] range.
        """
        cutoff = datetime.utcnow() - timedelta(days=28)
        heatmap = np.zeros((7, 24), dtype=float)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return heatmap.tolist()

            views_result = await session.execute(
                select(StoryView.viewed_at).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            view_times = views_result.scalars().all()

            events_result = await session.execute(
                select(OnlineEvent.went_online).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            online_times = events_result.scalars().all()

        all_times = list(view_times) + list(online_times)

        for t in all_times:
            day_of_week = t.weekday()
            hour = t.hour
            heatmap[day_of_week][hour] += 1.0

        max_val = heatmap.max()
        if max_val > 0:
            heatmap = heatmap / max_val

        return heatmap.tolist()

    async def detect_obsession_patterns(self, user_id: int) -> list[dict]:
        """Identify obsession patterns with confidence scores.

        Detects NIGHT_STALKER, IMMEDIATE_RESPONDER, DAILY_CHECKER,
        and SILENT_OBSERVER patterns based on behavioral analysis.

        Args:
            user_id: The Telegram user ID to analyze.

        Returns:
            list[dict]: List of detected patterns with pattern_type,
                confidence, and supporting evidence.
        """
        patterns = []
        heatmap = await self.build_heatmap(user_id)
        heatmap_arr = np.array(heatmap)

        night_pattern = self._check_night_obsession(heatmap_arr)
        if night_pattern:
            patterns.append(night_pattern)

        immediate_pattern = await self._check_immediate_obsession(user_id)
        if immediate_pattern:
            patterns.append(immediate_pattern)

        daily_pattern = await self._check_daily_obsession(user_id)
        if daily_pattern:
            patterns.append(daily_pattern)

        silent_pattern = await self._check_silent_obsession(user_id)
        if silent_pattern:
            patterns.append(silent_pattern)

        return patterns

    def _check_night_obsession(self, heatmap: np.ndarray) -> Optional[dict]:
        """Check for NIGHT_STALKER obsession pattern from heatmap.

        Args:
            heatmap: 7x24 numpy array of activity intensity.

        Returns:
            Optional[dict]: Pattern details or None.
        """
        night_hours = heatmap[:, 0:5]
        night_activity = float(night_hours.sum())
        total_activity = float(heatmap.sum())

        if total_activity == 0:
            return None

        night_ratio = night_activity / total_activity
        if night_ratio >= 0.25:
            peak_hour = int(np.argmax(night_hours.sum(axis=0)))
            confidence = min(1.0, night_ratio * 2.0)
            return {
                "pattern_type": "NIGHT_STALKER",
                "confidence": round(confidence, 3),
                "evidence": {
                    "night_activity_percentage": round(night_ratio * 100, 1),
                    "peak_night_hour": peak_hour,
                    "most_active_night_day": int(np.argmax(night_hours.sum(axis=1))),
                },
            }
        return None

    async def _check_immediate_obsession(self, user_id: int) -> Optional[dict]:
        """Check for IMMEDIATE_RESPONDER obsession pattern.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return None

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                    StoryView.view_order.isnot(None),
                )
            )
            views = views_result.scalars().all()

        if len(views) < 3:
            return None

        positions = [v.view_order for v in views if v.view_order is not None]
        avg_position = float(np.mean(positions))
        top_3_count = len([p for p in positions if p <= 3])
        top_3_ratio = top_3_count / len(positions)

        if top_3_ratio >= 0.4:
            confidence = min(1.0, top_3_ratio * (1.0 - avg_position / 30.0))
            return {
                "pattern_type": "IMMEDIATE_RESPONDER",
                "confidence": round(max(0.0, confidence), 3),
                "evidence": {
                    "average_position": round(avg_position, 1),
                    "top_3_ratio": round(top_3_ratio, 3),
                    "total_tracked_views": len(positions),
                },
            }
        return None

    async def _check_daily_obsession(self, user_id: int) -> Optional[dict]:
        """Check for DAILY_CHECKER obsession pattern.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return None

            views_result = await session.execute(
                select(StoryView.viewed_at).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            view_times = views_result.scalars().all()

            events_result = await session.execute(
                select(OnlineEvent.went_online).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            online_times = events_result.scalars().all()

        all_times = list(view_times) + list(online_times)
        if len(all_times) < 5:
            return None

        unique_days = set(t.date() for t in all_times)
        day_coverage = len(unique_days) / 14.0

        if day_coverage >= 0.5:
            confidence = min(1.0, day_coverage * 1.2)
            return {
                "pattern_type": "DAILY_CHECKER",
                "confidence": round(confidence, 3),
                "evidence": {
                    "days_active": len(unique_days),
                    "day_coverage_percent": round(day_coverage * 100, 1),
                    "total_events": len(all_times),
                },
            }
        return None

    async def _check_silent_obsession(self, user_id: int) -> Optional[dict]:
        """Check for SILENT_OBSERVER obsession pattern.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return None

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            views = views_result.scalars().all()

        if len(views) < 5:
            return None

        reactions = [v for v in views if v.reaction is not None]
        reaction_ratio = len(reactions) / len(views)

        if reaction_ratio <= 0.05:
            confidence = min(1.0, (1.0 - reaction_ratio) * len(views) / 20.0)
            return {
                "pattern_type": "SILENT_OBSERVER",
                "confidence": round(min(1.0, confidence), 3),
                "evidence": {
                    "total_views": len(views),
                    "reactions_given": len(reactions),
                    "silence_ratio": round(1.0 - reaction_ratio, 3),
                },
            }
        return None

    async def rebuild_all_profiles(self) -> list[dict]:
        """Rebuild behavior profiles for all active tracked users.

        Iterates all active tracked users, builds heatmaps and detects
        obsession patterns for each one.

        Returns:
            list[dict]: List of profile dicts with user_id, heatmap, and patterns.
        """
        profiles = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            users = result.scalars().all()

        for user in users:
            try:
                heatmap = await self.build_heatmap(user.telegram_id)
                patterns = await self.detect_obsession_patterns(user.telegram_id)
                profiles.append({
                    "user_id": user.telegram_id,
                    "heatmap": heatmap,
                    "patterns": patterns,
                })
            except Exception as e:
                logger.error(
                    f"Failed to rebuild profile for {user.telegram_id}: {e}"
                )

        return profiles

    async def get_personality_estimate(self, user_id: int) -> dict:
        """Estimate personality traits based on behavior timing patterns.

        Analyzes activity timing to infer traits like conscientiousness,
        impulsivity, obsessiveness, and social avoidance.

        Args:
            user_id: The Telegram user ID to profile.

        Returns:
            dict: Personality estimates with trait names as keys and
                float values [0, 1] indicating trait strength.
        """
        heatmap = await self.build_heatmap(user_id)
        heatmap_arr = np.array(heatmap)

        total_activity = float(heatmap_arr.sum())
        if total_activity == 0:
            return {
                "conscientiousness": 0.0,
                "impulsivity": 0.0,
                "obsessiveness": 0.0,
                "social_avoidance": 0.0,
                "regularity": 0.0,
            }

        work_hours = heatmap_arr[:, 9:17]
        night_hours = heatmap_arr[:, 0:5]
        weekend_activity = heatmap_arr[5:7, :].sum()
        weekday_activity = heatmap_arr[0:5, :].sum()

        hour_totals = heatmap_arr.sum(axis=0)
        hour_variance = float(np.var(hour_totals))
        max_hour_variance = 1.0

        regularity = 1.0 - min(1.0, hour_variance / max_hour_variance) if max_hour_variance > 0 else 0.0

        day_totals = heatmap_arr.sum(axis=1)
        day_variance = float(np.var(day_totals))
        conscientiousness = min(1.0, float(work_hours.sum()) / total_activity) if total_activity > 0 else 0.0

        night_ratio = float(night_hours.sum()) / total_activity if total_activity > 0 else 0.0
        social_avoidance = min(1.0, night_ratio * 2.0)

        patterns = await self.detect_obsession_patterns(user_id)
        obsessiveness = 0.0
        if patterns:
            obsessiveness = max(p["confidence"] for p in patterns)

        cutoff = datetime.utcnow() - timedelta(days=14)
        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            impulsivity = 0.0
            if tracked:
                views_result = await session.execute(
                    select(StoryView).where(
                        StoryView.tracked_user_id == tracked.id,
                        StoryView.viewed_at >= cutoff,
                        StoryView.view_order.isnot(None),
                    )
                )
                views = views_result.scalars().all()
                if views:
                    positions = [v.view_order for v in views if v.view_order]
                    if positions:
                        avg_pos = float(np.mean(positions))
                        impulsivity = max(0.0, 1.0 - avg_pos / 50.0)

        return {
            "conscientiousness": round(conscientiousness, 3),
            "impulsivity": round(impulsivity, 3),
            "obsessiveness": round(obsessiveness, 3),
            "social_avoidance": round(social_avoidance, 3),
            "regularity": round(regularity, 3),
        }
