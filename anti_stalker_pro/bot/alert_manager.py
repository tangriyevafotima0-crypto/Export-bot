"""Alert management system with rate limiting and delivery rules.

Creates, stores, and delivers alerts while enforcing rate limits
(max 2 per hour per user), quiet hours (00:00-08:00 for non-CRITICAL),
and 30-minute duplicate suppression windows.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, desc

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import Alert, TrackedUser

logger = get_logger(__name__)


class AlertManager:
    """Manages alert creation, storage, and delivery with rate limiting.

    Enforces the following rules:
    - Maximum 2 alerts per hour per tracked user
    - Quiet hours (00:00-08:00 UTC) for non-CRITICAL alerts
    - 30-minute duplicate suppression window for same type/user combos
    """

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"

    def __init__(self) -> None:
        """Initialize the AlertManager with settings."""
        self._settings = get_settings()

    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        user_id: int,
        message: str,
        details: Optional[dict] = None,
    ) -> Optional[Alert]:
        """Create a new alert record in the database.

        Validates the severity level and stores the alert regardless
        of delivery rules (delivery is handled by process_pending).

        Args:
            alert_type: Type identifier (e.g., "story_view", "score_spike").
            severity: One of: info, warning, high, critical.
            user_id: Telegram user ID of the tracked user.
            message: Human-readable alert message.
            details: Optional dictionary with additional alert context.

        Returns:
            Optional[Alert]: The created Alert object, or None if the
                tracked user was not found.
        """
        severity = severity.lower()
        if severity not in (
            self.SEVERITY_INFO,
            self.SEVERITY_WARNING,
            self.SEVERITY_HIGH,
            self.SEVERITY_CRITICAL,
        ):
            severity = self.SEVERITY_INFO

        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                logger.warning(f"Cannot create alert: user {user_id} not tracked")
                return None

            alert = Alert(
                tracked_user_id=tracked.id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                details=details or {},
                is_acknowledged=False,
                created_at=datetime.utcnow(),
            )
            session.add(alert)
            await session.commit()
            await session.refresh(alert)

        logger.info(
            f"Alert created: type={alert_type}, severity={severity}, "
            f"user={user_id}"
        )
        return alert

    async def process_pending(self) -> int:
        """Process and send all unacknowledged alerts respecting delivery rules.

        Sends alerts that pass the following checks:
        - Not already acknowledged
        - Not in quiet hours (unless CRITICAL)
        - Not exceeding rate limit (2/hour per user)
        - Not a duplicate (same type/user within 30 minutes)

        Returns:
            int: Number of alerts successfully delivered.
        """
        from bot.notifier import Notifier

        notifier = Notifier()
        sent_count = 0

        async for session in get_session():
            result = await session.execute(
                select(Alert)
                .where(Alert.is_acknowledged.is_(False))
                .order_by(Alert.created_at.asc())
            )
            pending_alerts = result.scalars().all()

        for alert in pending_alerts:
            if not self._can_deliver(alert, pending_alerts):
                continue

            success = await notifier.send_alert(alert)
            if success:
                async for session in get_session():
                    result = await session.execute(
                        select(Alert).where(Alert.id == alert.id)
                    )
                    db_alert = result.scalar_one_or_none()
                    if db_alert:
                        db_alert.is_acknowledged = True
                        await session.commit()
                sent_count += 1

        if sent_count > 0:
            logger.info(f"Processed {sent_count} pending alerts")
        return sent_count

    async def get_recent_alerts(
        self, limit: int = 20, severity: Optional[str] = None
    ) -> list[Alert]:
        """Get recent alerts, optionally filtered by severity.

        Args:
            limit: Maximum number of alerts to return.
            severity: Optional severity filter.

        Returns:
            list[Alert]: List of recent Alert objects.
        """
        async for session in get_session():
            query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
            if severity:
                query = query.where(Alert.severity == severity.lower())
            result = await session.execute(query)
            return result.scalars().all()

    async def get_alerts_for_user(self, user_id: int) -> list[Alert]:
        """Get all alerts for a specific tracked user.

        Args:
            user_id: Telegram user ID to get alerts for.

        Returns:
            list[Alert]: List of alerts for the user.
        """
        async for session in get_session():
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.telegram_id == user_id)
            )
            tracked = result.scalar_one_or_none()
            if not tracked:
                return []

            alerts_result = await session.execute(
                select(Alert)
                .where(Alert.tracked_user_id == tracked.id)
                .order_by(desc(Alert.created_at))
            )
            return alerts_result.scalars().all()

    async def acknowledge_alert(self, alert_id: int) -> bool:
        """Mark an alert as acknowledged.

        Args:
            alert_id: The alert ID to acknowledge.

        Returns:
            bool: True if the alert was found and acknowledged.
        """
        async for session in get_session():
            result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()
            if alert:
                alert.is_acknowledged = True
                await session.commit()
                return True
        return False

    async def get_unacknowledged_count(self) -> int:
        """Get the count of unacknowledged alerts.

        Returns:
            int: Number of pending alerts.
        """
        async for session in get_session():
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    Alert.is_acknowledged.is_(False)
                )
            )
            return result.scalar() or 0

    def _can_deliver(self, alert: Alert, all_pending: list[Alert]) -> bool:
        """Check if an alert can be delivered based on all rules.

        Args:
            alert: The alert to evaluate for delivery.
            all_pending: All pending alerts for context.

        Returns:
            bool: True if the alert passes all delivery rules.
        """
        if alert.severity.upper() == "CRITICAL":
            return True

        if self._is_quiet_hours():
            return False

        if self._exceeds_rate_limit(alert, all_pending):
            return False

        if self._is_duplicate(alert, all_pending):
            return False

        return True

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours (00:00-08:00 UTC).

        Returns:
            bool: True if in quiet hours.
        """
        current_hour = datetime.utcnow().hour
        return 0 <= current_hour < 8

    def _exceeds_rate_limit(
        self, alert: Alert, all_pending: list[Alert]
    ) -> bool:
        """Check if sending this alert would exceed the rate limit.

        Rate limit: maximum 2 alerts per hour per tracked user.

        Args:
            alert: The alert to check.
            all_pending: All pending alerts for counting.

        Returns:
            bool: True if the rate limit would be exceeded.
        """
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_for_user = [
            a
            for a in all_pending
            if a.tracked_user_id == alert.tracked_user_id
            and a.created_at >= one_hour_ago
            and a.is_acknowledged
        ]
        return len(recent_for_user) >= 2

    def _is_duplicate(self, alert: Alert, all_pending: list[Alert]) -> bool:
        """Check if this alert is a duplicate within the suppression window.

        Duplicate defined as same alert_type and tracked_user_id within
        30 minutes.

        Args:
            alert: The alert to check.
            all_pending: All pending alerts to check against.

        Returns:
            bool: True if this is a duplicate.
        """
        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        for other in all_pending:
            if other.id == alert.id:
                continue
            if (
                other.alert_type == alert.alert_type
                and other.tracked_user_id == alert.tracked_user_id
                and other.created_at >= thirty_min_ago
                and other.is_acknowledged
            ):
                return True
        return False
