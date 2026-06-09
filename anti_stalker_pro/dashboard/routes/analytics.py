"""Analytics API routes for the dashboard.

Provides endpoints for overview stats, heatmaps, score history,
and pattern analysis data.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from core.database import get_session
from core.logger import get_logger
from core.models import (
    Alert,
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)
from dashboard.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview(user: dict = Depends(get_current_user)) -> dict:
    """Get overview statistics for the dashboard.

    Returns total targets, today's events, alert count, and top suspicious users.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    async for session in get_session():
        total_targets = await session.execute(
            select(func.count(TrackedUser.id)).where(TrackedUser.is_active.is_(True))
        )
        targets_count = total_targets.scalar() or 0

        today_story_views = await session.execute(
            select(func.count(StoryView.id)).where(StoryView.viewed_at >= today)
        )
        today_views = today_story_views.scalar() or 0

        today_online_events = await session.execute(
            select(func.count(OnlineEvent.id)).where(OnlineEvent.went_online >= today)
        )
        today_online = today_online_events.scalar() or 0

        today_alerts = await session.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= today)
        )
        alerts_count = today_alerts.scalar() or 0

        top_suspects_result = await session.execute(
            select(TrackedUser)
            .where(TrackedUser.is_active.is_(True))
            .order_by(TrackedUser.suspicion_score.desc())
            .limit(5)
        )
        top_suspects = top_suspects_result.scalars().all()

    return {
        "total_targets": targets_count,
        "today_events": today_views + today_online,
        "today_alerts": alerts_count,
        "top_suspects": [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "first_name": u.first_name,
                "score": round(u.suspicion_score, 1),
            }
            for u in top_suspects
        ],
    }


@router.get("/heatmap/{user_id}")
async def get_heatmap(user_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Get activity heatmap data for a specific tracked user.

    Returns hourly activity counts over the past 7 days organized by day and hour.

    Args:
        user_id: Telegram user ID to get heatmap for.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)

    async for session in get_session():
        tracked_result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        tracked = tracked_result.scalar_one_or_none()
        if not tracked:
            return {"heatmap": [], "user_id": user_id}

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

    heatmap = [[0] * 24 for _ in range(7)]
    for t in all_times:
        day_idx = t.weekday()
        hour_idx = t.hour
        heatmap[day_idx][hour_idx] += 1

    return {
        "user_id": user_id,
        "heatmap": heatmap,
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "total_events": len(all_times),
    }


@router.get("/score-history/{user_id}")
async def get_score_history(
    user_id: int, days: int = 30, user: dict = Depends(get_current_user)
) -> dict:
    """Get score history for a specific tracked user.

    Args:
        user_id: Telegram user ID to get history for.
        days: Number of days to look back.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    async for session in get_session():
        tracked_result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        tracked = tracked_result.scalar_one_or_none()
        if not tracked:
            return {"history": [], "user_id": user_id}

        patterns_result = await session.execute(
            select(SuspicionPattern)
            .where(
                SuspicionPattern.tracked_user_id == tracked.id,
                SuspicionPattern.detected_at >= cutoff,
            )
            .order_by(SuspicionPattern.detected_at.asc())
        )
        patterns = patterns_result.scalars().all()

    history = [
        {
            "date": p.detected_at.isoformat(),
            "score": round(p.confidence * 100, 1),
            "pattern_type": p.pattern_type,
        }
        for p in patterns
    ]

    return {
        "user_id": user_id,
        "history": history,
        "current_score": round(tracked.suspicion_score, 1) if tracked else 0,
    }


@router.get("/patterns/{user_id}")
async def get_patterns(user_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Get detected patterns for a specific tracked user.

    Args:
        user_id: Telegram user ID to get patterns for.
    """
    async for session in get_session():
        tracked_result = await session.execute(
            select(TrackedUser).where(TrackedUser.telegram_id == user_id)
        )
        tracked = tracked_result.scalar_one_or_none()
        if not tracked:
            return {"patterns": [], "user_id": user_id}

        patterns_result = await session.execute(
            select(SuspicionPattern)
            .where(SuspicionPattern.tracked_user_id == tracked.id)
            .order_by(SuspicionPattern.detected_at.desc())
            .limit(50)
        )
        patterns = patterns_result.scalars().all()

    return {
        "user_id": user_id,
        "patterns": [
            {
                "pattern_type": p.pattern_type,
                "confidence": round(p.confidence, 3),
                "details": p.details,
                "detected_at": p.detected_at.isoformat(),
            }
            for p in patterns
        ],
    }
