"""Tests for the export engine."""
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from python.export.engine import ExportEngine, ExportConfig
from python.formatters.html_formatter import HTMLFormatter
from python.formatters.json_formatter import JSONFormatter
from python.formatters.csv_formatter import CSVFormatter


class TestExportConfig:
    """Tests for ExportConfig dataclass."""

    def test_default_values(self, tmp_export_dir):
        """Test ExportConfig has sensible defaults."""
        config = ExportConfig(
            chat_ids=[123],
            output_dir=tmp_export_dir,
        )
        assert config.format == "html"
        assert config.date_from is None
        assert config.date_to is None
        assert "photo" in config.media_types
        assert "video" in config.media_types
        assert "document" in config.media_types
        assert config.include_replies is True
        assert config.include_forwards is True
        assert config.max_file_size_mb == 500
        assert config.batch_size == 100

    def test_custom_values(self, tmp_export_dir):
        """Test ExportConfig with custom values."""
        config = ExportConfig(
            chat_ids=[1, 2, 3],
            output_dir=tmp_export_dir,
            format="json",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 6, 30),
            media_types={"photo", "video"},
            include_replies=False,
            include_forwards=False,
            max_file_size_mb=100,
            batch_size=50,
        )
        assert config.chat_ids == [1, 2, 3]
        assert config.format == "json"
        assert config.media_types == {"photo", "video"}
        assert config.batch_size == 50

    def test_media_types_default_set(self, tmp_export_dir):
        """Test that default media_types includes all expected types."""
        config = ExportConfig(chat_ids=[1], output_dir=tmp_export_dir)
        expected = {"photo", "video", "audio", "document", "voice", "sticker", "animation", "video_note"}
        assert config.media_types == expected


class TestExportEngine:
    """Tests for ExportEngine class."""

    def _make_engine(self, tmp_export_dir, media_types=None):
        """Helper to create an ExportEngine with mock client."""
        client = MagicMock()
        config = ExportConfig(
            chat_ids=[1],
            output_dir=tmp_export_dir,
            media_types=media_types or {"photo", "video", "audio", "document"},
        )
        return ExportEngine(client, config)

    def test_cancel_sets_flag(self, tmp_export_dir):
        """Test that cancel() sets the cancelled flag."""
        engine = self._make_engine(tmp_export_dir)
        assert engine.cancelled is False
        engine.cancel()
        assert engine.cancelled is True

    def test_should_download_media_photo(self, tmp_export_dir):
        """Test _should_download_media returns True for photos when enabled."""
        engine = self._make_engine(tmp_export_dir)
        media = MagicMock(spec=[])
        media.__class__ = type("MessageMediaPhoto", (), {})

        # Patch isinstance check
        from telethon.tl.types import MessageMediaPhoto
        photo_media = MagicMock(spec=MessageMediaPhoto)
        photo_media.__class__ = MessageMediaPhoto
        assert engine._should_download_media(photo_media) is True

    def test_should_download_media_photo_disabled(self, tmp_export_dir):
        """Test _should_download_media returns False for photos when disabled."""
        engine = self._make_engine(tmp_export_dir, media_types={"video"})
        from telethon.tl.types import MessageMediaPhoto
        photo_media = MagicMock(spec=MessageMediaPhoto)
        photo_media.__class__ = MessageMediaPhoto
        assert engine._should_download_media(photo_media) is False

    def test_should_download_media_document_video(self, tmp_export_dir):
        """Test _should_download_media returns True for video documents."""
        engine = self._make_engine(tmp_export_dir)
        from telethon.tl.types import MessageMediaDocument
        doc_media = MagicMock(spec=MessageMediaDocument)
        doc_media.__class__ = MessageMediaDocument
        doc_media.document = MagicMock()
        doc_media.document.mime_type = "video/mp4"
        assert engine._should_download_media(doc_media) is True

    def test_should_download_media_returns_false_for_unknown(self, tmp_export_dir):
        """Test _should_download_media returns False for unknown media types."""
        engine = self._make_engine(tmp_export_dir)
        unknown_media = MagicMock()
        unknown_media.__class__ = type("UnknownMedia", (), {})
        assert engine._should_download_media(unknown_media) is False

    def test_get_formatter_html(self, tmp_export_dir):
        """Test _get_formatter returns HTMLFormatter for html format."""
        engine = self._make_engine(tmp_export_dir)
        engine.config.format = "html"
        formatter = engine._get_formatter(tmp_export_dir)
        assert isinstance(formatter, HTMLFormatter)

    def test_get_formatter_json(self, tmp_export_dir):
        """Test _get_formatter returns JSONFormatter for json format."""
        engine = self._make_engine(tmp_export_dir)
        engine.config.format = "json"
        formatter = engine._get_formatter(tmp_export_dir)
        assert isinstance(formatter, JSONFormatter)

    def test_get_formatter_csv(self, tmp_export_dir):
        """Test _get_formatter returns CSVFormatter for csv format."""
        engine = self._make_engine(tmp_export_dir)
        engine.config.format = "csv"
        formatter = engine._get_formatter(tmp_export_dir)
        assert isinstance(formatter, CSVFormatter)

    def test_get_formatter_unknown_defaults_to_html(self, tmp_export_dir):
        """Test _get_formatter defaults to HTMLFormatter for unknown format."""
        engine = self._make_engine(tmp_export_dir)
        engine.config.format = "xlsx"
        formatter = engine._get_formatter(tmp_export_dir)
        assert isinstance(formatter, HTMLFormatter)
