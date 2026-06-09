"""Tests for the VersionChannel class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.version_channel import VersionChannel


@pytest.fixture
def mock_bot():
    """Create a mock Bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def version_channel(mock_bot):
    """Create a VersionChannel instance with a mock bot."""
    return VersionChannel(bot=mock_bot)


class TestPostVersionUpdate:
    """Tests for post_version_update method."""

    async def test_posts_formatted_message_with_version(
        self, version_channel, mock_bot
    ):
        """Test that version update posts a formatted message containing the version."""
        version_channel._settings = MagicMock()
        version_channel._settings.version_channel_id = -1001234567890
        version_channel._settings.bot_token = "fake-token"

        result = await version_channel.post_version_update(
            version="2.0.0",
            changelog=["Added version channel", "Fixed bugs"],
        )

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "2.0.0" in call_kwargs["text"]
        assert "Added version channel" in call_kwargs["text"]
        assert "Fixed bugs" in call_kwargs["text"]
        assert call_kwargs["chat_id"] == -1001234567890

    async def test_returns_false_when_channel_not_configured(self, mock_bot):
        """Test graceful handling when version_channel_id is None."""
        vc = VersionChannel(bot=mock_bot)
        vc._settings = MagicMock()
        vc._settings.version_channel_id = None

        result = await vc.post_version_update(
            version="2.0.0", changelog=["Test entry"]
        )

        assert result is False
        mock_bot.send_message.assert_not_called()

    async def test_returns_false_on_send_error(self, version_channel, mock_bot):
        """Test graceful handling when send_message raises an exception."""
        version_channel._settings = MagicMock()
        version_channel._settings.version_channel_id = -1001234567890
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await version_channel.post_version_update(
            version="2.0.0", changelog=["Entry"]
        )

        assert result is False


class TestPostSystemStatus:
    """Tests for post_system_status method."""

    async def test_posts_system_status(self, version_channel, mock_bot):
        """Test that system status is posted correctly."""
        version_channel._settings = MagicMock()
        version_channel._settings.version_channel_id = -1001234567890
        version_channel._settings.app_version = "2.0.0"

        status_data = {
            "status": "running",
            "version": "2.0.0",
            "uptime": "2h 30m",
            "active_targets": 5,
        }

        result = await version_channel.post_system_status(status_data)

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "running" in call_kwargs["text"]
        assert "2.0.0" in call_kwargs["text"]
        assert "2h 30m" in call_kwargs["text"]

    async def test_returns_false_when_channel_not_configured(self, mock_bot):
        """Test graceful handling when version_channel_id is None."""
        vc = VersionChannel(bot=mock_bot)
        vc._settings = MagicMock()
        vc._settings.version_channel_id = None

        result = await vc.post_system_status({"status": "running"})

        assert result is False
        mock_bot.send_message.assert_not_called()


class TestPostChangelogEntry:
    """Tests for post_changelog_entry method."""

    async def test_posts_changelog_entry(self, version_channel, mock_bot):
        """Test that a changelog entry is posted correctly."""
        version_channel._settings = MagicMock()
        version_channel._settings.version_channel_id = -1001234567890

        result = await version_channel.post_changelog_entry(
            "Added new monitoring feature"
        )

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "Added new monitoring feature" in call_kwargs["text"]
        assert "Changelog Update" in call_kwargs["text"]

    async def test_returns_false_when_channel_not_configured(self, mock_bot):
        """Test graceful handling when version_channel_id is None."""
        vc = VersionChannel(bot=mock_bot)
        vc._settings = MagicMock()
        vc._settings.version_channel_id = None

        result = await vc.post_changelog_entry("Some entry")

        assert result is False
        mock_bot.send_message.assert_not_called()

    async def test_returns_false_on_send_error(self, version_channel, mock_bot):
        """Test graceful handling when send_message raises an exception."""
        version_channel._settings = MagicMock()
        version_channel._settings.version_channel_id = -1001234567890
        mock_bot.send_message.side_effect = Exception("Timeout")

        result = await version_channel.post_changelog_entry("Entry")

        assert result is False


class TestVersionChannelInit:
    """Tests for VersionChannel initialization."""

    async def test_creates_bot_from_settings_when_none(self):
        """Test that bot is created from settings when not provided."""
        vc = VersionChannel(bot=None)
        assert vc._bot is None

    async def test_uses_provided_bot(self, mock_bot):
        """Test that provided bot instance is used directly."""
        vc = VersionChannel(bot=mock_bot)
        assert vc._bot is mock_bot
