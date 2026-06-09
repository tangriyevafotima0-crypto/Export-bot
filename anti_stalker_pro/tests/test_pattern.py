"""Tests for the PatternEngine pattern detection logic.

Tests each pattern type (NIGHT_STALKER, IMMEDIATE_RESPONDER,
DAILY_CHECKER, SILENT_OBSERVER) with mock database data.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class FakeStoryView:
    """Mock StoryView record for testing."""

    def __init__(self, viewed_at, view_order=None, reaction=None):
        self.viewed_at = viewed_at
        self.view_order = view_order
        self.reaction = reaction
        self.story_id = 1
        self.id = 1
        self.tracked_user_id = 1


class FakeOnlineEvent:
    """Mock OnlineEvent record for testing."""

    def __init__(self, went_online, overlaps_with_me=False):
        self.went_online = went_online
        self.overlaps_with_me = overlaps_with_me
        self.went_offline = None
        self.duration_seconds = None


class FakeTrackedUser:
    """Mock TrackedUser for testing."""

    def __init__(self, telegram_id=123456, user_id=1):
        self.id = user_id
        self.telegram_id = telegram_id
        self.is_active = True
        self.suspicion_score = 0.0


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

    def scalar(self):
        return self._items[0] if self._items else None


@pytest.fixture
def pattern_engine():
    """Create a PatternEngine instance with mocked settings."""
    with patch("intelligence.pattern_engine.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(alert_threshold=70)
        from intelligence.pattern_engine import PatternEngine
        engine = PatternEngine()
        return engine


class TestNightStalker:
    """Tests for NIGHT_STALKER pattern detection."""

    @pytest.mark.asyncio
    async def test_detects_night_stalker_when_mostly_night_activity(self, pattern_engine):
        """Should detect NIGHT_STALKER when >30% of activity is between 00:00-05:00."""
        now = datetime.utcnow()
        night_views = [
            FakeStoryView(viewed_at=now.replace(hour=2, minute=i * 10))
            for i in range(6)
        ]
        day_views = [
            FakeStoryView(viewed_at=now.replace(hour=14, minute=0))
        ]
        night_online = [
            FakeOnlineEvent(went_online=now.replace(hour=3, minute=0))
            for _ in range(4)
        ]

        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str and "viewed_at" in query_str:
                all_views = night_views + day_views
                return FakeScalarResult([v.viewed_at for v in all_views])
            elif "online_events" in query_str:
                return FakeScalarResult([e.went_online for e in night_online])
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_night_stalker(123456)

        assert result is not None
        assert result["pattern_type"] == "NIGHT_STALKER"
        assert result["confidence"] > 0.3
        assert result["details"]["night_activity_ratio"] > 0.3

    @pytest.mark.asyncio
    async def test_no_night_stalker_when_daytime_activity(self, pattern_engine):
        """Should NOT detect NIGHT_STALKER when activity is during day."""
        now = datetime.utcnow()
        day_views = [
            FakeStoryView(viewed_at=now.replace(hour=h, minute=0))
            for h in range(10, 20)
        ]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult([v.viewed_at for v in day_views])
            elif "online_events" in query_str:
                return FakeScalarResult([])
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_night_stalker(123456)

        assert result is None


class TestImmediateResponder:
    """Tests for IMMEDIATE_RESPONDER pattern detection."""

    @pytest.mark.asyncio
    async def test_detects_immediate_responder(self, pattern_engine):
        """Should detect IMMEDIATE_RESPONDER when avg position <= 10 and early ratio >= 0.5."""
        now = datetime.utcnow()
        views = [
            FakeStoryView(viewed_at=now, view_order=2),
            FakeStoryView(viewed_at=now, view_order=3),
            FakeStoryView(viewed_at=now, view_order=1),
            FakeStoryView(viewed_at=now, view_order=4),
            FakeStoryView(viewed_at=now, view_order=5),
        ]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult(views)
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_immediate_responder(123456)

        assert result is not None
        assert result["pattern_type"] == "IMMEDIATE_RESPONDER"
        assert result["details"]["average_view_position"] <= 10
        assert result["details"]["early_view_ratio"] >= 0.5

    @pytest.mark.asyncio
    async def test_no_immediate_responder_when_late_viewer(self, pattern_engine):
        """Should NOT detect IMMEDIATE_RESPONDER when view positions are high."""
        now = datetime.utcnow()
        views = [
            FakeStoryView(viewed_at=now, view_order=50),
            FakeStoryView(viewed_at=now, view_order=60),
            FakeStoryView(viewed_at=now, view_order=45),
            FakeStoryView(viewed_at=now, view_order=70),
        ]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult(views)
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_immediate_responder(123456)

        assert result is None


class TestDailyChecker:
    """Tests for DAILY_CHECKER pattern detection."""

    @pytest.mark.asyncio
    async def test_detects_daily_checker(self, pattern_engine):
        """Should detect DAILY_CHECKER when day coverage >= 60%."""
        now = datetime.utcnow()
        view_times = [
            now - timedelta(days=i, hours=2)
            for i in range(10)
        ]
        views = [FakeStoryView(viewed_at=t) for t in view_times]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult([v.viewed_at for v in views])
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_daily_checker(123456)

        assert result is not None
        assert result["pattern_type"] == "DAILY_CHECKER"
        assert result["details"]["day_coverage"] >= 0.6
        assert result["details"]["longest_streak"] >= 1

    @pytest.mark.asyncio
    async def test_no_daily_checker_with_sparse_views(self, pattern_engine):
        """Should NOT detect DAILY_CHECKER when activity spans few days."""
        now = datetime.utcnow()
        view_times = [now, now - timedelta(hours=1)]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult(view_times)
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_daily_checker(123456)

        assert result is None


class TestSilentObserver:
    """Tests for SILENT_OBSERVER pattern detection."""

    @pytest.mark.asyncio
    async def test_detects_silent_observer(self, pattern_engine):
        """Should detect SILENT_OBSERVER when high views but no reactions."""
        now = datetime.utcnow()
        views = [
            FakeStoryView(viewed_at=now - timedelta(hours=i), reaction=None)
            for i in range(10)
        ]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult(views)
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_silent_observer(123456)

        assert result is not None
        assert result["pattern_type"] == "SILENT_OBSERVER"
        assert result["details"]["reaction_ratio"] == 0.0
        assert result["details"]["total_views"] == 10

    @pytest.mark.asyncio
    async def test_no_silent_observer_when_reacting(self, pattern_engine):
        """Should NOT detect SILENT_OBSERVER when user reacts frequently."""
        now = datetime.utcnow()
        views = [
            FakeStoryView(viewed_at=now - timedelta(hours=i), reaction="thumbs_up")
            for i in range(10)
        ]
        fake_user = FakeTrackedUser()

        async def mock_session_execute(query):
            query_str = str(query)
            if "tracked_users" in query_str:
                return FakeScalarResult([fake_user])
            elif "story_views" in query_str:
                return FakeScalarResult(views)
            return FakeScalarResult([])

        mock_session = AsyncMock()
        mock_session.execute = mock_session_execute

        async def mock_get_session():
            yield mock_session

        with patch("intelligence.pattern_engine.get_session", mock_get_session):
            result = await pattern_engine._detect_silent_observer(123456)

        assert result is None


class TestLongestConsecutiveDays:
    """Tests for the _longest_consecutive_days helper method."""

    def test_consecutive_streak(self, pattern_engine):
        """Should correctly calculate longest consecutive day streak."""
        from datetime import date

        dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5)]
        result = pattern_engine._longest_consecutive_days(dates)
        assert result == 3

    def test_empty_list(self, pattern_engine):
        """Should return 0 for empty list."""
        result = pattern_engine._longest_consecutive_days([])
        assert result == 0

    def test_single_day(self, pattern_engine):
        """Should return 1 for single day."""
        from datetime import date

        result = pattern_engine._longest_consecutive_days([date(2024, 1, 1)])
        assert result == 1

    def test_no_consecutive(self, pattern_engine):
        """Should return 1 when no days are consecutive."""
        from datetime import date

        dates = [date(2024, 1, 1), date(2024, 1, 5), date(2024, 1, 10)]
        result = pattern_engine._longest_consecutive_days(dates)
        assert result == 1
