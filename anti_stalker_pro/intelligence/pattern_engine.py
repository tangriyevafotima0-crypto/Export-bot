"""Pattern detection engine for identifying stalking behaviors.

Runs comprehensive pattern analysis across all tracked users and
identifies specific behavior patterns like NIGHT_STALKER,
IMMEDIATE_RESPONDER, DAILY_CHECKER, and SILENT_OBSERVER.
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select, func

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import (
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)

logger = get_logger(__name__)

PATTERN_TYPES = [
    "NIGHT_STALKER",
    "IMMEDIATE_RESPONDER",
    "DAILY_CHECKER",
    "SILENT_OBSERVER",
]


class PatternEngine:
    """Detects stalking behavior patterns across tracked users.

    Runs deep analysis on activity data to identify specific patterns
    and stores results in the SuspicionPattern database table.
    """

    def __init__(self) -> None:
        """Initialize the PatternEngine with settings."""
        self._settings = get_settings()

    async def deep_analysis(self) -> list[dict]:
        """Run comprehensive pattern detection across all tracked users.

        Analyzes all active tracked users for the four primary patterns
        and records new detections in the database.

        Returns:
            list[dict]: List of detected patterns with user_id, pattern_type,
                confidence, and details.
        """
        all_patterns = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = result.scalars().all()

        for user in tracked_users:
            try:
                patterns = await self.detect_patterns(user.telegram_id)
                all_patterns.extend(patterns)
            except Exception as e:
                logger.error(
                    f"Error analyzing patterns for {user.telegram_id}: {e}"
                )

        logger.info(
            f"Deep analysis complete: {len(all_patterns)} patterns detected "
            f"across {len(tracked_users)} users"
        )
        return all_patterns

    async def detect_patterns(self, user_id: int) -> list[dict]:
        """Identify specific stalking patterns for a user.

        Checks for NIGHT_STALKER, IMMEDIATE_RESPONDER, DAILY_CHECKER,
        and SILENT_OBSERVER patterns based on activity data.

        Args:
            user_id: The Telegram user ID to analyze.

        Returns:
            list[dict]: List of detected patterns with type, confidence, and details.
        """
        detected = []

        night_stalker = await self._detect_night_stalker(user_id)
        if night_stalker:
            detected.append(night_stalker)

        immediate_responder = await self._detect_immediate_responder(user_id)
        if immediate_responder:
            detected.append(immediate_responder)

        daily_checker = await self._detect_daily_checker(user_id)
        if daily_checker:
            detected.append(daily_checker)

        silent_observer = await self._detect_silent_observer(user_id)
        if silent_observer:
            detected.append(silent_observer)

        for pattern in detected:
            await self._store_pattern(user_id, pattern)

        return detected

    async def _detect_night_stalker(self, user_id: int) -> Optional[dict]:
        """Detect NIGHT_STALKER pattern: frequent activity during late hours.

        Users who consistently view stories or go online between 00:00 and 05:00
        are flagged as potential night stalkers.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None if not detected.
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
        if len(all_times) < 3:
            return None

        night_hours = [t for t in all_times if 0 <= t.hour < 5]
        night_ratio = len(night_hours) / len(all_times)

        if night_ratio >= 0.3:
            confidence = min(1.0, night_ratio * 1.5)
            return {
                "pattern_type": "NIGHT_STALKER",
                "confidence": round(confidence, 3),
                "details": {
                    "night_activity_ratio": round(night_ratio, 3),
                    "total_events": len(all_times),
                    "night_events": len(night_hours),
                    "peak_hour": int(np.median([t.hour for t in night_hours])) if night_hours else 2,
                },
            }
        return None

    async def _detect_immediate_responder(self, user_id: int) -> Optional[dict]:
        """Detect IMMEDIATE_RESPONDER pattern: views stories within minutes.

        Users who consistently appear in the first few viewers of stories
        are flagged as immediate responders.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None if not detected.
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
        if not positions:
            return None

        avg_position = float(np.mean(positions))
        early_views = [p for p in positions if p <= 5]
        early_ratio = len(early_views) / len(positions)

        if avg_position <= 10 and early_ratio >= 0.5:
            confidence = min(1.0, early_ratio * (1.0 - avg_position / 50.0))
            return {
                "pattern_type": "IMMEDIATE_RESPONDER",
                "confidence": round(confidence, 3),
                "details": {
                    "average_view_position": round(avg_position, 1),
                    "early_view_ratio": round(early_ratio, 3),
                    "total_views": len(positions),
                    "views_in_top_5": len(early_views),
                },
            }
        return None

    async def _detect_daily_checker(self, user_id: int) -> Optional[dict]:
        """Detect DAILY_CHECKER pattern: views stories every single day.

        Users who view stories on a high percentage of days over the
        analysis period are flagged as daily checkers.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None if not detected.
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

        if len(view_times) < 5:
            return None

        unique_days = set(vt.date() for vt in view_times)
        total_days = 14
        day_coverage = len(unique_days) / total_days

        if day_coverage >= 0.6:
            consecutive = self._longest_consecutive_days(sorted(unique_days))
            confidence = min(1.0, day_coverage * (1.0 + consecutive / 14.0) / 2.0)
            return {
                "pattern_type": "DAILY_CHECKER",
                "confidence": round(confidence, 3),
                "details": {
                    "day_coverage": round(day_coverage, 3),
                    "unique_days": len(unique_days),
                    "total_days": total_days,
                    "longest_streak": consecutive,
                },
            }
        return None

    async def _detect_silent_observer(self, user_id: int) -> Optional[dict]:
        """Detect SILENT_OBSERVER pattern: views everything but never interacts.

        Users who have high story views but no reactions, no messages,
        and no group interactions are flagged as silent observers.

        Args:
            user_id: The Telegram user ID.

        Returns:
            Optional[dict]: Pattern details or None if not detected.
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

            reactions = [v for v in views if v.reaction is not None]

        if len(views) < 5:
            return None

        reaction_ratio = len(reactions) / len(views) if views else 1.0

        if reaction_ratio <= 0.1:
            view_frequency = len(views) / 14.0
            confidence = min(1.0, (1.0 - reaction_ratio) * min(1.0, view_frequency / 2.0))
            return {
                "pattern_type": "SILENT_OBSERVER",
                "confidence": round(confidence, 3),
                "details": {
                    "total_views": len(views),
                    "total_reactions": len(reactions),
                    "reaction_ratio": round(reaction_ratio, 3),
                    "views_per_day": round(view_frequency, 2),
                },
            }
        return None

    def _longest_consecutive_days(self, sorted_dates: list) -> int:
        """Find the longest streak of consecutive days in a sorted date list.

        Args:
            sorted_dates: List of date objects sorted in ascending order.

        Returns:
            int: Length of the longest consecutive day streak.
        """
        if not sorted_dates:
            return 0

        max_streak = 1
        current_streak = 1

        for i in range(1, len(sorted_dates)):
            diff = (sorted_dates[i] - sorted_dates[i - 1]).days
            if diff == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            elif diff > 1:
                current_streak = 1

        return max_streak

    async def _store_pattern(self, user_id: int, pattern: dict) -> None:
        """Store a detected pattern in the SuspicionPattern table.

        Args:
            user_id: The Telegram user ID the pattern was detected for.
            pattern: Pattern details dictionary with pattern_type, confidence, and details.
        """
        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return

            db_pattern = SuspicionPattern(
                tracked_user_id=tracked.id,
                pattern_type=pattern["pattern_type"],
                confidence=pattern["confidence"],
                details=pattern["details"],
                detected_at=datetime.utcnow(),
            )
            session.add(db_pattern)
            await session.commit()

        logger.debug(
            f"Stored pattern {pattern['pattern_type']} for user {user_id} "
            f"(confidence: {pattern['confidence']:.2f})"
        )
