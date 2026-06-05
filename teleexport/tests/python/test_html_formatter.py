"""Tests for the HTML formatter."""
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from python.formatters.html_formatter import HTMLFormatter


@pytest.fixture
def formatter(tmp_export_dir):
    """Create an HTMLFormatter with the tmp directory."""
    return HTMLFormatter(output_dir=tmp_export_dir)


@pytest.fixture
def sample_messages(mock_message_factory):
    """Create a set of sample messages for testing."""
    return [
        mock_message_factory(
            msg_id=1,
            text="Good morning!",
            date=datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc),
            sender_id=100,
            sender_name="Alice",
        ),
        mock_message_factory(
            msg_id=2,
            text="Hello Alice!",
            date=datetime(2024, 1, 15, 8, 5, 0, tzinfo=timezone.utc),
            sender_id=200,
            sender_name="Bob",
        ),
        mock_message_factory(
            msg_id=3,
            text="Next day message",
            date=datetime(2024, 1, 16, 10, 0, 0, tzinfo=timezone.utc),
            sender_id=100,
            sender_name="Alice",
        ),
    ]


class TestGroupByDate:
    """Tests for _group_by_date method."""

    def test_groups_messages_by_date(self, formatter, sample_messages):
        """Test that messages are grouped by their date."""
        groups = formatter._group_by_date(sample_messages)
        assert "2024-01-15" in groups
        assert "2024-01-16" in groups
        assert len(groups["2024-01-15"]) == 2
        assert len(groups["2024-01-16"]) == 1

    def test_empty_messages(self, formatter):
        """Test grouping with no messages."""
        groups = formatter._group_by_date([])
        assert groups == {}

    def test_single_date_group(self, formatter, mock_message_factory):
        """Test all messages on same date go in one group."""
        msgs = [
            mock_message_factory(msg_id=i, date=datetime(2024, 3, 1, i, 0, 0, tzinfo=timezone.utc))
            for i in range(1, 6)
        ]
        groups = formatter._group_by_date(msgs)
        assert len(groups) == 1
        assert "2024-03-01" in groups
        assert len(groups["2024-03-01"]) == 5

    def test_messages_sorted_within_group(self, formatter, mock_message_factory):
        """Test messages are sorted by date within each group."""
        msgs = [
            mock_message_factory(msg_id=3, date=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)),
            mock_message_factory(msg_id=1, date=datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)),
            mock_message_factory(msg_id=2, date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
        ]
        groups = formatter._group_by_date(msgs)
        times = [m.date.hour for m in groups["2024-01-01"]]
        assert times == [8, 12, 15]


class TestCollectParticipants:
    """Tests for _collect_participants method."""

    def test_extracts_unique_senders(self, formatter, sample_messages):
        """Test that unique participants are collected."""
        participants = formatter._collect_participants(sample_messages)
        assert 100 in participants
        assert 200 in participants
        assert len(participants) == 2

    def test_participant_info(self, formatter, sample_messages):
        """Test participant info contains id and name."""
        participants = formatter._collect_participants(sample_messages)
        assert participants[100]["id"] == 100
        assert participants[100]["name"] == "Alice"
        assert participants[200]["name"] == "Bob"

    def test_empty_messages(self, formatter):
        """Test with no messages returns empty dict."""
        participants = formatter._collect_participants([])
        assert participants == {}

    def test_duplicate_senders_not_repeated(self, formatter, mock_message_factory):
        """Test same sender appearing multiple times is only collected once."""
        msgs = [
            mock_message_factory(msg_id=i, sender_id=100, sender_name="Alice")
            for i in range(5)
        ]
        participants = formatter._collect_participants(msgs)
        assert len(participants) == 1


class TestFormat:
    """Tests for the format method producing valid HTML."""

    def test_produces_html_file(self, formatter, sample_messages, mock_entity, tmp_export_dir):
        """Test that format() produces an HTML file."""
        media_dir = tmp_export_dir / "media"
        media_dir.mkdir()

        output = formatter.format("Test Chat", mock_entity, sample_messages, media_dir)
        assert output.exists()
        assert output.suffix == ".html"

    def test_html_contains_chat_name(self, formatter, sample_messages, mock_entity, tmp_export_dir):
        """Test that generated HTML contains the chat name."""
        media_dir = tmp_export_dir / "media"
        media_dir.mkdir()

        output = formatter.format("My Chat", mock_entity, sample_messages, media_dir)
        html_content = output.read_text()
        assert "My Chat" in html_content

    def test_html_contains_message_text(self, formatter, sample_messages, mock_entity, tmp_export_dir):
        """Test that generated HTML contains message text."""
        media_dir = tmp_export_dir / "media"
        media_dir.mkdir()

        output = formatter.format("Test Chat", mock_entity, sample_messages, media_dir)
        html_content = output.read_text()
        assert "Good morning!" in html_content
        assert "Hello Alice!" in html_content
        assert "Next day message" in html_content

    def test_html_contains_date_separators(self, formatter, sample_messages, mock_entity, tmp_export_dir):
        """Test that HTML contains date separator elements."""
        media_dir = tmp_export_dir / "media"
        media_dir.mkdir()

        output = formatter.format("Test Chat", mock_entity, sample_messages, media_dir)
        html_content = output.read_text()
        assert "date-2024-01-15" in html_content
        assert "date-2024-01-16" in html_content

    def test_html_contains_sender_names(self, formatter, sample_messages, mock_entity, tmp_export_dir):
        """Test that HTML contains sender names."""
        media_dir = tmp_export_dir / "media"
        media_dir.mkdir()

        output = formatter.format("Test Chat", mock_entity, sample_messages, media_dir)
        html_content = output.read_text()
        assert "Alice" in html_content
        assert "Bob" in html_content


class TestCustomFilters:
    """Tests for custom Jinja2 filters."""

    def test_format_date(self):
        """Test _format_date produces readable date string."""
        dt = datetime(2024, 3, 15, 10, 30, 0)
        result = HTMLFormatter._format_date(dt)
        assert result == "March 15, 2024"

    def test_format_time(self):
        """Test _format_time produces HH:MM format."""
        dt = datetime(2024, 3, 15, 14, 5, 0)
        result = HTMLFormatter._format_time(dt)
        assert result == "14:05"

    def test_format_date_midnight(self):
        """Test format_date at midnight."""
        dt = datetime(2024, 12, 31, 0, 0, 0)
        result = HTMLFormatter._format_date(dt)
        assert result == "December 31, 2024"

    def test_format_time_midnight(self):
        """Test format_time at midnight."""
        dt = datetime(2024, 1, 1, 0, 0, 0)
        result = HTMLFormatter._format_time(dt)
        assert result == "00:00"
