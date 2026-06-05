"""Tests for the MediaDownloader."""
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest

from python.export.media_downloader import MediaDownloader


@pytest.fixture
def downloader(tmp_export_dir):
    """Create a MediaDownloader with a mock client and tmp dir."""
    client = MagicMock()
    return MediaDownloader(
        client=client,
        output_dir=tmp_export_dir,
        max_file_size=100 * 1024 * 1024,  # 100 MB
        media_types={"photo", "video", "document"},
    )


@pytest.fixture
def mock_photo_message():
    """Create a mock message with a photo."""
    msg = MagicMock()
    msg.id = 42
    msg.date = datetime(2024, 2, 10, 14, 30, 0, tzinfo=timezone.utc)
    msg.photo = MagicMock()
    msg.photo.id = 12345
    msg.video = None
    msg.audio = None
    msg.voice = None
    msg.document = None
    msg.file = None
    msg.media = MagicMock()
    msg.media.size = 5000
    msg.media.document = None  # No document for photo messages
    msg.download_media = AsyncMock(return_value="/tmp/test.jpg")
    return msg


@pytest.fixture
def mock_document_message():
    """Create a mock message with a document."""
    msg = MagicMock()
    msg.id = 43
    msg.date = datetime(2024, 2, 11, 9, 0, 0, tzinfo=timezone.utc)
    msg.photo = None
    msg.video = None
    msg.audio = None
    msg.voice = None
    msg.document = MagicMock()
    msg.document.id = 67890
    msg.file = MagicMock()
    msg.file.name = "report.pdf"
    msg.file.size = 1024000
    msg.media = MagicMock()
    msg.media.document = msg.document
    msg.media.document.size = 1024000
    msg.download_media = AsyncMock(return_value="/tmp/report.pdf")
    return msg


class TestGenerateFilename:
    """Tests for _generate_filename with various message types."""

    def test_photo_filename(self, downloader, mock_photo_message):
        """Test filename generation for a photo message."""
        filename = downloader._generate_filename(mock_photo_message)
        assert filename == "2024-02-10_14-30-00_42_media.jpg"

    def test_video_filename(self, downloader):
        """Test filename generation for a video message."""
        msg = MagicMock()
        msg.id = 50
        msg.date = datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        msg.photo = None
        msg.video = MagicMock()
        msg.audio = None
        msg.voice = None
        msg.document = None
        msg.file = None
        filename = downloader._generate_filename(msg)
        assert filename == "2024-03-01_12-00-00_50_media.mp4"

    def test_document_with_original_name(self, downloader, mock_document_message):
        """Test filename generation for a document with original name."""
        filename = downloader._generate_filename(mock_document_message)
        assert filename == "2024-02-11_09-00-00_43_report.pdf"

    def test_audio_filename(self, downloader):
        """Test filename generation for an audio message."""
        msg = MagicMock()
        msg.id = 55
        msg.date = datetime(2024, 4, 5, 16, 45, 0, tzinfo=timezone.utc)
        msg.photo = None
        msg.video = None
        msg.audio = MagicMock()
        msg.voice = None
        msg.document = None
        msg.file = None
        filename = downloader._generate_filename(msg)
        assert filename == "2024-04-05_16-45-00_55_media.mp3"

    def test_voice_filename(self, downloader):
        """Test filename generation for a voice message."""
        msg = MagicMock()
        msg.id = 60
        msg.date = datetime(2024, 5, 20, 8, 15, 0, tzinfo=timezone.utc)
        msg.photo = None
        msg.video = None
        msg.audio = None
        msg.voice = MagicMock()
        msg.document = None
        msg.file = None
        filename = downloader._generate_filename(msg)
        assert filename == "2024-05-20_08-15-00_60_media.ogg"

    def test_unknown_type_uses_bin(self, downloader):
        """Test filename generation for unknown media uses .bin extension."""
        msg = MagicMock()
        msg.id = 70
        msg.date = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        msg.photo = None
        msg.video = None
        msg.audio = None
        msg.voice = None
        msg.document = None
        msg.file = None
        filename = downloader._generate_filename(msg)
        assert filename == "2024-06-01_00-00-00_70_media.bin"


class TestGetFileId:
    """Tests for _get_file_id deduplication logic."""

    def test_photo_file_id(self, downloader, mock_photo_message):
        """Test file_id extraction for photos."""
        file_id = downloader._get_file_id(mock_photo_message)
        assert file_id == "photo_12345"

    def test_document_file_id(self, downloader, mock_document_message):
        """Test file_id extraction for documents."""
        file_id = downloader._get_file_id(mock_document_message)
        assert file_id == "doc_67890"

    def test_no_media_returns_none(self, downloader):
        """Test file_id returns None when no photo or document."""
        msg = MagicMock()
        msg.photo = None
        msg.document = None
        file_id = downloader._get_file_id(msg)
        assert file_id is None


class TestDedupLogic:
    """Tests for deduplication behavior."""

    @pytest.mark.asyncio
    async def test_same_file_id_not_downloaded_twice(self, downloader, mock_photo_message, tmp_export_dir):
        """Test that same file_id is not downloaded twice."""
        # Pre-populate the dedup cache
        cached_path = tmp_export_dir / "cached_photo.jpg"
        cached_path.touch()
        downloader._downloaded["photo_12345"] = cached_path

        result = await downloader.download(mock_photo_message)
        assert result == cached_path
        # download_media should NOT have been called
        mock_photo_message.download_media.assert_not_awaited()


class TestMaxFileSize:
    """Tests for max_file_size limit checking."""

    @pytest.mark.asyncio
    async def test_file_exceeding_max_size_skipped(self, tmp_export_dir):
        """Test that files exceeding max_file_size are skipped."""
        client = MagicMock()
        downloader = MediaDownloader(
            client=client,
            output_dir=tmp_export_dir,
            max_file_size=1024,  # 1 KB limit
        )

        msg = MagicMock()
        msg.id = 99
        msg.date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        msg.photo = None
        msg.document = None
        msg.media = MagicMock()
        msg.media.size = 0
        msg.media.document = MagicMock()
        msg.media.document.size = 2048  # 2 KB, exceeds limit
        msg.download_media = AsyncMock()

        result = await downloader.download(msg)
        assert result is None
        msg.download_media.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_file_within_max_size_downloaded(self, tmp_export_dir):
        """Test that files within max_file_size are downloaded."""
        client = MagicMock()
        downloader = MediaDownloader(
            client=client,
            output_dir=tmp_export_dir,
            max_file_size=10 * 1024 * 1024,  # 10 MB limit
        )

        msg = MagicMock()
        msg.id = 100
        msg.date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        msg.photo = MagicMock()
        msg.photo.id = 999
        msg.video = None
        msg.audio = None
        msg.voice = None
        msg.document = None
        msg.file = None
        msg.media = MagicMock()
        msg.media.size = 5000  # 5 KB, within limit
        # Simulate no document attribute for the size check
        msg.media.document = None

        downloaded_path = str(tmp_export_dir / "2024-01-01_00-00-00_100_media.jpg")
        msg.download_media = AsyncMock(return_value=downloaded_path)

        result = await downloader.download(msg)
        assert result is not None
