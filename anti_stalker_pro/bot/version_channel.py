"""Version channel module for posting update announcements to Telegram.

Provides the VersionChannel class that posts version updates, changelog
entries, and system status updates to a configured Telegram channel.
"""

from datetime import datetime
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)


class VersionChannel:
    """Posts version and system updates to a configured Telegram channel.

    Handles formatted message delivery for version announcements,
    changelog entries, and system status updates. Gracefully handles
    cases where no channel ID is configured.
    """

    def __init__(self, bot: Optional[Bot] = None) -> None:
        """Initialize the VersionChannel with a bot instance.

        Args:
            bot: Optional python-telegram-bot Bot instance. If None,
                creates one from settings.
        """
        self._settings = get_settings()
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

    @property
    def channel_id(self) -> Optional[int]:
        """Get the configured version channel ID.

        Returns:
            Optional[int]: The channel ID or None if not configured.
        """
        return self._settings.version_channel_id

    async def post_version_update(
        self, version: str, changelog: list[str]
    ) -> bool:
        """Post a formatted version update announcement to the channel.

        Args:
            version: The version string (e.g. '2.0.0').
            changelog: List of changelog entry strings.

        Returns:
            bool: True if the message was sent successfully.
        """
        if not self.channel_id:
            logger.info(
                "Version channel not configured, skipping version update post"
            )
            return False

        changes_text = ""
        for entry in changelog:
            changes_text += f"  - {entry}\n"

        text = (
            f"🚀 <b>Version {version} Released</b>\n\n"
            f"<b>What's New:</b>\n"
            f"{changes_text}\n"
            f"📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"Version update v{version} posted to channel")
            return True
        except Exception as e:
            logger.error(f"Failed to post version update: {e}")
            return False

    async def post_system_status(self, status_data: dict) -> bool:
        """Post a system status update to the channel.

        Args:
            status_data: Dictionary with status information. Expected keys:
                - status (str): Current system status (e.g. 'running').
                - version (str): Current version.
                - uptime (str): Uptime duration string.
                - active_targets (int): Number of active tracked targets.

        Returns:
            bool: True if the message was sent successfully.
        """
        if not self.channel_id:
            logger.info(
                "Version channel not configured, skipping system status post"
            )
            return False

        status = status_data.get("status", "unknown")
        version = status_data.get("version", self._settings.app_version)
        uptime = status_data.get("uptime", "N/A")
        active_targets = status_data.get("active_targets", 0)

        status_emoji = "🟢" if status == "running" else "🔴"

        text = (
            f"{status_emoji} <b>System Status Update</b>\n\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Version:</b> {version}\n"
            f"<b>Uptime:</b> {uptime}\n"
            f"<b>Active Targets:</b> {active_targets}\n"
            f"📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            logger.info("System status posted to channel")
            return True
        except Exception as e:
            logger.error(f"Failed to post system status: {e}")
            return False

    async def post_changelog_entry(self, entry: str) -> bool:
        """Post a single changelog entry to the channel.

        Args:
            entry: The changelog entry text.

        Returns:
            bool: True if the message was sent successfully.
        """
        if not self.channel_id:
            logger.info(
                "Version channel not configured, skipping changelog entry post"
            )
            return False

        text = (
            f"📝 <b>Changelog Update</b>\n\n"
            f"{entry}\n\n"
            f"📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            logger.info("Changelog entry posted to channel")
            return True
        except Exception as e:
            logger.error(f"Failed to post changelog entry: {e}")
            return False
