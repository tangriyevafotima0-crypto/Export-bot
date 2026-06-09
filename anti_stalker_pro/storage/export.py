"""Data export module for CSV, JSON, and PDF output.

Provides utilities for exporting tracked user data in multiple formats
and archiving old records.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import (
    BioLinkVisit,
    OnlineEvent,
    StoryView,
    SuspicionPattern,
    TrackedUser,
)

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
EXPORT_DIR = DATA_DIR / "exports"
ARCHIVE_DIR = DATA_DIR / "archive"


class DataExporter:
    """Handles data export in CSV, JSON, and PDF formats.

    All exports are saved to the data/exports/ directory with timestamped filenames.
    """

    def __init__(self) -> None:
        """Initialize the DataExporter and ensure output directories exist."""
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    async def export_csv(self, user_id: int, data_type: str = "story_views") -> Optional[str]:
        """Export user data to a CSV file.

        Args:
            user_id: Telegram user ID to export data for.
            data_type: Type of data to export ('story_views', 'online_events', 'patterns').

        Returns:
            str: Path to the created CSV file, or None on failure.
        """
        async for session in get_session():
            tracked_result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = tracked_result.scalar_one_or_none()
            if not tracked:
                logger.warning(f"Cannot export: user {user_id} not found")
                return None

            if data_type == "story_views":
                result = await session.execute(
                    select(StoryView)
                    .where(StoryView.tracked_user_id == tracked.id)
                    .order_by(StoryView.viewed_at.desc())
                )
                records = result.scalars().all()
                headers = ["id", "story_id", "viewed_at", "view_order", "reaction"]
                rows = [
                    [r.id, r.story_id, r.viewed_at.isoformat(), r.view_order, r.reaction]
                    for r in records
                ]
            elif data_type == "online_events":
                result = await session.execute(
                    select(OnlineEvent)
                    .where(OnlineEvent.tracked_user_id == tracked.id)
                    .order_by(OnlineEvent.went_online.desc())
                )
                records = result.scalars().all()
                headers = ["id", "went_online", "went_offline", "duration_seconds", "overlaps_with_me"]
                rows = [
                    [r.id, r.went_online.isoformat(), r.went_offline.isoformat() if r.went_offline else "", r.duration_seconds, r.overlaps_with_me]
                    for r in records
                ]
            elif data_type == "patterns":
                result = await session.execute(
                    select(SuspicionPattern)
                    .where(SuspicionPattern.tracked_user_id == tracked.id)
                    .order_by(SuspicionPattern.detected_at.desc())
                )
                records = result.scalars().all()
                headers = ["id", "pattern_type", "confidence", "details", "detected_at"]
                rows = [
                    [r.id, r.pattern_type, r.confidence, json.dumps(r.details) if r.details else "", r.detected_at.isoformat()]
                    for r in records
                ]
            else:
                logger.warning(f"Unknown data_type: {data_type}")
                return None

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{user_id}_{data_type}_{timestamp}.csv"
        filepath = EXPORT_DIR / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        logger.info(f"CSV export created: {filepath} ({len(rows)} rows)")
        return str(filepath)

    async def export_json(self, user_id: int) -> Optional[str]:
        """Export all data for a user as a JSON file.

        Includes tracked user info, story views, online events, and patterns.

        Args:
            user_id: Telegram user ID to export.

        Returns:
            str: Path to the created JSON file, or None on failure.
        """
        async for session in get_session():
            tracked_result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = tracked_result.scalar_one_or_none()
            if not tracked:
                logger.warning(f"Cannot export: user {user_id} not found")
                return None

            story_result = await session.execute(
                select(StoryView).where(StoryView.tracked_user_id == tracked.id)
            )
            story_views = story_result.scalars().all()

            online_result = await session.execute(
                select(OnlineEvent).where(OnlineEvent.tracked_user_id == tracked.id)
            )
            online_events = online_result.scalars().all()

            pattern_result = await session.execute(
                select(SuspicionPattern).where(SuspicionPattern.tracked_user_id == tracked.id)
            )
            patterns = pattern_result.scalars().all()

        export_data = {
            "user": {
                "telegram_id": tracked.telegram_id,
                "username": tracked.username,
                "first_name": tracked.first_name,
                "last_name": tracked.last_name,
                "suspicion_score": tracked.suspicion_score,
                "is_active": tracked.is_active,
                "added_at": tracked.added_at.isoformat(),
            },
            "story_views": [
                {
                    "story_id": sv.story_id,
                    "viewed_at": sv.viewed_at.isoformat(),
                    "view_order": sv.view_order,
                    "reaction": sv.reaction,
                }
                for sv in story_views
            ],
            "online_events": [
                {
                    "went_online": oe.went_online.isoformat(),
                    "went_offline": oe.went_offline.isoformat() if oe.went_offline else None,
                    "duration_seconds": oe.duration_seconds,
                    "overlaps_with_me": oe.overlaps_with_me,
                }
                for oe in online_events
            ],
            "patterns": [
                {
                    "pattern_type": p.pattern_type,
                    "confidence": p.confidence,
                    "details": p.details,
                    "detected_at": p.detected_at.isoformat(),
                }
                for p in patterns
            ],
            "exported_at": datetime.utcnow().isoformat(),
        }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{user_id}_full_{timestamp}.json"
        filepath = EXPORT_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON export created: {filepath}")
        return str(filepath)

    async def export_pdf(self, user_id: int) -> Optional[str]:
        """Generate a PDF report for a user.

        Delegates to the ReportGenerator for actual PDF creation.

        Args:
            user_id: Telegram user ID to generate report for.

        Returns:
            str: Path to the generated PDF, or None on failure.
        """
        from bot.report_generator import ReportGenerator

        generator = ReportGenerator()
        pdf_path = await generator.generate_pdf(user_id)
        return pdf_path

    async def archive_old_data(self, days: int = 90) -> dict:
        """Move data older than the specified number of days to archive.

        Exports old records to JSON archive files and removes them from
        the active database.

        Args:
            days: Age threshold in days (default 90).

        Returns:
            dict: Summary of archived records by type.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        archived = {"story_views": 0, "online_events": 0, "patterns": 0}

        async for session in get_session():
            old_views = await session.execute(
                select(StoryView).where(StoryView.viewed_at < cutoff)
            )
            views = old_views.scalars().all()
            archived["story_views"] = len(views)

            old_events = await session.execute(
                select(OnlineEvent).where(OnlineEvent.went_online < cutoff)
            )
            events = old_events.scalars().all()
            archived["online_events"] = len(events)

            old_patterns = await session.execute(
                select(SuspicionPattern).where(SuspicionPattern.detected_at < cutoff)
            )
            patterns = old_patterns.scalars().all()
            archived["patterns"] = len(patterns)

            if any(v > 0 for v in archived.values()):
                archive_data = {
                    "archived_at": datetime.utcnow().isoformat(),
                    "cutoff_date": cutoff.isoformat(),
                    "story_views": [
                        {"story_id": sv.story_id, "viewed_at": sv.viewed_at.isoformat()}
                        for sv in views
                    ],
                    "online_events": [
                        {"went_online": oe.went_online.isoformat(), "duration": oe.duration_seconds}
                        for oe in events
                    ],
                    "patterns": [
                        {"type": p.pattern_type, "confidence": p.confidence, "detected_at": p.detected_at.isoformat()}
                        for p in patterns
                    ],
                }

                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                archive_path = ARCHIVE_DIR / f"archive_{timestamp}.json"
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump(archive_data, f, indent=2)

                for sv in views:
                    await session.delete(sv)
                for oe in events:
                    await session.delete(oe)
                for p in patterns:
                    await session.delete(p)

                await session.commit()
                logger.info(f"Archived old data to {archive_path}: {archived}")

        return archived
