"""Anomaly detection using scikit-learn IsolationForest.

Detects sudden interest spikes and schedule changes in tracked users'
behavior using isolation-based anomaly detection on activity features.
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select, func

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import (
    Alert,
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)

logger = get_logger(__name__)


class AnomalyDetector:
    """Detects anomalous behavior spikes using IsolationForest.

    Uses scikit-learn's IsolationForest algorithm to identify users
    whose recent activity deviates significantly from their baseline.
    """

    def __init__(self) -> None:
        """Initialize the AnomalyDetector with IsolationForest model."""
        self._settings = get_settings()
        self._model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100,
        )

    async def run(self) -> list[dict]:
        """Check all tracked users for anomalous behavior spikes.

        Runs IsolationForest on activity features for each tracked user
        comparing recent behavior to historical baseline.

        Returns:
            list[dict]: List of detected anomalies with user_id,
                anomaly_score, anomaly_type, and details.
        """
        anomalies = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = result.scalars().all()

        for user in tracked_users:
            try:
                user_anomalies = await self._analyze_user(user)
                anomalies.extend(user_anomalies)
            except Exception as e:
                logger.error(
                    f"Error detecting anomalies for {user.telegram_id}: {e}"
                )

        if anomalies:
            logger.info(f"Detected {len(anomalies)} anomalies across all users")
        return anomalies

    async def _analyze_user(self, tracked_user: TrackedUser) -> list[dict]:
        """Analyze a single user for anomalous behavior.

        Builds daily feature vectors and uses IsolationForest to detect
        anomalous days.

        Args:
            tracked_user: The TrackedUser record to analyze.

        Returns:
            list[dict]: List of detected anomalies for this user.
        """
        features = await self._build_daily_features(tracked_user)
        if features is None or len(features) < 7:
            return []

        feature_array = np.array(features)

        try:
            self._model.fit(feature_array)
            predictions = self._model.predict(feature_array)
            scores = self._model.decision_function(feature_array)
        except Exception as e:
            logger.debug(f"IsolationForest failed for {tracked_user.telegram_id}: {e}")
            return []

        anomalies = []
        recent_days = min(3, len(predictions))
        for i in range(-recent_days, 0):
            if predictions[i] == -1:
                anomaly_score = float(-scores[i])
                anomaly = {
                    "user_id": tracked_user.telegram_id,
                    "username": tracked_user.username,
                    "anomaly_score": round(anomaly_score, 3),
                    "anomaly_type": "behavior_spike",
                    "day_offset": i,
                    "details": {
                        "features": features[i],
                        "baseline_mean": np.mean(feature_array, axis=0).tolist(),
                        "baseline_std": np.std(feature_array, axis=0).tolist(),
                    },
                }
                anomalies.append(anomaly)

                await self._store_anomaly(tracked_user, anomaly)

        return anomalies

    async def _build_daily_features(
        self, tracked_user: TrackedUser
    ) -> Optional[list[list[float]]]:
        """Build daily feature vectors for IsolationForest input.

        Creates a feature vector per day with: story_views, online_events,
        avg_view_position, night_activity_ratio, total_duration.

        Args:
            tracked_user: The TrackedUser record.

        Returns:
            Optional[list[list[float]]]: List of daily feature vectors,
                or None if insufficient data.
        """
        cutoff = datetime.utcnow() - timedelta(days=28)
        now = datetime.utcnow()

        async for session in get_session():
            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked_user.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            views = views_result.scalars().all()

            events_result = await session.execute(
                select(OnlineEvent).where(
                    OnlineEvent.tracked_user_id == tracked_user.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            online_events = events_result.scalars().all()

        if not views and not online_events:
            return None

        daily_features = []
        for day_offset in range(28):
            day_start = (now - timedelta(days=28 - day_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            day_views = [
                v for v in views if day_start <= v.viewed_at < day_end
            ]
            day_events = [
                e for e in online_events if day_start <= e.went_online < day_end
            ]

            story_view_count = float(len(day_views))
            online_event_count = float(len(day_events))

            positions = [
                v.view_order for v in day_views if v.view_order is not None
            ]
            avg_position = float(np.mean(positions)) if positions else 0.0

            all_hours = [v.viewed_at.hour for v in day_views] + [
                e.went_online.hour for e in day_events
            ]
            night_count = len([h for h in all_hours if 0 <= h < 5])
            night_ratio = night_count / max(len(all_hours), 1)

            total_duration = sum(
                e.duration_seconds for e in day_events
                if e.duration_seconds is not None
            )

            daily_features.append([
                story_view_count,
                online_event_count,
                avg_position,
                night_ratio,
                float(total_duration),
            ])

        return daily_features

    async def detect_sudden_interest(self, user_id: int) -> Optional[dict]:
        """Detect when someone dramatically increases monitoring activity.

        Compares the last 3 days of activity against the previous 11 days
        to identify sudden increases in engagement.

        Args:
            user_id: The Telegram user ID to check.

        Returns:
            Optional[dict]: Detection details or None if no spike detected.
        """
        now = datetime.utcnow()
        recent_start = now - timedelta(days=3)
        baseline_start = now - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return None

            recent_views = await session.execute(
                select(func.count(StoryView.id)).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= recent_start,
                )
            )
            recent_view_count = recent_views.scalar() or 0

            baseline_views = await session.execute(
                select(func.count(StoryView.id)).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= baseline_start,
                    StoryView.viewed_at < recent_start,
                )
            )
            baseline_view_count = baseline_views.scalar() or 0

            recent_events = await session.execute(
                select(func.count(OnlineEvent.id)).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= recent_start,
                )
            )
            recent_event_count = recent_events.scalar() or 0

            baseline_events = await session.execute(
                select(func.count(OnlineEvent.id)).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= baseline_start,
                    OnlineEvent.went_online < recent_start,
                )
            )
            baseline_event_count = baseline_events.scalar() or 0

        baseline_days = 11
        recent_days = 3

        baseline_daily_views = baseline_view_count / max(baseline_days, 1)
        recent_daily_views = recent_view_count / max(recent_days, 1)

        baseline_daily_events = baseline_event_count / max(baseline_days, 1)
        recent_daily_events = recent_event_count / max(recent_days, 1)

        view_increase = (
            (recent_daily_views - baseline_daily_views) / max(baseline_daily_views, 0.1)
        )
        event_increase = (
            (recent_daily_events - baseline_daily_events) / max(baseline_daily_events, 0.1)
        )

        combined_increase = (view_increase + event_increase) / 2.0

        if combined_increase >= 1.5:
            return {
                "user_id": user_id,
                "detected": True,
                "increase_factor": round(combined_increase, 2),
                "details": {
                    "recent_daily_views": round(recent_daily_views, 2),
                    "baseline_daily_views": round(baseline_daily_views, 2),
                    "view_increase_percent": round(view_increase * 100, 1),
                    "recent_daily_events": round(recent_daily_events, 2),
                    "baseline_daily_events": round(baseline_daily_events, 2),
                    "event_increase_percent": round(event_increase * 100, 1),
                },
            }
        return None

    async def detect_schedule_change(self, user_id: int) -> Optional[dict]:
        """Detect when a user's activity patterns shift significantly.

        Compares the hourly distribution of recent activity against
        historical patterns to identify schedule changes.

        Args:
            user_id: The Telegram user ID to check.

        Returns:
            Optional[dict]: Detection details or None if no shift detected.
        """
        now = datetime.utcnow()
        recent_start = now - timedelta(days=7)
        baseline_start = now - timedelta(days=28)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return None

            recent_views = await session.execute(
                select(StoryView.viewed_at).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= recent_start,
                )
            )
            recent_times = recent_views.scalars().all()

            recent_events = await session.execute(
                select(OnlineEvent.went_online).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= recent_start,
                )
            )
            recent_online = recent_events.scalars().all()

            baseline_views = await session.execute(
                select(StoryView.viewed_at).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= baseline_start,
                    StoryView.viewed_at < recent_start,
                )
            )
            baseline_times = baseline_views.scalars().all()

            baseline_events = await session.execute(
                select(OnlineEvent.went_online).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= baseline_start,
                    OnlineEvent.went_online < recent_start,
                )
            )
            baseline_online = baseline_events.scalars().all()

        all_recent = list(recent_times) + list(recent_online)
        all_baseline = list(baseline_times) + list(baseline_online)

        if len(all_recent) < 5 or len(all_baseline) < 5:
            return None

        recent_hours = np.zeros(24)
        for t in all_recent:
            recent_hours[t.hour] += 1
        recent_dist = recent_hours / max(recent_hours.sum(), 1)

        baseline_hours = np.zeros(24)
        for t in all_baseline:
            baseline_hours[t.hour] += 1
        baseline_dist = baseline_hours / max(baseline_hours.sum(), 1)

        kl_divergence = 0.0
        for i in range(24):
            p = recent_dist[i] + 1e-10
            q = baseline_dist[i] + 1e-10
            kl_divergence += p * np.log(p / q)

        recent_peak = int(np.argmax(recent_dist))
        baseline_peak = int(np.argmax(baseline_dist))
        peak_shift = abs(recent_peak - baseline_peak)

        if kl_divergence >= 0.5 or peak_shift >= 4:
            return {
                "user_id": user_id,
                "detected": True,
                "kl_divergence": round(float(kl_divergence), 3),
                "peak_hour_shift": peak_shift,
                "details": {
                    "recent_peak_hour": recent_peak,
                    "baseline_peak_hour": baseline_peak,
                    "recent_distribution": recent_dist.tolist(),
                    "baseline_distribution": baseline_dist.tolist(),
                    "shift_direction": "earlier" if recent_peak < baseline_peak else "later",
                },
            }
        return None

    async def _store_anomaly(
        self, tracked_user: TrackedUser, anomaly: dict
    ) -> None:
        """Store a detected anomaly as a SuspicionPattern and Alert.

        Args:
            tracked_user: The tracked user record.
            anomaly: Anomaly detection details.
        """
        async for session in get_session():
            pattern = SuspicionPattern(
                tracked_user_id=tracked_user.id,
                pattern_type="ANOMALY_SPIKE",
                confidence=min(1.0, anomaly["anomaly_score"]),
                details=anomaly["details"],
                detected_at=datetime.utcnow(),
            )
            session.add(pattern)

            if anomaly["anomaly_score"] >= 0.5:
                alert = Alert(
                    tracked_user_id=tracked_user.id,
                    alert_type="anomaly_detected",
                    severity="high" if anomaly["anomaly_score"] >= 0.8 else "medium",
                    message=(
                        f"Anomalous behavior detected for "
                        f"{tracked_user.username or tracked_user.telegram_id}: "
                        f"score {anomaly['anomaly_score']:.2f}"
                    ),
                    details=anomaly,
                )
                session.add(alert)

            await session.commit()
