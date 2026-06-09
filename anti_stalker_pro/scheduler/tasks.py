"""Scheduled task definitions for the Anti-Stalker monitoring system.

Defines all periodic tasks with their intervals:
- Every 30s: story check
- Every 60s: online status check
- Every 5min: anomaly detection + alert processing
- Every 1h: score update + prediction update
- Every 6h: deep analysis + profile rebuild
- Daily 03:00: backup + archive
- Daily 21:00: report generation + sending
- Smart task: predictive bait posting when stalker probability > 70%
"""

from datetime import datetime

from core.logger import get_logger

logger = get_logger(__name__)


def register_all_tasks(task_manager) -> None:
    """Register all scheduled tasks with the task manager.

    Configures all monitoring intervals as specified in the architecture.

    Args:
        task_manager: The TaskManager instance to register tasks with.
    """
    task_manager.add_job(
        func=task_check_stories,
        trigger="interval",
        job_id="check_stories",
        seconds=30,
    )

    task_manager.add_job(
        func=task_check_online,
        trigger="interval",
        job_id="check_online",
        seconds=60,
    )

    task_manager.add_job(
        func=task_anomaly_detection,
        trigger="interval",
        job_id="anomaly_detection",
        minutes=5,
    )

    task_manager.add_job(
        func=task_process_alerts,
        trigger="interval",
        job_id="process_alerts",
        minutes=5,
    )

    task_manager.add_job(
        func=task_update_scores,
        trigger="interval",
        job_id="update_scores",
        hours=1,
    )

    task_manager.add_job(
        func=task_update_predictions,
        trigger="interval",
        job_id="update_predictions",
        hours=1,
    )

    task_manager.add_job(
        func=task_deep_analysis,
        trigger="interval",
        job_id="deep_analysis",
        hours=6,
    )

    task_manager.add_job(
        func=task_rebuild_profiles,
        trigger="interval",
        job_id="rebuild_profiles",
        hours=6,
    )

    task_manager.add_job(
        func=task_daily_backup,
        trigger="cron",
        job_id="daily_backup",
        hour=3,
        minute=0,
    )

    task_manager.add_job(
        func=task_daily_report,
        trigger="cron",
        job_id="daily_report",
        hour=21,
        minute=0,
    )

    task_manager.add_job(
        func=task_smart_bait,
        trigger="interval",
        job_id="smart_bait",
        minutes=30,
    )

    logger.info("All scheduled tasks registered")


async def task_check_stories() -> None:
    """Check all stories for views by tracked users.

    Runs every 30 seconds to detect new story views by monitored users.
    """
    try:
        from userbot.story_tracker import StoryTracker

        tracker = StoryTracker()
        new_views = await tracker.check_all_stories()
        if new_views > 0:
            logger.info(f"Story check found {new_views} new views")
    except Exception as e:
        logger.error(f"Story check task failed: {e}")


async def task_check_online() -> None:
    """Check online status of all tracked users.

    Runs every 60 seconds to record online/offline transitions.
    """
    try:
        from userbot.online_tracker import OnlineTracker

        tracker = OnlineTracker()
        changes = await tracker.check_all_tracked_users()
        if changes > 0:
            logger.debug(f"Online check detected {changes} status changes")
    except Exception as e:
        logger.error(f"Online check task failed: {e}")


async def task_anomaly_detection() -> None:
    """Run anomaly detection on recent activity data.

    Runs every 5 minutes to identify unusual behavior patterns
    that may indicate escalating stalking activity.
    """
    try:
        from intelligence.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector()
        anomalies = await detector.detect_anomalies()
        if anomalies:
            logger.info(f"Anomaly detection found {len(anomalies)} anomalies")

            from bot.alert_manager import AlertManager
            alert_manager = AlertManager()
            for anomaly in anomalies:
                await alert_manager.create_alert(
                    alert_type="anomaly_detected",
                    severity=anomaly.get("severity", "warning"),
                    user_id=anomaly.get("user_id", 0),
                    message=anomaly.get("description", "Anomaly detected"),
                    details=anomaly,
                )
    except Exception as e:
        logger.error(f"Anomaly detection task failed: {e}")


async def task_process_alerts() -> None:
    """Process and send pending alerts.

    Runs every 5 minutes to deliver queued alerts while respecting
    rate limits, quiet hours, and duplicate suppression rules.
    """
    try:
        from bot.alert_manager import AlertManager

        manager = AlertManager()
        sent = await manager.process_pending()
        if sent > 0:
            logger.info(f"Alert processing sent {sent} alerts")
    except Exception as e:
        logger.error(f"Alert processing task failed: {e}")


async def task_update_scores() -> None:
    """Update suspicion scores for all tracked users.

    Runs every hour to recompute ML-based scores using the latest
    activity data.
    """
    try:
        from intelligence.ml_scorer import StalkerScorer

        scorer = StalkerScorer()
        results = await scorer.update_all_scores()
        logger.info(f"Score update completed for {len(results)} users")
    except Exception as e:
        logger.error(f"Score update task failed: {e}")


async def task_update_predictions() -> None:
    """Update predictions for all active tracked users.

    Runs every hour to refresh next-visit and online predictions.
    """
    try:
        from sqlalchemy import select
        from core.database import get_session
        from core.models import TrackedUser
        from intelligence.predictor import Predictor

        predictor = Predictor()

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.is_active.is_(True))
            )
            users = result.scalars().all()

        for user in users:
            try:
                await predictor.predict_next_visit(user.telegram_id)
            except Exception as e:
                logger.debug(f"Prediction failed for {user.telegram_id}: {e}")

        logger.debug(f"Predictions updated for {len(users)} users")
    except Exception as e:
        logger.error(f"Prediction update task failed: {e}")


async def task_deep_analysis() -> None:
    """Run deep pattern analysis on all tracked users.

    Runs every 6 hours to identify long-term behavioral patterns
    and detect complex multi-signal indicators.
    """
    try:
        from intelligence.pattern_engine import PatternEngine

        engine = PatternEngine()
        patterns = await engine.analyze_all_users()
        logger.info(f"Deep analysis found {len(patterns)} patterns")
    except Exception as e:
        logger.error(f"Deep analysis task failed: {e}")


async def task_rebuild_profiles() -> None:
    """Rebuild behavior profiles for all tracked users.

    Runs every 6 hours to update the behavioral profile models
    with the latest activity data.
    """
    try:
        from intelligence.behavior_profiler import BehaviorProfiler

        profiler = BehaviorProfiler()
        profiles = await profiler.rebuild_all_profiles()
        logger.info(f"Profile rebuild completed for {len(profiles)} users")
    except Exception as e:
        logger.error(f"Profile rebuild task failed: {e}")


async def task_daily_backup() -> None:
    """Create a daily database backup.

    Runs at 03:00 UTC daily. Copies the SQLite database to the
    backups directory with a date-stamped filename.
    """
    import shutil
    from pathlib import Path

    try:
        data_dir = Path(__file__).parent.parent / "data"
        backup_dir = data_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        db_path = data_dir / "anti_stalker.db"
        if db_path.exists():
            date_str = datetime.utcnow().strftime("%Y%m%d")
            backup_path = backup_dir / f"backup_{date_str}.db"
            shutil.copy2(str(db_path), str(backup_path))
            logger.info(f"Daily backup created: {backup_path}")

            _cleanup_old_backups(backup_dir, keep_days=30)
        else:
            logger.debug("No database file to backup")
    except Exception as e:
        logger.error(f"Daily backup task failed: {e}")


async def task_daily_report() -> None:
    """Generate and send the daily monitoring report.

    Runs at 21:00 UTC daily. Creates a PDF report and sends it
    via the Telegram bot notification system.
    """
    try:
        from bot.report_generator import ReportGenerator
        from bot.notifier import Notifier

        generator = ReportGenerator()
        pdf_path = await generator.generate_daily_summary()

        from sqlalchemy import select, func
        from core.database import get_session
        from core.models import TrackedUser, StoryView, OnlineEvent, Alert
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=24)

        async for session in get_session():
            views_count = await session.execute(
                select(func.count(StoryView.id)).where(
                    StoryView.viewed_at >= cutoff
                )
            )
            total_views = views_count.scalar() or 0

            alerts_count = await session.execute(
                select(func.count(Alert.id)).where(
                    Alert.created_at >= cutoff
                )
            )
            total_alerts = alerts_count.scalar() or 0

            targets_result = await session.execute(
                select(TrackedUser)
                .where(TrackedUser.is_active.is_(True))
                .order_by(TrackedUser.suspicion_score.desc())
                .limit(5)
            )
            top_targets = targets_result.scalars().all()

        report_data = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_events": total_views,
            "total_alerts": total_alerts,
            "top_suspects": {
                (t.username or str(t.telegram_id)): t.suspicion_score
                for t in top_targets
            },
            "pdf_path": pdf_path,
            "summary": f"Monitored activity for the past 24 hours. "
                       f"Detected {total_views} story views and {total_alerts} alerts.",
        }

        notifier = Notifier()
        await notifier.send_daily_report(report_data)
        logger.info("Daily report generated and sent")
    except Exception as e:
        logger.error(f"Daily report task failed: {e}")


async def task_smart_bait() -> None:
    """Evaluate conditions and auto-post bait stories when appropriate.

    Runs every 30 minutes. If any tracked user has a predicted stalker
    probability greater than 70%, schedules a bait story at the predicted
    optimal viewing time.
    """
    try:
        from sqlalchemy import select
        from core.database import get_session
        from core.models import TrackedUser
        from intelligence.predictor import Predictor
        from trapnet.honeypot import HoneypotManager

        predictor = Predictor()
        honeypot = HoneypotManager()

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(
                    TrackedUser.is_active.is_(True),
                    TrackedUser.suspicion_score >= 70.0,
                )
            )
            high_risk_users = result.scalars().all()

        for user in high_risk_users:
            try:
                prediction = await predictor.predict_next_visit(user.telegram_id)
                predicted_time = prediction.get("predicted_time")
                confidence = prediction.get("confidence_percent", 0)

                if predicted_time and confidence >= 40:
                    from datetime import datetime as dt
                    target_time = dt.fromisoformat(predicted_time)
                    bait_result = await honeypot.schedule_bait_story(target_time)
                    logger.info(
                        f"Smart bait scheduled for user {user.telegram_id}: "
                        f"{bait_result['tracking_code']}"
                    )
            except Exception as e:
                logger.debug(
                    f"Smart bait evaluation failed for {user.telegram_id}: {e}"
                )
    except Exception as e:
        logger.error(f"Smart bait task failed: {e}")


def _cleanup_old_backups(backup_dir, keep_days: int = 30) -> None:
    """Remove backup files older than the specified number of days.

    Args:
        backup_dir: Path to the backup directory.
        keep_days: Number of days to keep backups.
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=keep_days)

    for backup_file in backup_dir.glob("backup_*.db"):
        try:
            date_str = backup_file.stem.replace("backup_", "")
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff:
                backup_file.unlink()
                logger.debug(f"Removed old backup: {backup_file.name}")
        except (ValueError, OSError) as e:
            logger.debug(f"Skipping backup file {backup_file}: {e}")
