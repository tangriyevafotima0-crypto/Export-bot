"""Timeline construction for chronological event visualization.

Builds chronological event timelines from all data sources and
formats them for Chart.js dashboard visualization.
"""

from datetime import datetime, timedelta, date
from typing import Optional

from sqlalchemy import select, or_

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import (
    Alert,
    BioLinkVisit,
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)

logger = get_logger(__name__)


class TimelineBuilder:
    """Builds chronological event timelines for tracked users.

    Aggregates data from story views, online events, patterns, and alerts
    into a unified timeline suitable for dashboard visualization.
    """

    def __init__(self) -> None:
        """Initialize the TimelineBuilder with settings."""
        self._settings = get_settings()

    async def build_timeline(
        self, user_id: int, days: int = 30
    ) -> list[dict]:
        """Construct a chronological event list from all data sources.

        Aggregates story views, online events, suspicion patterns, and
        alerts into a single sorted timeline.

        Args:
            user_id: The Telegram user ID to build timeline for.
            days: Number of days to include (default 30).

        Returns:
            list[dict]: Chronological list of events, each with
                timestamp, event_type, and event-specific details.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        events = []

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return []

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= cutoff,
                )
            )
            for view in views_result.scalars().all():
                events.append({
                    "timestamp": view.viewed_at.isoformat(),
                    "event_type": "story_view",
                    "details": {
                        "story_id": view.story_id,
                        "view_order": view.view_order,
                        "reaction": view.reaction,
                    },
                })

            online_result = await session.execute(
                select(OnlineEvent).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= cutoff,
                )
            )
            for event in online_result.scalars().all():
                events.append({
                    "timestamp": event.went_online.isoformat(),
                    "event_type": "online",
                    "details": {
                        "went_offline": event.went_offline.isoformat() if event.went_offline else None,
                        "duration_seconds": event.duration_seconds,
                        "overlaps_with_me": event.overlaps_with_me,
                    },
                })

            patterns_result = await session.execute(
                select(SuspicionPattern).where(
                    SuspicionPattern.tracked_user_id == tracked.id,
                    SuspicionPattern.detected_at >= cutoff,
                )
            )
            for pattern in patterns_result.scalars().all():
                events.append({
                    "timestamp": pattern.detected_at.isoformat(),
                    "event_type": "pattern_detected",
                    "details": {
                        "pattern_type": pattern.pattern_type,
                        "confidence": pattern.confidence,
                        "pattern_details": pattern.details,
                    },
                })

            alerts_result = await session.execute(
                select(Alert).where(
                    Alert.tracked_user_id == tracked.id,
                    Alert.created_at >= cutoff,
                )
            )
            for alert in alerts_result.scalars().all():
                events.append({
                    "timestamp": alert.created_at.isoformat(),
                    "event_type": "alert",
                    "details": {
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "is_acknowledged": alert.is_acknowledged,
                    },
                })

            visits_result = await session.execute(
                select(BioLinkVisit).where(
                    BioLinkVisit.matched_user_id == tracked.id,
                    BioLinkVisit.visited_at >= cutoff,
                )
            )
            for visit in visits_result.scalars().all():
                events.append({
                    "timestamp": visit.visited_at.isoformat(),
                    "event_type": "bio_link_visit",
                    "details": {
                        "link_id": visit.link_id,
                        "country": visit.country,
                        "city": visit.city,
                    },
                })

        events.sort(key=lambda x: x["timestamp"])
        return events

    def format_for_dashboard(self, timeline: list[dict]) -> dict:
        """Format a timeline for Chart.js visualization.

        Converts the event timeline into a Chart.js-compatible data
        structure with labels, datasets, and color coding by event type.

        Args:
            timeline: List of timeline event dictionaries.

        Returns:
            dict: Chart.js compatible data with labels, datasets array,
                and per-type color configuration.
        """
        event_types = {
            "story_view": {"label": "Story Views", "color": "#FF6384", "data": []},
            "online": {"label": "Online Events", "color": "#36A2EB", "data": []},
            "pattern_detected": {"label": "Patterns", "color": "#FFCE56", "data": []},
            "alert": {"label": "Alerts", "color": "#FF0000", "data": []},
            "bio_link_visit": {"label": "Link Visits", "color": "#4BC0C0", "data": []},
        }

        labels = set()
        daily_counts: dict[str, dict[str, int]] = {}

        for event in timeline:
            day = event["timestamp"][:10]
            labels.add(day)
            event_type = event["event_type"]

            if day not in daily_counts:
                daily_counts[day] = {et: 0 for et in event_types}
            if event_type in daily_counts[day]:
                daily_counts[day][event_type] += 1

        sorted_labels = sorted(labels)

        datasets = []
        for event_type, config in event_types.items():
            data_points = [
                daily_counts.get(day, {}).get(event_type, 0)
                for day in sorted_labels
            ]
            datasets.append({
                "label": config["label"],
                "data": data_points,
                "backgroundColor": config["color"],
                "borderColor": config["color"],
                "fill": False,
            })

        return {
            "labels": sorted_labels,
            "datasets": datasets,
        }

    async def get_daily_summary(
        self, user_id: int, target_date: date
    ) -> dict:
        """Get a detailed summary for a single day.

        Provides counts, peak activity hour, and notable events
        for the specified date.

        Args:
            user_id: The Telegram user ID.
            target_date: The specific date to summarize.

        Returns:
            dict: Daily summary with event_count, peak_hour,
                events_by_type, and notable_events fields.
        """
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return {
                    "date": target_date.isoformat(),
                    "event_count": 0,
                    "peak_hour": None,
                    "events_by_type": {},
                    "notable_events": [],
                }

            views_result = await session.execute(
                select(StoryView).where(
                    StoryView.tracked_user_id == tracked.id,
                    StoryView.viewed_at >= start,
                    StoryView.viewed_at < end,
                )
            )
            views = views_result.scalars().all()

            events_result = await session.execute(
                select(OnlineEvent).where(
                    OnlineEvent.tracked_user_id == tracked.id,
                    OnlineEvent.went_online >= start,
                    OnlineEvent.went_online < end,
                )
            )
            online_events = events_result.scalars().all()

            alerts_result = await session.execute(
                select(Alert).where(
                    Alert.tracked_user_id == tracked.id,
                    Alert.created_at >= start,
                    Alert.created_at < end,
                )
            )
            alerts = alerts_result.scalars().all()

        all_hours = []
        for v in views:
            all_hours.append(v.viewed_at.hour)
        for e in online_events:
            all_hours.append(e.went_online.hour)

        peak_hour = None
        if all_hours:
            hour_counts: dict[int, int] = {}
            for h in all_hours:
                hour_counts[h] = hour_counts.get(h, 0) + 1
            peak_hour = max(hour_counts, key=hour_counts.get)

        total_events = len(views) + len(online_events) + len(alerts)

        notable_events = []
        for alert in alerts:
            notable_events.append({
                "type": "alert",
                "severity": alert.severity,
                "message": alert.message,
                "time": alert.created_at.strftime("%H:%M"),
            })
        for view in views:
            if view.view_order and view.view_order <= 3:
                notable_events.append({
                    "type": "early_story_view",
                    "view_order": view.view_order,
                    "story_id": view.story_id,
                    "time": view.viewed_at.strftime("%H:%M"),
                })

        return {
            "date": target_date.isoformat(),
            "event_count": total_events,
            "peak_hour": peak_hour,
            "events_by_type": {
                "story_views": len(views),
                "online_events": len(online_events),
                "alerts": len(alerts),
            },
            "notable_events": notable_events,
        }
