"""ML-based stalker scoring using scikit-learn and numpy.

Computes 8 weighted features and classifies users into risk categories
using local statistical methods. No external AI API calls are used.
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.preprocessing import MinMaxScaler
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

FEATURE_WEIGHTS = {
    "story_view_frequency": 0.20,
    "story_view_consistency": 0.25,
    "reaction_speed_score": 0.20,
    "view_timing_variance": 0.10,
    "online_during_my_active_hours": 0.10,
    "mutual_group_activity": 0.05,
    "read_without_reply_ratio": 0.05,
    "profile_content_engagement": 0.05,
}

CLASSIFICATION_THRESHOLDS = {
    "NORMAL": (0, 25),
    "CURIOUS": (25, 50),
    "SUSPICIOUS": (50, 75),
    "STALKER": (75, 100),
}


class StalkerScorer:
    """Scores users on stalking likelihood using weighted ML features.

    Uses 8 features with predefined weights, normalizes using MinMaxScaler,
    and classifies users into NORMAL, CURIOUS, SUSPICIOUS, or STALKER.
    """

    def __init__(self) -> None:
        """Initialize the StalkerScorer with scaler and settings."""
        self._scaler = MinMaxScaler(feature_range=(0, 100))
        self._settings = get_settings()

    async def update_score(self, user_id: int) -> dict:
        """Compute and update the suspicion score for a specific user.

        Calculates all 8 features, applies weights, normalizes,
        and updates the TrackedUser record in the database.

        Args:
            user_id: The Telegram user ID to score.

        Returns:
            dict: Score details with total_score, classification,
                features dict, and per-feature weighted contributions.
        """
        features = await self._compute_features(user_id)
        weighted_score = self._calculate_weighted_score(features)
        classification = self._classify_score(weighted_score)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if tracked:
                tracked.suspicion_score = weighted_score
                tracked.updated_at = datetime.utcnow()
                await session.commit()

        logger.info(
            f"User {user_id} scored {weighted_score:.1f} ({classification})"
        )

        return {
            "user_id": user_id,
            "total_score": round(weighted_score, 2),
            "classification": classification,
            "features": features,
            "weighted_contributions": {
                k: round(v * FEATURE_WEIGHTS[k] * 100, 2)
                for k, v in features.items()
            },
        }

    async def update_all_scores(self) -> list[dict]:
        """Update suspicion scores for all active tracked users.

        Computes fresh scores for every active user and updates the database.

        Returns:
            list[dict]: List of score details for all tracked users.
        """
        results = []

        async for session in get_session():
            query_result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            tracked_users = query_result.scalars().all()

        for user in tracked_users:
            try:
                score_result = await self.update_score(user.telegram_id)
                results.append(score_result)
            except Exception as e:
                logger.error(
                    f"Error scoring user {user.telegram_id}: {e}"
                )

        if results:
            self._normalize_scores(results)

        logger.info(f"Updated scores for {len(results)} users")
        return results

    async def get_score_history(
        self, user_id: int, days: int = 30
    ) -> list[dict]:
        """Get historical score data for a user over a time period.

        Retrieves all suspicion patterns recorded over the specified
        number of days to track score progression.

        Args:
            user_id: The Telegram user ID to get history for.
            days: Number of days to look back (default 30).

        Returns:
            list[dict]: Chronological list of score snapshots with
                date, score, and pattern_type fields.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        history = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return []

            patterns_result = await session.execute(
                select(SuspicionPattern)
                .where(
                    SuspicionPattern.tracked_user_id == tracked.id,
                    SuspicionPattern.detected_at >= cutoff,
                )
                .order_by(SuspicionPattern.detected_at.asc())
            )
            patterns = patterns_result.scalars().all()

            for pattern in patterns:
                history.append({
                    "date": pattern.detected_at.isoformat(),
                    "score": pattern.confidence * 100,
                    "pattern_type": pattern.pattern_type,
                    "details": pattern.details,
                })

        return history

    async def explain_score(self, user_id: int) -> dict:
        """Provide a detailed explanation of a user's suspicion score.

        Breaks down the score into individual feature contributions
        and provides human-readable explanations for each factor.

        Args:
            user_id: The Telegram user ID to explain score for.

        Returns:
            dict: Detailed breakdown with feature values, weights,
                contributions, and textual explanations.
        """
        features = await self._compute_features(user_id)
        weighted_score = self._calculate_weighted_score(features)
        classification = self._classify_score(weighted_score)

        explanations = {
            "story_view_frequency": "How often this user views your stories",
            "story_view_consistency": "How consistently they view every story",
            "reaction_speed_score": "How quickly they view after posting",
            "view_timing_variance": "Variance in viewing time (low = obsessive)",
            "online_during_my_active_hours": "Overlap with your online hours",
            "mutual_group_activity": "Activity level in shared groups",
            "read_without_reply_ratio": "Messages read without replying",
            "profile_content_engagement": "Engagement with profile content",
        }

        breakdown = []
        for feature_name, value in features.items():
            weight = FEATURE_WEIGHTS[feature_name]
            contribution = value * weight * 100
            breakdown.append({
                "feature": feature_name,
                "raw_value": round(value, 4),
                "weight": weight,
                "contribution": round(contribution, 2),
                "explanation": explanations.get(feature_name, ""),
            })

        breakdown.sort(key=lambda x: x["contribution"], reverse=True)

        return {
            "user_id": user_id,
            "total_score": round(weighted_score, 2),
            "classification": classification,
            "breakdown": breakdown,
            "top_factor": breakdown[0]["feature"] if breakdown else None,
        }

    async def _compute_features(self, user_id: int) -> dict[str, float]:
        """Compute all 8 scoring features for a user.

        Each feature is normalized to [0, 1] range before weighting.

        Args:
            user_id: The Telegram user ID to compute features for.

        Returns:
            dict[str, float]: Feature name to normalized value mapping.
        """
        features = {
            "story_view_frequency": await self._feature_story_view_frequency(user_id),
            "story_view_consistency": await self._feature_story_view_consistency(user_id),
            "reaction_speed_score": await self._feature_reaction_speed(user_id),
            "view_timing_variance": await self._feature_view_timing_variance(user_id),
            "online_during_my_active_hours": await self._feature_online_overlap(user_id),
            "mutual_group_activity": await self._feature_mutual_group_activity(user_id),
            "read_without_reply_ratio": await self._feature_read_without_reply(user_id),
            "profile_content_engagement": await self._feature_profile_engagement(user_id),
        }
        return features

    def _calculate_weighted_score(self, features: dict[str, float]) -> float:
        """Apply weighted formula to compute the final score.

        Args:
            features: Dictionary of feature name to normalized value.

        Returns:
            float: Weighted score in range [0, 100].
        """
        score = sum(
            features.get(name, 0.0) * weight * 100
            for name, weight in FEATURE_WEIGHTS.items()
        )
        return min(100.0, max(0.0, score))

    def _classify_score(self, score: float) -> str:
        """Classify a numeric score into a risk category.

        Args:
            score: Numeric score in range [0, 100].

        Returns:
            str: One of NORMAL, CURIOUS, SUSPICIOUS, or STALKER.
        """
        for classification, (low, high) in CLASSIFICATION_THRESHOLDS.items():
            if low <= score < high:
                return classification
        return "STALKER"

    def _normalize_scores(self, results: list[dict]) -> None:
        """Normalize scores across all users using MinMaxScaler.

        Adjusts scores so they are relative to the current population
        of tracked users. Modifies results in-place.

        Args:
            results: List of score result dictionaries.
        """
        if len(results) < 2:
            return

        scores = np.array([[r["total_score"]] for r in results])
        try:
            normalized = self._scaler.fit_transform(scores)
            for i, result in enumerate(results):
                result["normalized_score"] = round(float(normalized[i][0]), 2)
        except Exception as e:
            logger.debug(f"Normalization skipped: {e}")

    async def _feature_story_view_frequency(self, user_id: int) -> float:
        """Calculate story view frequency feature.

        Measures how often the user views stories in the last 14 days
        normalized by total stories posted.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Normalized frequency score [0, 1].
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            view_count = await session.execute(
                select(func.count(StoryView.id)).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            views = view_count.scalar() or 0

        max_expected_views = 14 * 3
        return min(1.0, views / max_expected_views) if max_expected_views > 0 else 0.0

    async def _feature_story_view_consistency(self, user_id: int) -> float:
        """Calculate story view consistency feature.

        Measures how consistently the user views every posted story.
        High consistency indicates deliberate monitoring.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Consistency score [0, 1] where 1.0 means views every story.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            views_result = await session.execute(
                select(StoryView.story_id)
                .where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
                .distinct()
            )
            unique_stories_viewed = len(views_result.scalars().all())

            total_stories_result = await session.execute(
                select(func.count(func.distinct(StoryView.story_id))).where(
                    StoryView.viewed_at >= cutoff
                )
            )
            total_stories = total_stories_result.scalar() or 0

        if total_stories == 0:
            return 0.0
        return min(1.0, unique_stories_viewed / total_stories)

    async def _feature_reaction_speed(self, user_id: int) -> float:
        """Calculate reaction speed score feature.

        Measures how quickly the user views stories after they are posted.
        Faster views get higher scores.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Speed score [0, 1] where 1.0 means immediate views.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            views = views_result.scalars().all()

        if not views:
            return 0.0

        view_orders = [v.view_order for v in views if v.view_order is not None]
        if not view_orders:
            return 0.0

        avg_position = np.mean(view_orders)
        speed_score = max(0.0, 1.0 - (avg_position / 50.0))
        return min(1.0, speed_score)

    async def _feature_view_timing_variance(self, user_id: int) -> float:
        """Calculate view timing variance feature.

        Low variance in viewing times indicates obsessive/scheduled behavior.
        Returns inverted variance so low variance = high score.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Inverted variance score [0, 1] where 1.0 means very consistent timing.
        """
        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            views_result = await session.execute(
                select(StoryView.viewed_at).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            view_times = views_result.scalars().all()

        if len(view_times) < 3:
            return 0.0

        hours = np.array([vt.hour + vt.minute / 60.0 for vt in view_times])
        variance = float(np.var(hours))
        max_variance = 36.0
        normalized_variance = min(1.0, variance / max_variance)
        return 1.0 - normalized_variance

    async def _feature_online_overlap(self, user_id: int) -> float:
        """Calculate online time overlap feature.

        Measures how often the user is online during the owner's
        active hours, indicating coordinated monitoring.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Overlap score [0, 1] where 1.0 means always overlapping.
        """
        cutoff = datetime.utcnow() - timedelta(days=7)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            events_result = await session.execute(
                select(OnlineEvent).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            events = events_result.scalars().all()

        if not events:
            return 0.0

        overlap_count = sum(1 for e in events if e.overlaps_with_me)
        return overlap_count / len(events) if events else 0.0

    async def _feature_mutual_group_activity(self, user_id: int) -> float:
        """Calculate mutual group activity feature.

        Checks suspicion patterns related to group activity for scoring.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Activity score [0, 1].
        """
        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            pattern_result = await session.execute(
                select(SuspicionPattern).where(
                    SuspicionPattern.tracked_user_id == tracked.id,
                    SuspicionPattern.pattern_type == "GROUP_STALKER",
                )
            )
            patterns = pattern_result.scalars().all()

        if not patterns:
            return 0.0

        max_confidence = max(p.confidence for p in patterns)
        return min(1.0, max_confidence)

    async def _feature_read_without_reply(self, user_id: int) -> float:
        """Calculate read-without-reply ratio feature.

        Uses cached message tracking data to get the ratio.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Ratio [0, 1] where 1.0 means never replies.
        """
        try:
            from userbot.message_tracker import MessageTracker

            tracker = MessageTracker()
            ratio = await tracker.calculate_read_without_reply_ratio(user_id)
            return min(1.0, ratio)
        except Exception:
            return 0.0

    async def _feature_profile_engagement(self, user_id: int) -> float:
        """Calculate profile content engagement feature.

        Measures engagement with bio links and profile content via
        BioLinkVisit records matched to this user.

        Args:
            user_id: The Telegram user ID.

        Returns:
            float: Engagement score [0, 1].
        """
        from core.models import BioLinkVisit

        cutoff = datetime.utcnow() - timedelta(days=14)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return 0.0

            visits_result = await session.execute(
                select(func.count(BioLinkVisit.id)).where(
                    BioLinkVisit.matched_user_id == tracked.id,
                    BioLinkVisit.visited_at >= cutoff,
                )
            )
            visit_count = visits_result.scalar() or 0

        max_expected = 10
        return min(1.0, visit_count / max_expected)
