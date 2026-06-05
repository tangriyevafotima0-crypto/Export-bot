"""Shared pytest fixtures for Python backend tests."""
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest

# Ensure the python package is importable from teleexport/ root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_telegram_client():
    """Mock TelegramClient with common async methods."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=True)
    client.get_me = AsyncMock(return_value=MagicMock(
        id=12345,
        first_name="Test",
        last_name="User",
        username="testuser",
        phone="1234567890",
    ))
    client.get_entity = AsyncMock(return_value=MagicMock(
        title="Test Chat",
        broadcast=False,
        megagroup=False,
    ))
    client.iter_messages = MagicMock()
    client.send_code_request = AsyncMock()
    client.sign_in = AsyncMock()
    client.log_out = AsyncMock()
    return client


@pytest.fixture
def mock_message_factory():
    """Factory for creating mock Message objects with configurable attributes."""

    def _create(
        msg_id=1,
        text="Hello, world!",
        date=None,
        sender_id=100,
        sender_name="Alice",
        photo=None,
        video=None,
        document=None,
        audio=None,
        voice=None,
        sticker=None,
        media=None,
        reply_to_msg_id=None,
        fwd_from=None,
        file=None,
        poll=None,
        geo=None,
        contact=None,
    ):
        msg = MagicMock()
        msg.id = msg_id
        msg.text = text
        msg.date = date or datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        msg.sender_id = sender_id
        msg.sender_name = sender_name
        msg.photo = photo
        msg.video = video
        msg.document = document
        msg.audio = audio
        msg.voice = voice
        msg.sticker = sticker
        msg.media = media
        msg.reply_to_msg_id = reply_to_msg_id
        msg.fwd_from = fwd_from
        msg.file = file
        msg.poll = poll
        msg.geo = geo
        msg.contact = contact
        msg.download_media = AsyncMock(return_value="/tmp/media/file.jpg")
        return msg

    return _create


@pytest.fixture
def tmp_export_dir(tmp_path):
    """Temporary directory for export output."""
    export_dir = tmp_path / "export_output"
    export_dir.mkdir()
    return export_dir


@pytest.fixture
def mock_entity():
    """Mock entity (chat/user) with title and type attributes."""
    entity = MagicMock()
    entity.title = "Test Chat"
    entity.broadcast = False
    entity.megagroup = False
    return entity
