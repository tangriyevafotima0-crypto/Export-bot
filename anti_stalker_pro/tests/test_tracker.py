"""Tests for StoryTracker and OnlineTracker event recording and alert logic.

Uses mocked Telethon client responses and database sessions.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class FakeTrackedUser:
    """Mock TrackedUser for testing."""

    def __init__(self, telegram_id=123456, user_id=1, score=0.0):
        self.id = user_id
        self.telegram_id = telegram_id
        self.username = "test_user"
        self.first_name = "Test"
        self.is_active = True
        self.suspicion_score = score


class FakeScalarResult:
    """Mock scalar result from SQLAlchemy."""

    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class TestStoryTrackerAlerts:
    """Tests for StoryTracker alert triggering conditions."""

    @pytest.mark.asyncio
    async def test_alert_triggered_when_score_exceeds_threshold(self):
        """Should create an Alert when tracked user score >= alert_threshold."""
        with patch("userbot.story_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.client.TelethonClient", create=True) as mock_cls:
                mock_cls.return_value = MagicMock()
                with patch("userbot.story_tracker.StoryTracker.__init__", return_value=None):
                    from userbot.story_tracker import StoryTracker
                    tracker = StoryTracker.__new__(StoryTracker)
                    tracker._telethon = MagicMock()
                    tracker._settings = mock_settings.return_value

                    high_score_user = FakeTrackedUser(score=85.0)
                    mock_session = AsyncMock()
                    added_items = []
                    mock_session.add = lambda item: added_items.append(item)

                    await tracker._check_alert_threshold(mock_session, high_score_user)

                    assert len(added_items) == 1
                    alert = added_items[0]
                    assert alert.alert_type == "story_view"
                    assert alert.severity == "high"
                    assert "85.0" in alert.message

    @pytest.mark.asyncio
    async def test_no_alert_when_score_below_threshold(self):
        """Should NOT create an Alert when score is below threshold."""
        with patch("userbot.story_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.story_tracker.StoryTracker.__init__", return_value=None):
                from userbot.story_tracker import StoryTracker
                tracker = StoryTracker.__new__(StoryTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value

                low_score_user = FakeTrackedUser(score=30.0)
                mock_session = AsyncMock()
                added_items = []
                mock_session.add = lambda item: added_items.append(item)

                await tracker._check_alert_threshold(mock_session, low_score_user)

                assert len(added_items) == 0


class TestOnlineTrackerStatus:
    """Tests for OnlineTracker status change handling."""

    @pytest.mark.asyncio
    async def test_handle_online_records_event(self):
        """Should record an online event when user comes online."""
        with patch("userbot.online_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.online_tracker.OnlineTracker.__init__", return_value=None):
                from userbot.online_tracker import OnlineTracker
                tracker = OnlineTracker.__new__(OnlineTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value
                tracker._online_cache = {}

                tracked_user = FakeTrackedUser(telegram_id=111)
                now = datetime.utcnow()

                added_items = []
                mock_session = AsyncMock()
                mock_session.add = lambda item: added_items.append(item)
                mock_session.commit = AsyncMock()

                async def mock_get_session():
                    yield mock_session

                with patch("userbot.online_tracker.get_session", mock_get_session):
                    with patch.object(tracker, "_check_owner_online", return_value=True):
                        result = await tracker._handle_online(tracked_user, now)

                assert result is True
                assert tracked_user.telegram_id in tracker._online_cache
                assert len(added_items) == 1
                event = added_items[0]
                assert event.went_online == now
                assert event.overlaps_with_me is True

    @pytest.mark.asyncio
    async def test_handle_online_ignores_already_online(self):
        """Should not create duplicate event if user is already marked online."""
        with patch("userbot.online_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.online_tracker.OnlineTracker.__init__", return_value=None):
                from userbot.online_tracker import OnlineTracker
                tracker = OnlineTracker.__new__(OnlineTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value
                tracker._online_cache = {222: datetime.utcnow()}

                tracked_user = FakeTrackedUser(telegram_id=222)
                now = datetime.utcnow()

                result = await tracker._handle_online(tracked_user, now)
                assert result is False

    @pytest.mark.asyncio
    async def test_handle_offline_calculates_duration(self):
        """Should calculate duration when user goes offline."""
        with patch("userbot.online_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.online_tracker.OnlineTracker.__init__", return_value=None):
                from userbot.online_tracker import OnlineTracker
                tracker = OnlineTracker.__new__(OnlineTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value

                online_time = datetime(2024, 1, 1, 12, 0, 0)
                tracker._online_cache = {333: online_time}

                tracked_user = FakeTrackedUser(telegram_id=333)
                offline_time = datetime(2024, 1, 1, 12, 5, 0)

                mock_event = MagicMock()
                mock_event.went_offline = None

                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=FakeScalarResult([mock_event]))
                mock_session.commit = AsyncMock()

                async def mock_get_session():
                    yield mock_session

                mock_status = MagicMock()
                mock_status.was_online = offline_time

                with patch("userbot.online_tracker.get_session", mock_get_session):
                    result = await tracker._handle_offline(tracked_user, datetime.utcnow(), mock_status)

                assert result is True
                assert 333 not in tracker._online_cache
                assert mock_event.went_offline == offline_time
                assert mock_event.duration_seconds == 300

    @pytest.mark.asyncio
    async def test_handle_offline_ignores_not_cached(self):
        """Should return False if user was not in online cache."""
        with patch("userbot.online_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.online_tracker.OnlineTracker.__init__", return_value=None):
                from userbot.online_tracker import OnlineTracker
                tracker = OnlineTracker.__new__(OnlineTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value
                tracker._online_cache = {}

                tracked_user = FakeTrackedUser(telegram_id=444)
                mock_status = MagicMock()

                result = await tracker._handle_offline(tracked_user, datetime.utcnow(), mock_status)
                assert result is False


class TestOnlineTrackerHistory:
    """Tests for OnlineTracker get_online_history method."""

    @pytest.mark.asyncio
    async def test_get_online_history_returns_formatted_data(self):
        """Should return formatted history list from database."""
        with patch("userbot.online_tracker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(alert_threshold=70)

            with patch("userbot.online_tracker.OnlineTracker.__init__", return_value=None):
                from userbot.online_tracker import OnlineTracker
                tracker = OnlineTracker.__new__(OnlineTracker)
                tracker._telethon = MagicMock()
                tracker._settings = mock_settings.return_value
                tracker._online_cache = {}

                now = datetime.utcnow()
                fake_user = FakeTrackedUser(telegram_id=555)
                fake_event = MagicMock()
                fake_event.went_online = now
                fake_event.went_offline = now
                fake_event.duration_seconds = 120
                fake_event.overlaps_with_me = True

                mock_session = AsyncMock()

                call_count = [0]

                async def mock_execute(query):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return FakeScalarResult([fake_user])
                    return FakeScalarResult([fake_event])

                mock_session.execute = mock_execute

                async def mock_get_session():
                    yield mock_session

                with patch("userbot.online_tracker.get_session", mock_get_session):
                    history = await tracker.get_online_history(555, days=7)

                assert len(history) == 1
                assert history[0]["duration_seconds"] == 120
                assert history[0]["overlaps_with_me"] is True
