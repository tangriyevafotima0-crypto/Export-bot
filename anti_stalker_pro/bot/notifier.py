"""Notification system for sending alerts and reports via Telegram bot.

Handles formatted alert delivery, daily report summaries, and real-time
story view notifications. Respects quiet hours and duplicate suppression.
"""

from datetime import datetime, timedelta
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from core.config import get_settings
from core.logger import get_logger
from core.models import Alert

logger = get_logger(__name__)


class Notifier:
    """Sends notifications via Telegram bot with rate limiting and quiet hours.

    Manages notification delivery while respecting quiet hours (00:00-08:00),
    duplicate suppression (30-minute window), and severity-based formatting.
    """

    _instance: Optional["Notifier"] = None

    def __new__(cls, bot: Optional[Bot] = None) -> "Notifier":
        """Ensure singleton pattern for the Notifier instance.

        Returns:
            Notifier: The single Notifier instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, bot: Optional[Bot] = None) -> None:
        """Initialize the Notifier with a bot instance.

        Args:
            bot: Optional python-telegram-bot Bot instance. If None,
                creates one from settings.
        """
        if not hasattr(self, "_last_notifications"):
            self._settings = get_settings()
            self._bot = bot
            self._last_notifications: dict[str, datetime] = {}
            self._quiet_start_hour: int = 0
            self._quiet_end_hour: int = 8
        elif bot is not None:
            self._bot = bot

    @property
    def bot(self) -> Bot:
        """Get or create the Bot instance.

        Returns:
            Bot: The python-telegram-bot Bot instance.
        """
        if self._bot is None:
            self._bot = Bot(token=self._settings.bot_token)
        return self._bot

    async def send_alert(self, alert: Alert) -> bool:
        """Send a formatted alert notification via Telegram bot.

        Checks quiet hours and duplicate suppression before sending.
        CRITICAL alerts bypass quiet hours.

        Args:
            alert: The Alert model instance to send.

        Returns:
            bool: True if the notification was sent successfully.
        """
        if not self._should_send(alert):
            logger.debug(f"Alert suppressed: type={alert.alert_type}, severity={alert.severity}")
            return False

        severity_emoji = self._severity_emoji(alert.severity)
        text = (
            f"{severity_emoji} <b>ALERT: {alert.alert_type.upper()}</b>\n\n"
            f"<b>Severity:</b> {alert.severity.upper()}\n"
            f"<b>Message:</b> {alert.message}\n"
            f"<b>Time:</b> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        if alert.details:
            details_text = "\n".join(
                f"  {k}: {v}" for k, v in alert.details.items()
            )
            text += f"\n<b>Details:</b>\n<code>{details_text}</code>"

        try:
            await self.bot.send_message(
                chat_id=self._settings.my_telegram_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            self._record_notification(f"{alert.alert_type}_{alert.tracked_user_id}", alert.tracked_user_id)
            logger.info(f"Alert sent: {alert.alert_type} ({alert.severity})")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    async def send_daily_report(self, report: dict) -> bool:
        """Send the daily summary report via Telegram bot.

        Formats and sends a comprehensive daily monitoring summary.

        Args:
            report: Dictionary with report data including total_events,
                total_alerts, top_suspects, and summary fields.

        Returns:
            bool: True if the report was sent successfully.
        """
        text = (
            "📊 <b>Daily Monitoring Report</b>\n"
            f"📅 {report.get('date', datetime.utcnow().strftime('%Y-%m-%d'))}\n\n"
            f"📈 <b>Total Events:</b> {report.get('total_events', 0)}\n"
            f"🚨 <b>Total Alerts:</b> {report.get('total_alerts', 0)}\n"
        )

        top_suspects = report.get("top_suspects", {})
        if top_suspects:
            text += "\n🏆 <b>Top Suspects:</b>\n"
            for user_info, score in list(top_suspects.items())[:5]:
                text += f"  - {user_info}: {score:.1f}/100\n"

        summary = report.get("summary", "")
        if summary:
            text += f"\n📝 <b>Summary:</b>\n{summary}"

        pdf_path = report.get("pdf_path")
        try:
            await self.bot.send_message(
                chat_id=self._settings.my_telegram_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )

            if pdf_path:
                with open(pdf_path, "rb") as pdf_file:
                    await self.bot.send_document(
                        chat_id=self._settings.my_telegram_id,
                        document=pdf_file,
                        caption="Daily PDF Report",
                    )

            logger.info("Daily report sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")
            return False

    async def send_story_notification(self, viewer: dict) -> bool:
        """Send an instant notification when a tracked user views a story.

        Args:
            viewer: Dictionary with viewer information including
                user_id, username, view_order, story_id, and score.

        Returns:
            bool: True if the notification was sent successfully.
        """
        dedup_key = f"story_{viewer.get('user_id')}_{viewer.get('story_id')}"
        if self._is_duplicate(dedup_key):
            return False

        if self._is_quiet_hours() and viewer.get("score", 0) < 75:
            return False

        username = viewer.get("username", "Unknown")
        user_id = viewer.get("user_id", 0)
        view_order = viewer.get("view_order", "?")
        score = viewer.get("score", 0)

        score_bar = self._score_bar(score)

        text = (
            f"👁 <b>Story View Detected!</b>\n\n"
            f"<b>User:</b> {username} (ID: {user_id})\n"
            f"<b>View Position:</b> #{view_order}\n"
            f"<b>Suspicion Score:</b> {score:.1f}/100 {score_bar}\n"
            f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S')}"
        )

        try:
            await self.bot.send_message(
                chat_id=self._settings.my_telegram_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            self._record_notification(dedup_key, user_id)
            return True
        except Exception as e:
            logger.error(f"Failed to send story notification: {e}")
            return False

    def _should_send(self, alert: Alert) -> bool:
        """Check if an alert should be sent based on rules.

        CRITICAL alerts always send. Others respect quiet hours
        and duplicate suppression.

        Args:
            alert: The alert to evaluate.

        Returns:
            bool: True if the alert should be sent.
        """
        if alert.severity.upper() == "CRITICAL":
            return True

        if self._is_quiet_hours():
            return False

        dedup_key = f"{alert.alert_type}_{alert.tracked_user_id}"
        return not self._is_duplicate(dedup_key)

    def _is_quiet_hours(self) -> bool:
        """Check if the current time is within quiet hours (00:00-08:00).

        Returns:
            bool: True if currently in quiet hours.
        """
        current_hour = datetime.utcnow().hour
        return self._quiet_start_hour <= current_hour < self._quiet_end_hour

    def _is_duplicate(self, key: str) -> bool:
        """Check if a notification with this key was sent in the last 30 minutes.

        Args:
            key: Unique notification deduplication key.

        Returns:
            bool: True if a duplicate was sent recently.
        """
        last_sent = self._last_notifications.get(key)
        if last_sent is None:
            return False
        return (datetime.utcnow() - last_sent) < timedelta(minutes=30)

    def _record_notification(self, key: str, user_id: int) -> None:
        """Record that a notification was sent for deduplication tracking.

        Args:
            key: Notification deduplication key.
            user_id: Associated user ID.
        """
        self._last_notifications[key] = datetime.utcnow()

    def _severity_emoji(self, severity: str) -> str:
        """Get the emoji for an alert severity level.

        Args:
            severity: Severity string (info, warning, high, critical).

        Returns:
            str: Corresponding emoji character.
        """
        mapping = {
            "info": "🔵",
            "warning": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }
        return mapping.get(severity.lower(), "⚪")

    def _score_bar(self, score: float) -> str:
        """Generate a visual score bar using block characters.

        Args:
            score: Score value from 0 to 100.

        Returns:
            str: Visual bar representation.
        """
        filled = int(score / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty
