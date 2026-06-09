"""Prediction module using pandas time series and numpy statistics.

Provides predictions for next visits, online times, and story viewing
probability using only local statistical methods (no external AI APIs).
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import OnlineEvent, StoryView, TrackedUser

logger = get_logger(__name__)


class Predictor:
    """Predicts user behavior using local statistical methods.

    Uses pandas for time series analysis and numpy for statistical
    predictions. Does not make any external API calls.
    """

    def __init__(self) -> None:
        """Initialize the Predictor with settings."""
        self._settings = get_settings()

    async def predict_next_visit(self, user_id: int) -> dict:
        """Predict when the user will next view a story or come online.

        Uses the last 14 days of activity data to identify timing patterns
        and predict the most likely next activity window.

        Args:
            user_id: The Telegram user ID to predict for.

        Returns:
            dict: Prediction with predicted_time (ISO format),
                confidence_percent (0-100), method used, and
                supporting_data with pattern details.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return self._empty_prediction("No tracked user found")

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

        all_times = sorted(list(view_times) + list(online_times))
        if len(all_times) < 3:
            return self._empty_prediction("Insufficient data for prediction")

        df = pd.DataFrame({"timestamp": all_times})
        df["hour"] = df["timestamp"].apply(lambda t: t.hour)
        df["weekday"] = df["timestamp"].apply(lambda t: t.weekday())
        df["minute_of_day"] = df["timestamp"].apply(
            lambda t: t.hour * 60 + t.minute
        )

        now = datetime.utcnow()
        current_weekday = now.weekday()

        same_day_events = df[df["weekday"] == current_weekday]
        if len(same_day_events) >= 2:
            typical_minutes = same_day_events["minute_of_day"].values
            median_minute = int(np.median(typical_minutes))
            std_minute = float(np.std(typical_minutes))

            predicted_time = now.replace(
                hour=median_minute // 60,
                minute=median_minute % 60,
                second=0,
                microsecond=0,
            )
            if predicted_time <= now:
                predicted_time += timedelta(days=7)

            confidence = max(10, min(90, int(100 - std_minute / 2)))
        else:
            typical_minutes = df["minute_of_day"].values
            median_minute = int(np.median(typical_minutes))
            std_minute = float(np.std(typical_minutes))

            intervals = []
            for i in range(1, len(all_times)):
                delta = (all_times[i] - all_times[i - 1]).total_seconds() / 3600.0
                if delta < 48:
                    intervals.append(delta)

            if intervals:
                avg_interval_hours = float(np.mean(intervals))
                predicted_time = all_times[-1] + timedelta(hours=avg_interval_hours)
                if predicted_time <= now:
                    predicted_time = now.replace(
                        hour=median_minute // 60,
                        minute=median_minute % 60,
                        second=0,
                        microsecond=0,
                    )
                    if predicted_time <= now:
                        predicted_time += timedelta(days=1)
                confidence = max(10, min(70, int(60 - std_minute / 3)))
            else:
                predicted_time = now + timedelta(hours=24)
                confidence = 10

        return {
            "predicted_time": predicted_time.isoformat(),
            "confidence_percent": confidence,
            "method": "time_series_median",
            "supporting_data": {
                "data_points": len(all_times),
                "typical_hour": int(np.median(df["hour"].values)),
                "std_minutes": round(std_minute, 1),
                "most_active_weekday": int(df["weekday"].mode().iloc[0]) if len(df) > 0 else current_weekday,
            },
        }

    async def predict_online_time(self, user_id: int) -> dict:
        """Predict if the user will be online in the next 2 hours.

        Based on weekly patterns of online activity, estimates the
        probability that the user will come online within 2 hours.

        Args:
            user_id: The Telegram user ID to predict for.

        Returns:
            dict: Prediction with probability (0.0-1.0),
                will_be_online (bool), expected_at (ISO format or None),
                and pattern_basis details.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return {
                    "probability": 0.0,
                    "will_be_online": False,
                    "expected_at": None,
                    "pattern_basis": "no_data",
                }

            events_result = await session.execute(
                select(OnlineEvent).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            events = events_result.scalars().all()

        if len(events) < 3:
            return {
                "probability": 0.0,
                "will_be_online": False,
                "expected_at": None,
                "pattern_basis": "insufficient_data",
            }

        now = datetime.utcnow()
        current_weekday = now.weekday()
        current_hour = now.hour
        window_end_hour = (current_hour + 2) % 24

        weekly_pattern = np.zeros((7, 24), dtype=float)
        for event in events:
            weekly_pattern[event.went_online.weekday()][event.went_online.hour] += 1

        total_per_day = weekly_pattern.sum(axis=1)
        if total_per_day[current_weekday] > 0:
            weekly_pattern[current_weekday] /= total_per_day[current_weekday]

        if current_hour < window_end_hour:
            window_hours = range(current_hour, window_end_hour)
        else:
            window_hours = list(range(current_hour, 24)) + list(range(0, window_end_hour))

        probability = 0.0
        for h in window_hours:
            probability += weekly_pattern[current_weekday][h]
        probability = min(1.0, probability)

        expected_at = None
        if probability > 0.3:
            max_hour = current_hour
            max_prob = 0.0
            for h in window_hours:
                if weekly_pattern[current_weekday][h] > max_prob:
                    max_prob = weekly_pattern[current_weekday][h]
                    max_hour = h
            expected_at = now.replace(
                hour=max_hour, minute=30, second=0, microsecond=0
            )
            if expected_at <= now:
                expected_at += timedelta(days=1)

        return {
            "probability": round(probability, 3),
            "will_be_online": probability >= 0.5,
            "expected_at": expected_at.isoformat() if expected_at else None,
            "pattern_basis": {
                "total_events_analyzed": len(events),
                "events_on_same_weekday": int(total_per_day[current_weekday]),
                "window_hours": list(window_hours),
            },
        }

    async def will_view_story(
        self, user_id: int, posted_at: datetime
    ) -> dict:
        """Predict the probability that a user will view a story.

        Analyzes historical story viewing patterns relative to posting time
        to estimate whether this user will view the story.

        Args:
            user_id: The Telegram user ID to predict for.
            posted_at: When the story was/will be posted.

        Returns:
            dict: Prediction with probability (0.0-1.0),
                likely_view_within_hours, and confidence_basis.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return {
                    "probability": 0.0,
                    "likely_view_within_hours": None,
                    "confidence_basis": "no_data",
                }

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            views = views_result.scalars().all()

            total_stories_result = await session.execute(
                select(StoryView.story_id)
                .where(StoryView.viewed_at >= cutoff)
                .distinct()
            )
            total_unique_stories = len(total_stories_result.scalars().all())

        if not views or total_unique_stories == 0:
            return {
                "probability": 0.0,
                "likely_view_within_hours": None,
                "confidence_basis": "insufficient_data",
            }

        unique_stories_viewed = len(set(v.story_id for v in views))
        base_probability = unique_stories_viewed / max(1, total_unique_stories)

        posting_hour = posted_at.hour
        posting_weekday = posted_at.weekday()

        view_hours = [v.viewed_at.hour for v in views]
        view_weekdays = [v.viewed_at.weekday() for v in views]

        hour_match_count = sum(
            1 for h in view_hours if abs(h - posting_hour) <= 2
        )
        hour_factor = hour_match_count / len(views) if views else 0

        weekday_match_count = sum(
            1 for w in view_weekdays if w == posting_weekday
        )
        weekday_factor = weekday_match_count / len(views) if views else 0

        combined_probability = min(
            1.0,
            base_probability * 0.5 + hour_factor * 0.3 + weekday_factor * 0.2,
        )

        likely_within_hours = None
        if views:
            view_positions = [v.view_order for v in views if v.view_order]
            if view_positions:
                avg_position = float(np.mean(view_positions))
                likely_within_hours = max(0.5, min(24.0, avg_position * 0.5))
            else:
                likely_within_hours = 6.0

        return {
            "probability": round(combined_probability, 3),
            "likely_view_within_hours": round(likely_within_hours, 1) if likely_within_hours else None,
            "confidence_basis": {
                "stories_viewed_ratio": round(base_probability, 3),
                "hour_alignment": round(hour_factor, 3),
                "weekday_alignment": round(weekday_factor, 3),
                "total_views_analyzed": len(views),
            },
        }

    def _empty_prediction(self, reason: str) -> dict:
        """Create an empty prediction result with a reason.

        Args:
            reason: Explanation for why no prediction could be made.

        Returns:
            dict: Empty prediction structure with reason.
        """
        return {
            "predicted_time": None,
            "confidence_percent": 0,
            "method": "none",
            "supporting_data": {"reason": reason},
        }
